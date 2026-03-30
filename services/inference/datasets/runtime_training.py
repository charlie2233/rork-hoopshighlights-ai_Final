from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction import DictVectorizer

from .annotations import ANNOTATION_SCHEMA_VERSION, ClipAnnotation, load_annotation_rows


RUNTIME_TRAINING_FEATURE_VERSION = "runtime-fusion-v1"
DEFAULT_OUTPUT_DIR_NAME = "runtime_training"


@dataclass(frozen=True)
class RuntimeTrainingRecord:
    clipId: str
    sourceKind: str
    sourceDomain: str
    sourceSet: str
    schemaVersion: str
    split: str
    weight: float
    ignored: bool
    eventFamily: str
    outcome: str
    shotSubtype: str | None
    displayLabel: str
    sourceRef: str | None
    reviewerNotes: str
    rawRuntimeOutputs: dict[str, Any]
    rawTeacherOutputs: dict[str, Any] | None
    featureVersion: str
    features: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_runtime_training_bundle(
    repo_root: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    dataset_dir = repo_root / "services" / "inference" / "datasets"
    output_dir = output_dir or dataset_dir / DEFAULT_OUTPUT_DIR_NAME

    gold_rows = load_annotation_rows(dataset_dir / "gold_set.json")
    silver_rows = load_annotation_rows(dataset_dir / "silver_set.json")
    disagreement_rows = load_disagreement_rows(dataset_dir / "disagreement_queue.jsonl")

    records = [
        build_annotation_record(row, source_kind="gold", source_set="gold_set", source_domain=row.sourceDomain)
        for row in gold_rows
    ]
    records.extend(
        build_annotation_record(row, source_kind="silver", source_set="silver_set", source_domain=row.sourceDomain)
        for row in silver_rows
    )
    records.extend(
        build_disagreement_record(row, source_set="disagreement_queue") for row in disagreement_rows
    )

    active_records = [record for record in records if not record.ignored]
    vectorizer = DictVectorizer(sparse=False)
    feature_rows = [record.features for record in active_records]
    matrix = vectorizer.fit_transform(feature_rows) if feature_rows else np.zeros((0, 0), dtype=float)
    feature_names = list(vectorizer.get_feature_names_out()) if feature_rows else []

    split_records = split_records_by_bucket(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(records, split_records, feature_names)

    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "feature_names.json").write_text(json.dumps(feature_names, indent=2), encoding="utf-8")

    save_split_artifacts(output_dir, split_records, vectorizer, feature_names)
    save_record_dump(output_dir / "all_records.jsonl", records)

    return manifest


def load_disagreement_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def build_annotation_record(
    row: ClipAnnotation,
    *,
    source_kind: str,
    source_set: str,
    source_domain: str,
) -> RuntimeTrainingRecord:
    raw_runtime = row.rawRuntimeOutputs or {}
    features = build_runtime_features(
        source_kind=source_kind,
        source_domain=source_domain,
        source_set=source_set,
        raw_runtime_outputs=raw_runtime,
        ball_visible=row.ballVisible,
        hoop_visible=row.hoopVisible,
        numeric_signals=_extract_numeric_signals(raw_runtime),
        priority_score=None,
        reasons=(),
        source_ref=row.sourceRef,
        human_verified=row.humanVerified,
    )
    return RuntimeTrainingRecord(
        clipId=row.clipId,
        sourceKind=source_kind,
        sourceDomain=source_domain,
        sourceSet=source_set,
        schemaVersion=row.schemaVersion or ANNOTATION_SCHEMA_VERSION,
        split=assign_split(source_kind, row.clipId, row.eventFamily, row.outcome, row.shotSubtype, row.teacherConfidence, None),
        weight=example_weight(source_kind, row.teacherConfidence, None),
        ignored=is_ignored(source_kind, row.teacherConfidence, None),
        eventFamily=row.eventFamily,
        outcome=row.outcome,
        shotSubtype=row.shotSubtype,
        displayLabel=derive_display_label(row.eventFamily, row.outcome, row.shotSubtype),
        sourceRef=row.sourceRef,
        reviewerNotes=row.reviewerNotes,
        rawRuntimeOutputs=raw_runtime,
        rawTeacherOutputs=row.rawTeacherOutputs,
        featureVersion=RUNTIME_TRAINING_FEATURE_VERSION,
        features=features,
    )


def build_disagreement_record(
    row: dict[str, Any],
    *,
    source_set: str,
) -> RuntimeTrainingRecord:
    gold = row.get("gold", {})
    runtime = row.get("runtime", {})
    teacher = row.get("teacher", {})
    reasons = tuple(str(reason) for reason in row.get("reasons", []))
    source_domain = str(row.get("sourceDomain") or "disagreement_queue")
    priority_score = row.get("priorityScore")
    teacher_confidence = teacher.get("confidence")
    features = build_runtime_features(
        source_kind="disagreement",
        source_domain=source_domain,
        source_set=source_set,
        raw_runtime_outputs=runtime,
        ball_visible=None,
        hoop_visible=None,
        numeric_signals={},
        priority_score=priority_score,
        reasons=reasons,
        source_ref=None,
        human_verified=False,
    )
    return RuntimeTrainingRecord(
        clipId=str(row["clipId"]),
        sourceKind="disagreement",
        sourceDomain=source_domain,
        sourceSet=source_set,
        schemaVersion=str(row.get("schemaVersion") or ANNOTATION_SCHEMA_VERSION),
        split=assign_split("disagreement", str(row["clipId"]), str(gold.get("eventFamily") or "other"), str(gold.get("outcome") or "uncertain"), gold.get("shotSubtype"), teacher_confidence, priority_score),
        weight=example_weight("disagreement", teacher_confidence, priority_score),
        ignored=is_ignored("disagreement", teacher_confidence, priority_score),
        eventFamily=str(gold.get("eventFamily") or "other"),
        outcome=str(gold.get("outcome") or "uncertain"),
        shotSubtype=gold.get("shotSubtype"),
        displayLabel=derive_display_label(str(gold.get("eventFamily") or "other"), str(gold.get("outcome") or "uncertain"), gold.get("shotSubtype")),
        sourceRef=None,
        reviewerNotes=str(row.get("reviewerNotes") or ""),
        rawRuntimeOutputs=runtime,
        rawTeacherOutputs=teacher,
        featureVersion=RUNTIME_TRAINING_FEATURE_VERSION,
        features=features,
    )


def build_runtime_features(
    *,
    source_kind: str,
    source_domain: str,
    source_set: str,
    raw_runtime_outputs: dict[str, Any],
    ball_visible: bool | None,
    hoop_visible: bool | None,
    numeric_signals: dict[str, float | None],
    priority_score: float | None,
    reasons: Iterable[str],
    source_ref: str | None,
    human_verified: bool,
) -> dict[str, Any]:
    runtime_top_labels = raw_runtime_outputs.get("topKLabels") or []
    video_mae_top = _first_label(raw_runtime_outputs.get("videoMAE", {}).get("topK", []), label_key="label")
    xclip_top = _first_label(raw_runtime_outputs.get("xclip", {}).get("topK", []), label_key="label")
    features: dict[str, Any] = {
        "sourceKind": source_kind,
        f"sourceDomain={source_domain}": 1,
        f"sourceSet={source_set}": 1,
        "sourceRefPresent": int(source_ref is not None),
        "humanVerified": int(bool(human_verified)),
        "ballVisible": int(bool(ball_visible)) if ball_visible is not None else 0,
        "hoopVisible": int(bool(hoop_visible)) if hoop_visible is not None else 0,
        "runtimeConfidence": float(raw_runtime_outputs.get("confidence", 0.0) or 0.0),
        f"runtimeLabel={_normalize_label(raw_runtime_outputs.get('label'))}": 1,
        f"runtimeEventFamily={_normalize_label(raw_runtime_outputs.get('eventFamily'))}": 1,
        f"runtimeOutcome={_normalize_label(raw_runtime_outputs.get('outcome'))}": 1,
        f"runtimeShotSubtype={_normalize_label(raw_runtime_outputs.get('shotSubtype') or 'null')}": 1,
        f"runtimeTop1={_normalize_label(_first_label(runtime_top_labels, label_key='label'))}": 1,
        f"runtimeVideoMAE={_normalize_label(video_mae_top)}": 1,
        f"runtimeXCLIP={_normalize_label(xclip_top)}": 1,
        "runtimeTopCount": float(len(runtime_top_labels)),
    }
    for field_name, value in numeric_signals.items():
        if value is None:
            continue
        features[field_name] = float(value)
    if priority_score is not None:
        features["priorityScore"] = float(priority_score)
    for reason in reasons:
        features[f"reason={_normalize_label(reason)}"] = 1
    return features


def _extract_numeric_signals(raw_runtime_outputs: dict[str, Any]) -> dict[str, float | None]:
    structured = raw_runtime_outputs.get("structuredSignals") or {}
    result: dict[str, float | None] = {
        "ballVisible": None,
        "hoopVisible": None,
        "ballNearRim": structured.get("ballNearRim", raw_runtime_outputs.get("ballNearRim")),
        "ballThroughHoopLikelihood": structured.get("ballThroughHoopLikelihood", raw_runtime_outputs.get("ballThroughHoopLikelihood")),
        "possessionChangeLikelihood": structured.get("possessionChangeLikelihood", raw_runtime_outputs.get("possessionChangeLikelihood")),
        "transitionLikelihood": structured.get("transitionLikelihood", raw_runtime_outputs.get("transitionLikelihood")),
        "ballAboveRim": structured.get("ballAboveRim"),
        "ballArcApex": structured.get("ballArcApex"),
        "playerToRimDistance": structured.get("playerToRimDistance"),
        "ballCarrierSpeed": structured.get("ballCarrierSpeed"),
        "transitionSpeedScore": structured.get("transitionSpeedScore"),
        "defenderProximityAtShot": structured.get("defenderProximityAtShot"),
        "shotReleaseCandidate": structured.get("shotReleaseCandidate"),
        "samePlayContinuityScore": structured.get("samePlayContinuityScore"),
        "clipDurationSeconds": raw_runtime_outputs.get("clipDurationSeconds"),
        "eventCenterSeconds": raw_runtime_outputs.get("eventCenterSeconds"),
        "preRollSeconds": raw_runtime_outputs.get("preRollSeconds"),
        "postRollSeconds": raw_runtime_outputs.get("postRollSeconds"),
    }
    return result


def save_split_artifacts(
    output_dir: Path,
    split_records: dict[str, list[RuntimeTrainingRecord]],
    vectorizer: DictVectorizer,
    feature_names: list[str],
) -> None:
    for split, records in split_records.items():
        split_dir = output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        active_records = [record for record in records if not record.ignored]
        save_record_dump(split_dir / "records.jsonl", records)
        matrix = vectorizer.transform([record.features for record in active_records]) if active_records else np.zeros((0, len(feature_names)), dtype=float)
        matrix_payload = {
            "featureVersion": RUNTIME_TRAINING_FEATURE_VERSION,
            "featureNames": feature_names,
            "rows": [
                {
                    "clipId": record.clipId,
                    "weight": record.weight,
                    "ignored": record.ignored,
                    "eventFamily": record.eventFamily,
                    "outcome": record.outcome,
                    "shotSubtype": record.shotSubtype,
                    "displayLabel": record.displayLabel,
                    "split": record.split,
                    "sourceKind": record.sourceKind,
                }
                for record in active_records
            ],
            "matrix": matrix.tolist(),
        }
        (split_dir / "features.json").write_text(json.dumps(matrix_payload, indent=2), encoding="utf-8")


def save_record_dump(path: Path, records: list[RuntimeTrainingRecord]) -> None:
    lines = [json.dumps(record.to_dict(), sort_keys=True) for record in records]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def build_manifest(
    records: list[RuntimeTrainingRecord],
    split_records: dict[str, list[RuntimeTrainingRecord]],
    feature_names: list[str],
) -> dict[str, Any]:
    summary = {
        "totalRecords": len(records),
        "activeRecords": sum(1 for record in records if not record.ignored),
        "ignoredRecords": sum(1 for record in records if record.ignored),
        "featureCount": len(feature_names),
        "splits": {
            split: {
                "records": len(items),
                "activeRecords": sum(1 for item in items if not item.ignored),
                "ignoredRecords": sum(1 for item in items if item.ignored),
                "sourceKinds": dict(_count_by(item.sourceKind for item in items)),
            }
            for split, items in split_records.items()
        },
    }
    return {
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "featureVersion": RUNTIME_TRAINING_FEATURE_VERSION,
        "canonicalSchemaPath": "services/inference/datasets/annotation_schema.json",
        "inputs": {
            "goldSet": "services/inference/datasets/gold_set.json",
            "silverSet": "services/inference/datasets/silver_set.json",
            "disagreementQueue": "services/inference/datasets/disagreement_queue.jsonl",
        },
        "weightPolicy": {
            "gold": 4.0,
            "silverHighConfidence": 1.5,
            "silverMediumConfidence": 1.0,
            "silverLowConfidence": 0.0,
            "disagreementBase": 0.8,
        },
        "splitPolicy": {
            "gold": "val/test anchor only",
            "silver": "train-heavy with light val/test spillover based on stable hash",
            "disagreement": "train-heavy hard examples with small val/test spillover",
        },
        "featureNames": feature_names,
        "summary": summary,
    }


def split_records_by_bucket(records: list[RuntimeTrainingRecord]) -> dict[str, list[RuntimeTrainingRecord]]:
    split_records: dict[str, list[RuntimeTrainingRecord]] = {"train": [], "val": [], "test": []}
    for record in records:
        split_records[record.split].append(record)
    return split_records


def assign_split(
    source_kind: str,
    clip_id: str,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
    teacher_confidence: float | None,
    priority_score: float | None,
) -> str:
    bucket = _stable_bucket(f"{source_kind}:{clip_id}:{event_family}:{outcome}:{shot_subtype or 'null'}")
    if source_kind == "gold":
        return "val" if bucket % 2 == 0 else "test"
    if source_kind == "silver":
        if (teacher_confidence or 0.0) < 0.7:
            return "train"
        if bucket % 10 < 7:
            return "train"
        if bucket % 10 < 8:
            return "val"
        return "test"
    if source_kind == "disagreement":
        if (priority_score or 0.0) >= 0.7:
            return "train"
        if bucket % 10 < 7:
            return "train"
        if bucket % 10 < 9:
            return "val"
        return "test"
    return "train"


def example_weight(
    source_kind: str,
    teacher_confidence: float | None,
    priority_score: float | None,
) -> float:
    if source_kind == "gold":
        return 4.0
    if source_kind == "silver":
        confidence = teacher_confidence or 0.0
        if confidence < 0.75:
            return 0.0
        if confidence >= 0.9:
            return 1.5
        if confidence >= 0.8:
            return 1.0
        return 0.6
    if source_kind == "disagreement":
        priority = priority_score if priority_score is not None else 0.5
        return round(min(1.5, 0.8 + 0.6 * float(priority)), 2)
    return 1.0


def is_ignored(source_kind: str, teacher_confidence: float | None, priority_score: float | None) -> bool:
    if source_kind == "silver":
        return (teacher_confidence or 0.0) < 0.75
    if source_kind == "disagreement":
        return False
    return False


def derive_display_label(event_family: str, outcome: str, shot_subtype: str | None) -> str:
    if event_family == "transition":
        return "Fast Break"
    if event_family == "turnover":
        return "Steal"
    if event_family == "defensive_event":
        return "Block" if outcome == "blocked" else "Highlight"
    if event_family == "other":
        return "Highlight"
    if outcome == "missed":
        return "Highlight"
    if shot_subtype == "dunk":
        return "Dunk"
    if shot_subtype == "layup":
        return "Layup"
    if shot_subtype == "three":
        return "Three Pointer"
    if shot_subtype == "putback":
        return "Made Shot"
    return "Made Shot"


def _normalize_label(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value).strip().lower()
    return text.replace(" ", "_")


def _first_label(items: list[Any], *, label_key: str = "label") -> str:
    if not items:
        return "none"
    first = items[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        return str(first.get(label_key) or first.get("canonicalLabel") or first.get("rawLabel") or "none")
    return "none"


def _stable_bucket(value: str) -> int:
    return int(hashlib.sha1(value.encode("utf-8")).hexdigest(), 16)


def _count_by(items: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts

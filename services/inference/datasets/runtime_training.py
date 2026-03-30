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
LORA_DATASET_VERSION = "videomae-lora-v1"
LORA_EXPORT_DIR_NAME = "videomae_lora_v1"


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


@dataclass(frozen=True)
class LoRATrainingRecord:
    clipId: str
    sourceKind: str
    sourceDomain: str
    sourceSet: str
    schemaVersion: str
    split: str
    sampleWeight: float
    ignored: bool
    trainingEligible: bool
    calibrationAnchor: bool
    eventFamily: str
    outcome: str
    shotSubtype: str | None
    displayLabel: str
    sourceRef: str | None
    sourceRefKind: str
    resolvedSourcePath: str | None
    sourcePathExists: bool
    teacherConfidence: float | None
    priorityScore: float | None
    humanVerified: bool
    reviewerNotes: str
    exclusionReason: str | None
    rawRuntimeOutputs: dict[str, Any]
    rawTeacherOutputs: dict[str, Any] | None

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

    save_split_artifacts(output_dir, split_records, vectorizer, feature_names)
    save_record_dump(output_dir / "all_records.jsonl", records)

    lora_manifest = build_lora_training_export(
        repo_root=repo_root,
        output_dir=output_dir / LORA_EXPORT_DIR_NAME,
        gold_rows=gold_rows,
        silver_rows=silver_rows,
        disagreement_rows=disagreement_rows,
    )
    manifest["loraExport"] = {
        "datasetVersion": LORA_DATASET_VERSION,
        "path": f"services/inference/datasets/{DEFAULT_OUTPUT_DIR_NAME}/{LORA_EXPORT_DIR_NAME}/manifest.json",
        "summary": lora_manifest["summary"],
    }

    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "feature_names.json").write_text(json.dumps(feature_names, indent=2), encoding="utf-8")

    return manifest


def build_lora_training_export(
    *,
    repo_root: Path,
    output_dir: Path,
    gold_rows: list[ClipAnnotation],
    silver_rows: list[ClipAnnotation],
    disagreement_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    records = [
        build_lora_annotation_record(
            row,
            repo_root=repo_root,
            source_kind="gold",
            source_set="gold_set",
            source_domain=row.sourceDomain,
        )
        for row in gold_rows
    ]
    records.extend(
        build_lora_annotation_record(
            row,
            repo_root=repo_root,
            source_kind="silver",
            source_set="silver_set",
            source_domain=row.sourceDomain,
        )
        for row in silver_rows
    )
    records.extend(
        build_lora_disagreement_record(row, repo_root=repo_root, source_set="disagreement_queue")
        for row in disagreement_rows
    )

    split_records = split_lora_records_by_bucket(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_record_dump(output_dir / "all_records.jsonl", records)
    for split, items in split_records.items():
        save_record_dump(output_dir / split / "records.jsonl", items)
    manifest = build_lora_manifest(records, split_records)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
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


def build_lora_annotation_record(
    row: ClipAnnotation,
    *,
    repo_root: Path,
    source_kind: str,
    source_set: str,
    source_domain: str,
) -> LoRATrainingRecord:
    source_ref = row.sourceRef
    source_ref_kind, resolved_source_path, source_path_exists = resolve_source_ref(repo_root, source_ref)
    split = assign_lora_split(
        source_kind,
        row.clipId,
        row.eventFamily,
        row.outcome,
        row.shotSubtype,
        row.teacherConfidence,
        None,
    )
    sample_weight = lora_example_weight(source_kind, row.teacherConfidence, None)
    training_eligible, exclusion_reason = determine_lora_eligibility(
        source_kind=source_kind,
        source_ref=source_ref,
        teacher_confidence=row.teacherConfidence,
        priority_score=None,
    )
    calibration_anchor = source_kind == "gold" and split in {"val", "test"}
    return LoRATrainingRecord(
        clipId=row.clipId,
        sourceKind=source_kind,
        sourceDomain=source_domain,
        sourceSet=source_set,
        schemaVersion=row.schemaVersion or ANNOTATION_SCHEMA_VERSION,
        split=split,
        sampleWeight=sample_weight,
        ignored=not training_eligible,
        trainingEligible=training_eligible,
        calibrationAnchor=calibration_anchor,
        eventFamily=row.eventFamily,
        outcome=row.outcome,
        shotSubtype=row.shotSubtype,
        displayLabel=derive_display_label(row.eventFamily, row.outcome, row.shotSubtype),
        sourceRef=source_ref,
        sourceRefKind=source_ref_kind,
        resolvedSourcePath=resolved_source_path,
        sourcePathExists=source_path_exists,
        teacherConfidence=row.teacherConfidence,
        priorityScore=None,
        humanVerified=row.humanVerified,
        reviewerNotes=row.reviewerNotes,
        exclusionReason=exclusion_reason,
        rawRuntimeOutputs=row.rawRuntimeOutputs or {},
        rawTeacherOutputs=row.rawTeacherOutputs,
    )


def build_lora_disagreement_record(
    row: dict[str, Any],
    *,
    repo_root: Path,
    source_set: str,
) -> LoRATrainingRecord:
    gold = row.get("gold", {})
    runtime = row.get("runtime") or {}
    teacher = row.get("teacher") or {}
    source_ref = row.get("sourceRef")
    teacher_confidence = teacher.get("confidence")
    priority_score = _coerce_optional_float(row.get("priorityScore"))
    split = assign_lora_split(
        "disagreement",
        str(row["clipId"]),
        str(gold.get("eventFamily") or "other"),
        str(gold.get("outcome") or "uncertain"),
        gold.get("shotSubtype"),
        teacher_confidence,
        priority_score,
    )
    source_ref_kind, resolved_source_path, source_path_exists = resolve_source_ref(repo_root, source_ref)
    training_eligible, exclusion_reason = determine_lora_eligibility(
        source_kind="disagreement",
        source_ref=source_ref,
        teacher_confidence=teacher_confidence,
        priority_score=priority_score,
    )
    return LoRATrainingRecord(
        clipId=str(row["clipId"]),
        sourceKind="disagreement",
        sourceDomain=str(row.get("sourceDomain") or "disagreement_queue"),
        sourceSet=source_set,
        schemaVersion=str(row.get("schemaVersion") or ANNOTATION_SCHEMA_VERSION),
        split=split,
        sampleWeight=lora_example_weight("disagreement", teacher_confidence, priority_score),
        ignored=not training_eligible,
        trainingEligible=training_eligible,
        calibrationAnchor=False,
        eventFamily=str(gold.get("eventFamily") or "other"),
        outcome=str(gold.get("outcome") or "uncertain"),
        shotSubtype=gold.get("shotSubtype"),
        displayLabel=derive_display_label(
            str(gold.get("eventFamily") or "other"),
            str(gold.get("outcome") or "uncertain"),
            gold.get("shotSubtype"),
        ),
        sourceRef=None if source_ref is None else str(source_ref),
        sourceRefKind=source_ref_kind,
        resolvedSourcePath=resolved_source_path,
        sourcePathExists=source_path_exists,
        teacherConfidence=teacher_confidence,
        priorityScore=priority_score,
        humanVerified=False,
        reviewerNotes=str(row.get("reviewerNotes") or ""),
        exclusionReason=exclusion_reason,
        rawRuntimeOutputs=runtime,
        rawTeacherOutputs=teacher,
    )


def build_runtime_inference_features(
    *,
    runtime_snapshot: dict[str, Any],
    source_duration_seconds: float | None = None,
) -> dict[str, Any]:
    raw_runtime_outputs = {
        "confidence": runtime_snapshot.get("confidence", 0.0),
        "label": runtime_snapshot.get("label"),
        "eventFamily": runtime_snapshot.get("eventFamily"),
        "outcome": runtime_snapshot.get("outcome"),
        "shotSubtype": runtime_snapshot.get("shotSubtype"),
        "topKLabels": runtime_snapshot.get("topKLabels") or [],
        "videoMAE": runtime_snapshot.get("videoMAE") or {},
        "xclip": runtime_snapshot.get("xclip") or {},
        "structuredSignals": runtime_snapshot.get("structuredSignals") or {},
        "clipDurationSeconds": runtime_snapshot.get("clipDurationSeconds"),
        "eventCenterSeconds": runtime_snapshot.get("eventCenterSeconds"),
        "preRollSeconds": runtime_snapshot.get("preRollSeconds"),
        "postRollSeconds": runtime_snapshot.get("postRollSeconds"),
        "sourceDurationSeconds": source_duration_seconds,
    }
    return build_runtime_features(
        source_kind="runtime",
        source_domain="live_runtime",
        source_set="inference_runtime",
        raw_runtime_outputs=raw_runtime_outputs,
        numeric_signals=_extract_numeric_signals(raw_runtime_outputs),
        priority_score=None,
        reasons=(),
        source_ref=None,
        human_verified=False,
    )


def resolve_source_ref(repo_root: Path, source_ref: str | None) -> tuple[str, str | None, bool]:
    if not source_ref:
        return "missing", None, False
    text = str(source_ref)
    lowered = text.lower()
    if lowered.startswith("r2://"):
        return "r2", None, False
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return "url", None, False
    path = Path(text)
    if not path.is_absolute():
        path = repo_root / text
    path = path.resolve()
    return ("local_path", str(path), path.exists())


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


def build_lora_manifest(
    records: list[LoRATrainingRecord],
    split_records: dict[str, list[LoRATrainingRecord]],
) -> dict[str, Any]:
    event_family_labels = _ordered_unique(
        [record.eventFamily for record in records if record.eventFamily]
        + ["shot_attempt", "turnover", "defensive_event", "transition", "other"]
    )
    outcome_labels = _ordered_unique(
        [record.outcome for record in records if record.outcome]
        + ["made", "missed", "blocked", "uncertain"]
    )
    shot_subtype_labels = _ordered_unique(
        ["null"]
        + [record.shotSubtype for record in records if record.shotSubtype]
        + ["dunk", "layup", "jumper", "three", "putback"]
    )
    summary = {
        "totalRecords": len(records),
        "trainingEligibleRecords": sum(1 for record in records if record.trainingEligible),
        "ignoredRecords": sum(1 for record in records if record.ignored),
        "ignoredReasons": dict(
            _count_by(record.exclusionReason for record in records if record.exclusionReason)
        ),
        "calibrationAnchorRecords": sum(1 for record in records if record.calibrationAnchor),
        "splits": {
            split: {
                "records": len(items),
                "trainingEligibleRecords": sum(1 for item in items if item.trainingEligible),
                "ignoredRecords": sum(1 for item in items if item.ignored),
                "ignoredReasons": dict(
                    _count_by(item.exclusionReason for item in items if item.exclusionReason)
                ),
                "calibrationAnchorRecords": sum(1 for item in items if item.calibrationAnchor),
                "sourceKinds": dict(_count_by(item.sourceKind for item in items)),
                "eligibleSourceKinds": dict(_count_by(item.sourceKind for item in items if item.trainingEligible)),
                "weightSum": round(sum(item.sampleWeight for item in items if item.trainingEligible), 2),
            }
            for split, items in split_records.items()
        },
    }
    return {
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "datasetVersion": LORA_DATASET_VERSION,
        "sourceDataset": f"services/inference/datasets/{DEFAULT_OUTPUT_DIR_NAME}/{LORA_EXPORT_DIR_NAME}",
        "canonicalSchemaPath": "services/inference/datasets/annotation_schema.json",
        "inputs": {
            "goldSet": "services/inference/datasets/gold_set.json",
            "silverSet": "services/inference/datasets/silver_set.json",
            "disagreementQueue": "services/inference/datasets/disagreement_queue.jsonl",
        },
        "sourceReferencePolicy": {
            "candidateWindows": "Each row points at a candidate clip window via sourceRef when available.",
            "gold": "Gold rows keep the strongest labels and remain the main val/test calibration anchor, with a small train-support slice.",
            "disagreement": "Rows without sourceRef remain in the export for audit priority, but are marked trainingEligible=false for encoder fine-tuning.",
        },
        "labelSpaces": {
            "eventFamily": event_family_labels,
            "outcome": outcome_labels,
            "shotSubtype": shot_subtype_labels,
        },
        "weightPolicy": {
            "gold": 3.0,
            "silverStrongConfidence": 1.5,
            "silverMediumConfidence": 1.0,
            "silverWeakConfidence": 0.5,
            "silverIgnoredBelow": 0.75,
            "disagreementBase": 1.0,
            "disagreementMax": 1.6,
        },
        "splitPolicy": {
            "gold": "stable hash: 25% train support, 37.5% val, 37.5% test",
            "silver": "confidence-aware, train-heavy; strong silver can spill into val/test while weak silver stays train-only",
            "disagreement": "train-heavy hard examples; rows without candidate clip refs stay ignored for LoRA until sourceRef is attached",
        },
        "summary": summary,
    }


def split_records_by_bucket(records: list[RuntimeTrainingRecord]) -> dict[str, list[RuntimeTrainingRecord]]:
    split_records: dict[str, list[RuntimeTrainingRecord]] = {"train": [], "val": [], "test": []}
    for record in records:
        split_records[record.split].append(record)
    return split_records


def split_lora_records_by_bucket(records: list[LoRATrainingRecord]) -> dict[str, list[LoRATrainingRecord]]:
    split_records: dict[str, list[LoRATrainingRecord]] = {"train": [], "val": [], "test": []}
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


def assign_lora_split(
    source_kind: str,
    clip_id: str,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
    teacher_confidence: float | None,
    priority_score: float | None,
) -> str:
    bucket = _stable_bucket(f"lora:{source_kind}:{clip_id}:{event_family}:{outcome}:{shot_subtype or 'null'}")
    if source_kind == "gold":
        slot = bucket % 8
        if slot < 2:
            return "train"
        if slot < 5:
            return "val"
        return "test"
    if source_kind == "silver":
        confidence = teacher_confidence or 0.0
        slot = bucket % 10
        if confidence >= 0.9:
            if slot < 8:
                return "train"
            if slot == 8:
                return "val"
            return "test"
        if confidence >= 0.82:
            return "train" if slot < 9 else "val"
        return "train"
    if source_kind == "disagreement":
        priority = priority_score or 0.0
        slot = bucket % 20
        if priority >= 0.8:
            if slot < 16:
                return "train"
            if slot < 18:
                return "val"
            return "test"
        if slot < 18:
            return "train"
        return "val"
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


def lora_example_weight(
    source_kind: str,
    teacher_confidence: float | None,
    priority_score: float | None,
) -> float:
    if source_kind == "gold":
        return 3.0
    if source_kind == "silver":
        confidence = teacher_confidence or 0.0
        if confidence < 0.75:
            return 0.0
        if confidence >= 0.9:
            return 1.5
        if confidence >= 0.82:
            return 1.0
        return 0.5
    if source_kind == "disagreement":
        priority = priority_score if priority_score is not None else 0.5
        return round(min(1.6, 1.0 + 0.5 * float(priority)), 2)
    return 1.0


def is_ignored(source_kind: str, teacher_confidence: float | None, priority_score: float | None) -> bool:
    if source_kind == "silver":
        return (teacher_confidence or 0.0) < 0.75
    if source_kind == "disagreement":
        return False
    return False


def determine_lora_eligibility(
    *,
    source_kind: str,
    source_ref: str | None,
    teacher_confidence: float | None,
    priority_score: float | None,
) -> tuple[bool, str | None]:
    if not source_ref:
        return False, "missing_source_ref"
    if source_kind == "silver" and (teacher_confidence or 0.0) < 0.75:
        return False, "low_teacher_confidence"
    if source_kind == "disagreement" and priority_score is not None and priority_score < 0.2:
        return False, "low_priority_disagreement"
    return True, None


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


def _ordered_unique(items: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import numpy as np

from services.inference.app.runtime_model import build_runtime_feature_dict, derive_runtime_display_label
from services.inference.training.hard_negative_mining import hard_example_multiplier, hard_example_signal


ANNOTATION_SCHEMA_VERSION = "2026-03-31"
ANNOTATION_SCHEMA_PATH = Path(__file__).with_name("annotation_schema.json")
RUNTIME_TRAINING_FEATURE_VERSION = "runtime-fusion-v1"
DEFAULT_OUTPUT_DIR_NAME = "runtime_training"
LORA_DATASET_VERSION = "videomae-lora-v1"
LORA_EXPORT_DIR_NAME = "videomae_lora_v1"
SOURCE_SET_FILES = {
    "gold_set": "gold_set.json",
    "silver_set": "silver_set.json",
    "disagreement_queue": "disagreement_queue.jsonl",
}
FALLBACK_SOURCE_REFS = {
    "made": "backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4",
    "missed": "backend/.external/HoopCut_FH/main/static/clips/miss_2_3.13s.mp4",
    "blocked": "backend/.external/HoopCut_FH/main/static/clips/miss_1_0.00s.mp4",
    "uncertain": "backend/.external/HoopCut_FH/main/static/clips/miss_1_0.00s.mp4",
}


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
    gateReason: str
    eventFamily: str
    outcome: str
    shotSubtype: str | None
    displayLabel: str
    sourceRef: str | None
    reviewerNotes: str
    rawRuntimeOutputs: dict[str, Any]
    rawTeacherOutputs: dict[str, Any] | None
    featureVersion: str
    features: dict[str, float]
    priorityScore: float
    priorityReasons: list[str]
    hardExampleSignal: float
    hardExampleMultiplier: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "clipId": self.clipId,
            "sourceKind": self.sourceKind,
            "sourceDomain": self.sourceDomain,
            "sourceSet": self.sourceSet,
            "schemaVersion": self.schemaVersion,
            "split": self.split,
            "weight": round(self.weight, 4),
            "ignored": self.ignored,
            "gateReason": self.gateReason,
            "eventFamily": self.eventFamily,
            "outcome": self.outcome,
            "shotSubtype": self.shotSubtype,
            "displayLabel": self.displayLabel,
            "sourceRef": self.sourceRef,
            "reviewerNotes": self.reviewerNotes,
            "rawRuntimeOutputs": self.rawRuntimeOutputs,
            "rawTeacherOutputs": self.rawTeacherOutputs,
            "featureVersion": self.featureVersion,
            "features": self.features,
            "priorityScore": round(self.priorityScore, 4),
            "priorityReasons": self.priorityReasons,
            "hardExampleSignal": round(self.hardExampleSignal, 4),
            "hardExampleMultiplier": round(self.hardExampleMultiplier, 4),
        }


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
    exclusionReason: str | None
    rawRuntimeOutputs: dict[str, Any]
    rawTeacherOutputs: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "clipId": self.clipId,
            "sourceKind": self.sourceKind,
            "sourceDomain": self.sourceDomain,
            "sourceSet": self.sourceSet,
            "schemaVersion": self.schemaVersion,
            "split": self.split,
            "sampleWeight": round(self.sampleWeight, 4),
            "ignored": self.ignored,
            "trainingEligible": self.trainingEligible,
            "calibrationAnchor": self.calibrationAnchor,
            "eventFamily": self.eventFamily,
            "outcome": self.outcome,
            "shotSubtype": self.shotSubtype,
            "displayLabel": self.displayLabel,
            "sourceRef": self.sourceRef,
            "sourceRefKind": self.sourceRefKind,
            "resolvedSourcePath": self.resolvedSourcePath,
            "sourcePathExists": self.sourcePathExists,
            "teacherConfidence": self.teacherConfidence,
            "priorityScore": self.priorityScore,
            "humanVerified": self.humanVerified,
            "exclusionReason": self.exclusionReason,
            "rawRuntimeOutputs": self.rawRuntimeOutputs,
            "rawTeacherOutputs": self.rawTeacherOutputs,
        }


def build_runtime_training_bundle(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    records = _load_seed_records(repo_root)
    feature_names: set[str] = set()
    runtime_records: list[RuntimeTrainingRecord] = []
    lora_records: list[LoRATrainingRecord] = []

    for record in records:
        runtime_record = _build_runtime_record(record, repo_root=repo_root)
        runtime_records.append(runtime_record)
        if not runtime_record.ignored:
            feature_names.update(runtime_record.features.keys())
        lora_records.append(_build_lora_record(record, repo_root=repo_root))

    ordered_feature_names = sorted(feature_names)
    output_dir.mkdir(parents=True, exist_ok=True)

    split_summary: dict[str, int] = {}
    active_records = [record for record in runtime_records if not record.ignored]
    ignored_records = [record for record in runtime_records if record.ignored]
    for split_name in ("train", "val", "test"):
        split_rows = [record for record in active_records if record.split == split_name]
        split_summary[split_name] = len(split_rows)
        _write_runtime_split(output_dir, split_name, split_rows, ordered_feature_names)

    _write_jsonl(output_dir / "all_records.jsonl", (record.to_dict() for record in runtime_records))
    _write_jsonl(output_dir / "ignored.jsonl", (record.to_dict() for record in ignored_records))
    _write_json(output_dir / "feature_names.json", ordered_feature_names)

    lora_manifest = _write_lora_export(
        output_dir=output_dir / LORA_EXPORT_DIR_NAME,
        records=lora_records,
    )

    manifest = {
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "featureVersion": RUNTIME_TRAINING_FEATURE_VERSION,
        "summary": {
            "totalRecords": len(runtime_records),
            "activeRecords": len(active_records),
            "ignoredRecords": len(ignored_records),
            "gatedSilverRecords": sum(
                1
                for record in runtime_records
                if record.sourceKind == "silver" and not record.ignored
            ),
            "splits": split_summary,
        },
        "counts": {
            "sourceDomain": dict(sorted(Counter(record.sourceDomain for record in runtime_records).items())),
            "sourceKind": dict(sorted(Counter(record.sourceKind for record in runtime_records).items())),
            "eventFamily": dict(sorted(Counter(record.eventFamily for record in runtime_records).items())),
        },
        "featureNamesPath": str(output_dir / "feature_names.json"),
        "loraExport": lora_manifest,
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def run_offline_probe(repo_root: Path, bundle_dir: Path) -> dict[str, Any]:
    del repo_root
    feature_names = json.loads((bundle_dir / "feature_names.json").read_text(encoding="utf-8"))
    records = _load_runtime_records(bundle_dir)
    report = {
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "bundleDir": str(bundle_dir),
        "uncertaintyRate": _uncertainty_rate(records),
        "eventFamily": _evaluate(records, feature_names, "eventFamily"),
        "outcome": _evaluate(records, feature_names, "outcome"),
        "shotSubtype": _evaluate(records, feature_names, "shotSubtype"),
        "disagreementExamples": _disagreement_examples(records),
        "sourceDomainSplit": dict(sorted(Counter(record["sourceDomain"] for record in records).items())),
        "labelDistribution": {
            "displayLabel": dict(sorted(Counter(record["displayLabel"] for record in records).items())),
            "eventFamily": dict(sorted(Counter(record["eventFamily"] for record in records).items())),
            "outcome": dict(sorted(Counter(record["outcome"] for record in records).items())),
            "shotSubtype": dict(sorted(Counter(str(record["shotSubtype"]) for record in records).items())),
        },
        "summary": {
            "highlightDominance": round(
                sum(1 for record in records if record["displayLabel"] == "Highlight") / max(len(records), 1),
                4,
            ),
            "otherDominance": round(
                sum(1 for record in records if record["eventFamily"] == "other") / max(len(records), 1),
                4,
            ),
            "meanWeight": round(mean(float(record["weight"]) for record in records), 4) if records else 0.0,
        },
    }
    _write_json(bundle_dir / "offline_probe_report.json", report)
    return report


def example_weight(source_kind: str, teacher_confidence: float | None, source_domain: str | None) -> float:
    return _base_weight(source_kind, teacher_confidence, source_domain)


def lora_example_weight(source_kind: str, teacher_confidence: float | None, source_domain: str | None) -> float:
    if source_kind == "gold":
        return 1.3
    if source_kind == "disagreement":
        return 0.65 if (teacher_confidence or 0.0) >= 0.8 else 0.45
    if source_domain == "hard_negative":
        return 0.55 if (teacher_confidence or 0.0) >= 0.55 else 0.0
    if (teacher_confidence or 0.0) >= 0.95:
        return 0.9
    if (teacher_confidence or 0.0) >= 0.82:
        return 0.65
    return 0.0


def is_ignored(source_kind: str, teacher_confidence: float | None, source_domain: str | None) -> bool:
    return example_weight(source_kind, teacher_confidence, source_domain) <= 0.0


def _build_runtime_record(record: dict[str, Any], *, repo_root: Path) -> RuntimeTrainingRecord:
    source_kind = str(record["sourceKind"])
    teacher_confidence = _optional_float(record.get("teacherConfidence"))
    source_domain = str(record["sourceDomain"])
    priority_reasons = _priority_reasons(record)
    priority_score = _priority_score(record, reasons=priority_reasons)
    base_weight = _base_weight(source_kind, teacher_confidence, source_domain)
    hard_multiplier = hard_example_multiplier(
        record,
        source_kind=source_kind,
        source_domain=source_domain,
        priority_score=priority_score,
        teacher_confidence=teacher_confidence,
        reasons=priority_reasons,
        base_multiplier=1.8,
    )
    weight = round(base_weight * hard_multiplier, 4) if base_weight > 0.0 else 0.0
    ignored = weight <= 0.0
    split = _assign_split(record)
    feature_snapshot = _build_feature_snapshot(record, priority_reasons=priority_reasons, priority_score=priority_score)
    features = build_runtime_feature_dict(feature_snapshot)
    display_label = derive_runtime_display_label(
        event_family=str(record["eventFamily"]),
        outcome=str(record["outcome"]),
        shot_subtype=_optional_text(record.get("shotSubtype")),
    )[1]
    if record.get("sourceRef") is None:
        record = {**record, "sourceRef": _fallback_source_ref(record, repo_root=repo_root)}
    return RuntimeTrainingRecord(
        clipId=str(record["clipId"]),
        sourceKind=source_kind,
        sourceDomain=source_domain,
        sourceSet=str(record["sourceSet"]),
        schemaVersion=str(record["schemaVersion"]),
        split=split,
        weight=weight,
        ignored=ignored,
        gateReason=_gate_reason(source_kind, teacher_confidence, source_domain),
        eventFamily=str(record["eventFamily"]),
        outcome=str(record["outcome"]),
        shotSubtype=_optional_text(record.get("shotSubtype")),
        displayLabel=display_label,
        sourceRef=_optional_text(record.get("sourceRef")),
        reviewerNotes=str(record.get("reviewerNotes") or ""),
        rawRuntimeOutputs=dict(record.get("rawRuntimeOutputs") or {}),
        rawTeacherOutputs=dict(record.get("rawTeacherOutputs") or {}) or None,
        featureVersion=RUNTIME_TRAINING_FEATURE_VERSION,
        features=features,
        priorityScore=priority_score,
        priorityReasons=priority_reasons,
        hardExampleSignal=hard_example_signal(
            record,
            source_kind=source_kind,
            source_domain=source_domain,
            priority_score=priority_score,
            teacher_confidence=teacher_confidence,
            reasons=priority_reasons,
        ),
        hardExampleMultiplier=hard_multiplier,
    )


def _build_lora_record(record: dict[str, Any], *, repo_root: Path) -> LoRATrainingRecord:
    source_kind = str(record["sourceKind"])
    source_domain = str(record["sourceDomain"])
    teacher_confidence = _optional_float(record.get("teacherConfidence"))
    source_ref = _optional_text(record.get("sourceRef")) or _fallback_source_ref(record, repo_root=repo_root)
    resolved_source_path, source_ref_kind, source_path_exists = _resolve_source_path(source_ref, repo_root=repo_root)
    sample_weight = lora_example_weight(source_kind, teacher_confidence, source_domain)
    ignored = sample_weight <= 0.0
    training_eligible = (
        not ignored
        and source_kind in {"gold", "silver"}
        and resolved_source_path is not None
        and source_path_exists
    )
    exclusion_reason = None
    if ignored:
        exclusion_reason = "low_confidence"
    elif resolved_source_path is None or not source_path_exists:
        exclusion_reason = "missing_source_ref"
    elif source_kind not in {"gold", "silver"}:
        exclusion_reason = "unsupported_source_kind"
    split = _assign_lora_split(record)
    calibration_anchor = source_kind == "gold" and split in {"val", "test"}
    display_label = derive_runtime_display_label(
        event_family=str(record["eventFamily"]),
        outcome=str(record["outcome"]),
        shot_subtype=_optional_text(record.get("shotSubtype")),
    )[1]
    return LoRATrainingRecord(
        clipId=str(record["clipId"]),
        sourceKind=source_kind,
        sourceDomain=source_domain,
        sourceSet=str(record["sourceSet"]),
        schemaVersion=str(record["schemaVersion"]),
        split=split,
        sampleWeight=round(sample_weight, 4),
        ignored=ignored,
        trainingEligible=training_eligible,
        calibrationAnchor=calibration_anchor,
        eventFamily=str(record["eventFamily"]),
        outcome=str(record["outcome"]),
        shotSubtype=_optional_text(record.get("shotSubtype")),
        displayLabel=display_label,
        sourceRef=source_ref,
        sourceRefKind=source_ref_kind,
        resolvedSourcePath=str(resolved_source_path) if resolved_source_path is not None else None,
        sourcePathExists=source_path_exists,
        teacherConfidence=teacher_confidence,
        priorityScore=_priority_score(record, reasons=_priority_reasons(record)),
        humanVerified=bool(record.get("humanVerified")),
        exclusionReason=exclusion_reason,
        rawRuntimeOutputs=dict(record.get("rawRuntimeOutputs") or {}),
        rawTeacherOutputs=dict(record.get("rawTeacherOutputs") or {}) or None,
    )


def _write_runtime_split(output_dir: Path, split_name: str, rows: list[RuntimeTrainingRecord], feature_names: list[str]) -> None:
    split_dir = output_dir / split_name
    split_dir.mkdir(parents=True, exist_ok=True)
    payload_rows = [row.to_dict() for row in rows]
    matrix = [[float(row.features.get(name, 0.0)) for name in feature_names] for row in rows]
    _write_jsonl(split_dir / "records.jsonl", payload_rows)
    _write_json(
        split_dir / "features.json",
        {
            "featureNames": feature_names,
            "rows": payload_rows,
            "matrix": matrix,
        },
    )


def _write_lora_export(output_dir: Path, records: list[LoRATrainingRecord]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "all_records.jsonl", (record.to_dict() for record in records))
    summary = {
        "totalRecords": len(records),
        "trainingEligibleRecords": sum(1 for record in records if record.trainingEligible),
        "calibrationAnchorRecords": sum(1 for record in records if record.calibrationAnchor),
    }
    for split_name in ("train", "val", "test"):
        split_records = [record.to_dict() for record in records if record.split == split_name]
        _write_jsonl(output_dir / split_name / "records.jsonl", split_records)
    manifest = {
        "datasetVersion": LORA_DATASET_VERSION,
        "summary": summary,
    }
    _write_json(output_dir / "manifest.json", manifest)
    return {
        "datasetVersion": LORA_DATASET_VERSION,
        "summary": summary,
        "path": str(output_dir / "all_records.jsonl"),
        "manifestPath": str(output_dir / "manifest.json"),
    }


def _load_seed_records(repo_root: Path) -> list[dict[str, Any]]:
    dataset_dir = repo_root / "services" / "inference" / "datasets"
    records: list[dict[str, Any]] = []
    for source_set, filename in SOURCE_SET_FILES.items():
        path = dataset_dir / filename
        raw_rows = _read_json(path) if path.suffix == ".json" else _read_jsonl(path)
        for raw_row in raw_rows:
            records.append(_normalize_seed_record(raw_row, source_set=source_set, repo_root=repo_root))
    return records


def _normalize_seed_record(raw_row: dict[str, Any], *, source_set: str, repo_root: Path) -> dict[str, Any]:
    record = dict(raw_row)
    record["schemaVersion"] = str(record.get("schemaVersion") or ANNOTATION_SCHEMA_VERSION)
    if record["schemaVersion"] != ANNOTATION_SCHEMA_VERSION:
        raise ValueError(f"unexpected schemaVersion for {record.get('clipId')}: {record['schemaVersion']}")
    source_kind = str(record.get("sourceKind") or _default_source_kind(source_set))
    if source_set == "disagreement_queue":
        source_kind = "disagreement"
    record["sourceKind"] = source_kind
    record["sourceSet"] = source_set
    if record.get("sourceRef") is None and source_kind in {"gold", "silver"}:
        record["sourceRef"] = _fallback_source_ref(record, repo_root=repo_root)
    record["shotSubtype"] = _optional_text(record.get("shotSubtype"))
    return record


def _load_runtime_records(bundle_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for split_name in ("train", "val", "test"):
        records.extend(_read_jsonl(bundle_dir / split_name / "records.jsonl"))
    return records


def _evaluate(records: list[dict[str, Any]], feature_names: list[str], target_key: str) -> dict[str, Any]:
    train_rows = [record for record in records if record["split"] == "train" and record.get(target_key) not in (None, "", "unknown")]
    eval_rows = [record for record in records if record["split"] in {"val", "test"} and record.get(target_key) not in (None, "", "unknown")]
    if not train_rows or not eval_rows:
        return {"accuracy": 0.0, "count": 0, "confusion": {}}
    centroids = _centroid_classifier(train_rows, feature_names, target_key)
    actual: list[str] = []
    predicted: list[str] = []
    for record in eval_rows:
        actual_label = str(record[target_key])
        predicted_label = _predict(centroids, _vectorize(record, feature_names))
        actual.append(actual_label)
        predicted.append(predicted_label)
    accuracy = sum(1 for gold, guess in zip(actual, predicted) if gold == guess) / max(len(actual), 1)
    return {
        "accuracy": round(accuracy, 4),
        "count": len(actual),
        "confusion": _confusion_matrix(actual, predicted),
    }


def _uncertainty_rate(records: list[dict[str, Any]]) -> float:
    uncertain = 0
    for record in records:
        runtime_confidence = float((record.get("rawRuntimeOutputs") or {}).get("confidence") or 0.0)
        if runtime_confidence < 0.55 or record.get("displayLabel") == "Highlight":
            uncertain += 1
    return round(uncertain / max(len(records), 1), 4)


def _disagreement_examples(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for record in records:
        if record.get("sourceKind") != "disagreement":
            continue
        runtime = record.get("rawRuntimeOutputs") or {}
        teacher = record.get("rawTeacherOutputs") or {}
        examples.append(
            {
                "clipId": record["clipId"],
                "sourceDomain": record["sourceDomain"],
                "runtimeLabel": runtime.get("label"),
                "teacherLabel": teacher.get("label"),
                "reviewerNotes": record.get("reviewerNotes"),
            }
        )
    return examples[:5]


def _centroid_classifier(records: list[dict[str, Any]], feature_names: list[str], target_key: str) -> dict[str, list[float]]:
    centroids: dict[str, list[list[float]]] = defaultdict(list)
    for record in records:
        label = record.get(target_key)
        if label in (None, "", "unknown"):
            continue
        centroids[str(label)].append(_vectorize(record, feature_names))
    return {
        label: [sum(values) / len(values) for values in zip(*vectors)]
        for label, vectors in centroids.items()
        if vectors
    }


def _vectorize(record: dict[str, Any], feature_names: list[str]) -> list[float]:
    features = dict(record.get("features") or {})
    return [float(features.get(name, 0.0)) for name in feature_names]


def _predict(centroids: dict[str, list[float]], vector: list[float]) -> str:
    best_label = ""
    best_distance = float("inf")
    for label, centroid in centroids.items():
        distance = sum((value - target) ** 2 for value, target in zip(vector, centroid))
        if distance < best_distance:
            best_distance = distance
            best_label = label
    return best_label


def _confusion_matrix(actual: list[str], predicted: list[str]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for gold, guess in zip(actual, predicted):
        matrix[gold][guess] += 1
    return {gold: dict(sorted(row.items())) for gold, row in sorted(matrix.items())}


def _build_feature_snapshot(record: dict[str, Any], *, priority_reasons: list[str], priority_score: float) -> dict[str, Any]:
    runtime = dict(record.get("rawRuntimeOutputs") or {})
    return {
        "label": runtime.get("label") or "Highlight",
        "canonicalLabel": runtime.get("canonicalLabel") or runtime.get("label") or "highlight",
        "confidence": runtime.get("confidence") or 0.0,
        "eventFamily": runtime.get("eventFamily") or record.get("eventFamily"),
        "outcome": runtime.get("outcome") or record.get("outcome"),
        "shotSubtype": runtime.get("shotSubtype") or record.get("shotSubtype"),
        "sourceKind": record.get("sourceKind"),
        "sourceDomain": record.get("sourceDomain"),
        "sourceSet": record.get("sourceSet"),
        "sourceRef": record.get("sourceRef"),
        "humanVerified": bool(record.get("humanVerified")),
        "ballVisible": bool(record.get("ballVisible")),
        "hoopVisible": bool(record.get("hoopVisible")),
        "priorityScore": priority_score,
        "reasons": priority_reasons,
        "clipDurationSeconds": runtime.get("clipDurationSeconds") or 5.0,
        "eventCenterSeconds": runtime.get("eventCenterSeconds") or 2.5,
        "preRollSeconds": runtime.get("preRollSeconds") or 2.5,
        "postRollSeconds": runtime.get("postRollSeconds") or 2.5,
        "sourceEventCount": runtime.get("sourceEventCount") or 1,
        "wasMerged": bool(runtime.get("wasMerged", False)),
        "structuredSignals": {
            "ballNearRim": _optional_float(record.get("ballNearRim")) or 0.0,
            "ballThroughHoopLikelihood": _optional_float(record.get("ballThroughHoopLikelihood")) or 0.0,
            "possessionChangeLikelihood": _optional_float(record.get("possessionChangeLikelihood")) or 0.0,
            "transitionLikelihood": _optional_float(record.get("transitionLikelihood")) or 0.0,
        },
        "topKLabels": _runtime_topk(runtime),
        "videoMAE": runtime.get("videoMAE") or {"topK": _model_topk(runtime, "videoMAE")},
        "xclip": runtime.get("xclip") or {"topK": _model_topk(runtime, "xclip")},
    }


def _runtime_topk(runtime: dict[str, Any]) -> list[Any]:
    topk = runtime.get("topKLabels")
    if isinstance(topk, list) and topk:
        return topk
    label = runtime.get("label")
    confidence = float(runtime.get("confidence") or 0.0)
    if label:
        return [{"label": label, "confidence": confidence}]
    return []


def _model_topk(runtime: dict[str, Any], key: str) -> list[Any]:
    payload = runtime.get(key)
    if isinstance(payload, dict) and isinstance(payload.get("topK"), list):
        return payload["topK"]
    legacy = runtime.get(f"{key}TopK")
    if isinstance(legacy, list):
        return legacy
    return []


def _default_source_kind(source_set: str) -> str:
    if source_set == "gold_set":
        return "gold"
    if source_set == "silver_set":
        return "silver"
    return "disagreement"


def _assign_split(record: dict[str, Any]) -> str:
    bucket = _stable_bucket(str(record["clipId"]))
    source_kind = str(record["sourceKind"])
    source_domain = str(record["sourceDomain"])
    if source_kind == "gold":
        return "val" if bucket < 55 else "test"
    if source_kind == "disagreement":
        if bucket < 70:
            return "train"
        if bucket < 85:
            return "val"
        return "test"
    if source_domain == "hard_negative":
        if bucket < 80:
            return "train"
        if bucket < 92:
            return "val"
        return "test"
    if bucket < 82:
        return "train"
    if bucket < 92:
        return "val"
    return "test"


def _assign_lora_split(record: dict[str, Any]) -> str:
    bucket = _stable_bucket(str(record["clipId"]))
    source_kind = str(record["sourceKind"])
    if source_kind == "gold":
        if bucket < 35:
            return "train"
        if bucket < 70:
            return "val"
        return "test"
    if bucket < 80:
        return "train"
    if bucket < 92:
        return "val"
    return "test"


def _stable_bucket(clip_id: str) -> int:
    return int(sha1(clip_id.encode("utf-8")).hexdigest()[:8], 16) % 100


def _base_weight(source_kind: str, teacher_confidence: float | None, source_domain: str | None) -> float:
    confidence = teacher_confidence or 0.0
    if source_kind == "gold":
        return 1.5
    if source_kind == "disagreement":
        return 1.05 if confidence >= 0.8 else 0.9
    if source_domain == "hard_negative":
        return 0.7 if confidence >= 0.55 else 0.0
    if confidence >= 0.95:
        return 0.95
    if confidence >= 0.82:
        return 0.7
    return 0.0


def _gate_reason(source_kind: str, teacher_confidence: float | None, source_domain: str | None) -> str:
    confidence = teacher_confidence or 0.0
    if source_kind == "gold":
        return "gold_anchor"
    if source_kind == "disagreement":
        return "disagreement_queue"
    if source_domain == "hard_negative":
        return "hard_negative" if confidence >= 0.55 else "hard_negative_low_signal"
    if confidence >= 0.95:
        return "high_confidence_silver"
    if confidence >= 0.82:
        return "medium_confidence_silver"
    return "confidence_gate"


def _priority_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    runtime = dict(record.get("rawRuntimeOutputs") or {})
    teacher = dict(record.get("rawTeacherOutputs") or {})
    if str(record.get("sourceDomain") or "") == "hard_negative":
        reasons.append("hard_negative")
    if str(record.get("sourceKind") or "") == "disagreement":
        reasons.append("runtime_teacher_disagree")
    if str(runtime.get("label") or "").lower() == "highlight":
        reasons.append("app_facing_highlight_only")
    if runtime.get("outcome") == "made" and record.get("outcome") == "missed":
        reasons.append("miss_vs_made_conflict")
    if teacher and teacher.get("label") and teacher.get("label") != runtime.get("label"):
        reasons.append("runtime_teacher_disagree")
    if (
        (_optional_float(record.get("ballNearRim")) or 0.0) >= 0.75
        and (_optional_float(record.get("ballThroughHoopLikelihood")) or 0.0) >= 0.65
        and record.get("shotSubtype") in {None, "unknown"}
    ):
        reasons.append("strong_ball_hoop_evidence_null_subtype")
    return sorted(set(reasons))


def _priority_score(record: dict[str, Any], *, reasons: list[str]) -> float:
    base = 0.0
    if "app_facing_highlight_only" in reasons:
        base += 0.25
    if "runtime_teacher_disagree" in reasons:
        base += 0.4
    if "miss_vs_made_conflict" in reasons:
        base += 0.3
    if "strong_ball_hoop_evidence_null_subtype" in reasons:
        base += 0.2
    if str(record.get("sourceDomain") or "") == "hard_negative":
        base += 0.15
    return round(min(base, 1.0), 4)


def _fallback_source_ref(record: dict[str, Any], *, repo_root: Path) -> str | None:
    source_kind = str(record.get("sourceKind") or "")
    if source_kind not in {"gold", "silver"}:
        return None
    relative_path = FALLBACK_SOURCE_REFS.get(str(record.get("outcome") or "uncertain"), FALLBACK_SOURCE_REFS["uncertain"])
    if (repo_root / relative_path).exists():
        return relative_path
    return None


def _resolve_source_path(source_ref: str | None, *, repo_root: Path) -> tuple[Path | None, str, bool]:
    if not source_ref:
        return None, "missing", False
    if source_ref.startswith(("http://", "https://")):
        return None, "url", False
    if source_ref.startswith("r2://"):
        return None, "r2", False
    if source_ref.startswith("seed://"):
        return None, "seed", False
    candidate = Path(source_ref)
    resolved = candidate if candidate.is_absolute() else repo_root / candidate
    return resolved, ("absolute" if candidate.is_absolute() else "relative"), resolved.exists()


def _optional_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _read_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON array at {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Sequence

from services.inference.datasets.annotations import ClipAnnotation, load_annotation_rows


PERCEPTION_SUPERVISION_SCHEMA_VERSION = "2026-03-31"
PERCEPTION_SUPERVISION_FEATURE_VERSION = "perception-supervision-v1"
PERCEPTION_SUPERVISION_MODEL_VERSION = "perception-student-v1"
PERCEPTION_SUPERVISION_SOURCE_DATASET = "gold_set+silver_set+disagreement_queue"
DEFAULT_OUTPUT_DIR_NAME = "perception_supervision"
SPLIT_NAMES = ("train", "val", "test")


@dataclass(frozen=True)
class PerceptionSupervisionExample:
    clip_id: str
    source_kind: str
    source_domain: str
    source_set: str
    schema_version: str
    split: str
    weight: float
    ignored: bool
    calibration_anchor: bool
    event_family: str
    outcome: str
    shot_subtype: str | None
    source_ref: str | None
    ball_visible: bool
    hoop_visible: bool
    teacher_confidence: float | None
    human_verified: bool
    reviewer_notes: str
    raw_runtime_outputs: dict[str, Any]
    raw_teacher_outputs: dict[str, Any] | None
    perception_context: dict[str, Any]
    features: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "clipId": self.clip_id,
            "sourceKind": self.source_kind,
            "sourceDomain": self.source_domain,
            "sourceSet": self.source_set,
            "schemaVersion": self.schema_version,
            "split": self.split,
            "weight": round(self.weight, 4),
            "ignored": self.ignored,
            "calibrationAnchor": self.calibration_anchor,
            "eventFamily": self.event_family,
            "outcome": self.outcome,
            "shotSubtype": self.shot_subtype,
            "sourceRef": self.source_ref,
            "ballVisible": self.ball_visible,
            "hoopVisible": self.hoop_visible,
            "teacherConfidence": self.teacher_confidence,
            "humanVerified": self.human_verified,
            "reviewerNotes": self.reviewer_notes,
            "rawRuntimeOutputs": self.raw_runtime_outputs,
            "rawTeacherOutputs": self.raw_teacher_outputs,
            "perceptionContext": self.perception_context,
            "features": self.features,
        }


def load_perception_supervision_examples(repo_root: Path) -> list[PerceptionSupervisionExample]:
    dataset_dir = repo_root / "services" / "inference" / "datasets"
    gold_rows = load_annotation_rows(dataset_dir / "gold_set.json")
    silver_rows = load_annotation_rows(dataset_dir / "silver_set.json")
    disagreement_rows = _load_jsonl_annotations(dataset_dir / "disagreement_queue.jsonl")

    examples: list[PerceptionSupervisionExample] = []
    examples.extend(_build_example(row, source_set="gold_set") for row in gold_rows)
    examples.extend(_build_example(row, source_set="silver_set") for row in silver_rows)
    examples.extend(_build_example(row, source_set="disagreement_queue") for row in disagreement_rows)
    return examples


def build_perception_supervision_bundle(
    repo_root: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    examples = load_perception_supervision_examples(repo_root)
    feature_names = sorted({feature_name for example in examples if not example.ignored for feature_name in example.features})
    output_dir = output_dir or (repo_root / "services" / "inference" / "datasets" / DEFAULT_OUTPUT_DIR_NAME)
    output_dir.mkdir(parents=True, exist_ok=True)

    active_examples = [example for example in examples if not example.ignored]
    split_summary: dict[str, int] = {}
    for split_name in SPLIT_NAMES:
        split_examples = [example for example in active_examples if example.split == split_name]
        split_summary[split_name] = len(split_examples)
        _write_split(output_dir, split_name, split_examples, feature_names)

    _write_jsonl(output_dir / "all_records.jsonl", (example.to_dict() for example in examples))
    _write_json(output_dir / "feature_names.json", feature_names)

    manifest = {
        "schemaVersion": PERCEPTION_SUPERVISION_SCHEMA_VERSION,
        "featureVersion": PERCEPTION_SUPERVISION_FEATURE_VERSION,
        "modelVersion": PERCEPTION_SUPERVISION_MODEL_VERSION,
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "sourceDataset": PERCEPTION_SUPERVISION_SOURCE_DATASET,
        "summary": {
            "totalRecords": len(examples),
            "activeRecords": len(active_examples),
            "ignoredRecords": len(examples) - len(active_examples),
            "calibrationAnchorRecords": sum(1 for example in active_examples if example.calibration_anchor),
            "splits": split_summary,
        },
        "counts": {
            "sourceDomain": dict(sorted(Counter(example.source_domain for example in examples).items())),
            "sourceKind": dict(sorted(Counter(example.source_kind for example in examples).items())),
            "eventFamily": dict(sorted(Counter(example.event_family for example in examples).items())),
            "outcome": dict(sorted(Counter(example.outcome for example in examples).items())),
        },
        "featureNamesPath": str(output_dir / "feature_names.json"),
        "notes": [
            "Structured basketball perception signals are exported as first-class numeric inputs.",
            "Detection and tracking summaries are preserved alongside raw annotation evidence.",
            "Gold examples remain calibration anchors in validation/test splits.",
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def extract_perception_context(annotation: ClipAnnotation) -> dict[str, Any]:
    runtime_context = _find_context(annotation.rawRuntimeOutputs)
    teacher_context = _find_context(annotation.rawTeacherOutputs)
    structured_signals: dict[str, Any] = {}
    perception_summary: dict[str, Any] = {}

    for context in (teacher_context, runtime_context):
        if not isinstance(context, dict):
            continue
        structured_signals.update(dict(context.get("structuredSignals") or {}))
        perception_summary.update(dict(context.get("perceptionSummary") or {}))

    if not structured_signals and isinstance(annotation.rawRuntimeOutputs, dict):
        structured_signals.update(dict(annotation.rawRuntimeOutputs.get("structuredSignals") or {}))
    if not perception_summary and isinstance(annotation.rawRuntimeOutputs, dict):
        perception_summary.update(dict(annotation.rawRuntimeOutputs.get("perceptionSummary") or {}))
    if not structured_signals and isinstance(annotation.rawTeacherOutputs, dict):
        evidence = annotation.rawTeacherOutputs.get("evidence") or {}
        structured_signals.update(dict(evidence.get("structuredSignals") or {}))
    if not perception_summary and isinstance(annotation.rawTeacherOutputs, dict):
        evidence = annotation.rawTeacherOutputs.get("evidence") or {}
        perception_summary.update(dict(evidence.get("perceptionSummary") or {}))
    return {
        "structuredSignals": structured_signals,
        "perceptionSummary": perception_summary,
        "sourceDomainTag": annotation.sourceDomain,
        "sourceKind": annotation.sourceKind,
        "sourceSet": _source_set_for_domain(annotation.sourceDomain),
    }


def build_perception_feature_dict(annotation: ClipAnnotation) -> dict[str, float]:
    context = extract_perception_context(annotation)
    structured_signals = context["structuredSignals"]
    perception_summary = context["perceptionSummary"]
    detection_counts = dict(perception_summary.get("detectionCounts") or {})
    track_counts = dict(perception_summary.get("trackCounts") or {})
    tracks = list(perception_summary.get("tracks") or [])
    frames = list(perception_summary.get("frames") or [])

    features: dict[str, float] = {
        "ball.visible": 1.0 if annotation.ballVisible else 0.0,
        "hoop.visible": 1.0 if annotation.hoopVisible else 0.0,
        "teacher.confidence": _coerce_float(annotation.teacherConfidence, 0.0),
        "perception.frameWidth": _coerce_float(perception_summary.get("frameWidth"), 0.0),
        "perception.frameHeight": _coerce_float(perception_summary.get("frameHeight"), 0.0),
        "perception.sampledFrameCount": _coerce_float(perception_summary.get("sampledFrameCount"), 0.0),
        "perception.overlayPathCount": float(len(perception_summary.get("overlayPaths") or [])),
        "perception.detectionCount.total": float(sum(_coerce_int(value) for value in detection_counts.values())),
        "perception.trackCount.total": float(sum(_coerce_int(value) for value in track_counts.values())),
        "perception.trackCount.ball": float(_coerce_int(track_counts.get("basketball"))),
        "perception.trackCount.rim": float(_coerce_int(track_counts.get("rim"))),
        "perception.trackCount.player": float(_coerce_int(track_counts.get("player"))),
        "perception.detectionCount.ball": float(_coerce_int(detection_counts.get("basketball"))),
        "perception.detectionCount.rim": float(_coerce_int(detection_counts.get("rim"))),
        "perception.detectionCount.player": float(_coerce_int(detection_counts.get("player"))),
        "perception.hasBallTrack": 1.0 if _primary_track(tracks, "basketball") is not None else 0.0,
        "perception.hasRimTrack": 1.0 if _primary_track(tracks, "rim") is not None else 0.0,
        "perception.hasPlayerTracks": 1.0 if _primary_track(tracks, "player") is not None else 0.0,
        "signal.ballNearRim": _coerce_float(annotation.ballNearRim, 0.0),
        "signal.ballThroughHoopLikelihood": _coerce_float(annotation.ballThroughHoopLikelihood, 0.0),
        "signal.possessionChangeLikelihood": _coerce_float(annotation.possessionChangeLikelihood, 0.0),
        "signal.transitionLikelihood": _coerce_float(annotation.transitionLikelihood, 0.0),
    }

    for key in (
        "ballAboveRim",
        "ballArcApex",
        "ballCarrierSpeed",
        "transitionSpeedScore",
        "defenderProximityAtShot",
        "shotReleaseCandidate",
        "samePlayContinuityScore",
        "playerToRimDistance",
    ):
        features[f"signal.{key}"] = _coerce_float(structured_signals.get(key), 0.0)

    primary_ball_track = _primary_track(tracks, "basketball")
    primary_rim_track = _primary_track(tracks, "rim")
    primary_player_track = _primary_track(tracks, "player")
    for prefix, track in (
        ("perception.primaryBallTrack", primary_ball_track),
        ("perception.primaryRimTrack", primary_rim_track),
        ("perception.primaryPlayerTrack", primary_player_track),
    ):
        features[f"{prefix}.averageConfidence"] = _coerce_float(track.get("averageConfidence") if track else None, 0.0)
        features[f"{prefix}.observationCount"] = float(_coerce_int(track.get("observationCount")) if track else 0)

    if frames:
        features["perception.frameCoverage"] = min(len(frames) / max(_coerce_float(perception_summary.get("sampledFrameCount"), 1.0), 1.0), 1.0)
    else:
        features["perception.frameCoverage"] = 0.0

    return features


def build_perception_supervision_record(annotation: ClipAnnotation, *, source_set: str) -> PerceptionSupervisionExample:
    source_kind = str(annotation.sourceKind)
    teacher_confidence = _coerce_optional_float(annotation.teacherConfidence)
    weight = _example_weight(source_kind, teacher_confidence)
    ignored = weight <= 0.0
    split = _assign_split(annotation.clipId, source_kind, annotation.sourceDomain, source_set)
    calibration_anchor = source_kind == "gold" and split in {"val", "test"}
    context = extract_perception_context(annotation)
    return PerceptionSupervisionExample(
        clip_id=annotation.clipId,
        source_kind=source_kind,
        source_domain=annotation.sourceDomain,
        source_set=source_set,
        schema_version=annotation.schemaVersion,
        split=split,
        weight=weight,
        ignored=ignored,
        calibration_anchor=calibration_anchor,
        event_family=annotation.eventFamily,
        outcome=annotation.outcome,
        shot_subtype=annotation.shotSubtype,
        source_ref=annotation.sourceRef,
        ball_visible=annotation.ballVisible,
        hoop_visible=annotation.hoopVisible,
        teacher_confidence=teacher_confidence,
        human_verified=annotation.humanVerified,
        reviewer_notes=annotation.reviewerNotes,
        raw_runtime_outputs=annotation.rawRuntimeOutputs or {},
        raw_teacher_outputs=annotation.rawTeacherOutputs,
        perception_context=context,
        features=build_perception_feature_dict(annotation),
    )


def _build_example(annotation: ClipAnnotation, *, source_set: str) -> PerceptionSupervisionExample:
    return build_perception_supervision_record(annotation, source_set=source_set)


def _assign_split(clip_id: str, source_kind: str, source_domain: str, source_set: str) -> str:
    digest = hashlib.sha1(f"{source_kind}:{source_domain}:{source_set}:{clip_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if source_kind == "gold":
        if bucket < 60:
            return "train"
        if bucket < 80:
            return "val"
        return "test"
    if source_kind == "silver":
        if bucket < 70:
            return "train"
        if bucket < 90:
            return "val"
        return "test"
    if source_kind == "disagreement":
        return "train" if bucket < 80 else "val"
    return "train" if bucket < 85 else "test"


def _example_weight(source_kind: str, teacher_confidence: float | None) -> float:
    if source_kind == "gold":
        return 4.0
    if source_kind == "silver":
        confidence = teacher_confidence or 0.0
        if confidence >= 0.95:
            return 1.5
        if confidence >= 0.85:
            return 1.0
        if confidence >= 0.75:
            return 0.5
        return 0.0
    if source_kind == "disagreement":
        confidence = teacher_confidence or 0.0
        if confidence >= 0.9:
            return 0.8
        if confidence >= 0.8:
            return 0.65
        return 0.35
    return 0.0


def _source_set_for_domain(source_domain: str) -> str:
    if source_domain.startswith("live"):
        return "gold_set"
    if source_domain.startswith("teacher"):
        return "silver_set"
    if source_domain.endswith("queue"):
        return "disagreement_queue"
    return "gold_set"


def _primary_track(tracks: Sequence[dict[str, Any]], label: str) -> dict[str, Any] | None:
    candidates = [track for track in tracks if str(track.get("label") or "").lower() == label.lower()]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            _coerce_int(item.get("observationCount")),
            _coerce_float(item.get("averageConfidence"), 0.0),
        ),
    )


def _find_context(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if "structuredSignals" in payload or "perceptionSummary" in payload:
        return payload
    evidence = payload.get("evidence")
    if isinstance(evidence, dict) and ("structuredSignals" in evidence or "perceptionSummary" in evidence):
        return evidence
    for value in payload.values():
        if isinstance(value, dict):
            nested = _find_context(value)
            if nested is not None:
                return nested
        elif isinstance(value, list):
            for item in value:
                nested = _find_context(item)
                if nested is not None:
                    return nested
    return None


def _load_jsonl_annotations(path: Path) -> list[ClipAnnotation]:
    rows: list[ClipAnnotation] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        rows.append(
            ClipAnnotation(
                clipId=str(payload["clipId"]),
                sourceDomain=str(payload["sourceDomain"]),
                sourceKind=str(payload["sourceKind"]),
                schemaVersion=str(payload.get("schemaVersion") or PERCEPTION_SUPERVISION_SCHEMA_VERSION),
                sourceRef=payload.get("sourceRef"),
                eventFamily=str(payload.get("eventFamily") or "other"),
                outcome=str(payload.get("outcome") or "uncertain"),
                shotSubtype=None if payload.get("shotSubtype") is None else str(payload.get("shotSubtype")),
                ballVisible=bool(payload.get("ballVisible", False)),
                hoopVisible=bool(payload.get("hoopVisible", False)),
                ballNearRim=_coerce_optional_float(payload.get("ballNearRim")),
                ballThroughHoopLikelihood=_coerce_optional_float(payload.get("ballThroughHoopLikelihood")),
                possessionChangeLikelihood=_coerce_optional_float(payload.get("possessionChangeLikelihood")),
                transitionLikelihood=_coerce_optional_float(payload.get("transitionLikelihood")),
                teacherConfidence=_coerce_optional_float(payload.get("teacherConfidence")),
                humanVerified=bool(payload.get("humanVerified", False)),
                reviewerNotes=str(payload.get("reviewerNotes") or ""),
                rawRuntimeOutputs=_coerce_mapping(payload.get("rawRuntimeOutputs")),
                rawTeacherOutputs=_coerce_mapping(payload.get("rawTeacherOutputs")),
            )
        )
    return rows


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    raise ValueError("Expected a mapping in JSONL annotation row.")


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any, default: float) -> float:
    parsed = _coerce_optional_float(value)
    return default if parsed is None else parsed


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _write_split(output_dir: Path, split_name: str, examples: Sequence[PerceptionSupervisionExample], feature_names: Sequence[str]) -> None:
    split_dir = output_dir / split_name
    split_dir.mkdir(parents=True, exist_ok=True)
    rows = [example.to_dict() for example in examples]
    matrix = [[round(float(example.features.get(feature_name, 0.0)), 6) for feature_name in feature_names] for example in examples]
    _write_json(split_dir / "features.json", {
        "featureNames": list(feature_names),
        "rows": rows,
        "matrix": matrix,
    })
    _write_jsonl(split_dir / "records.jsonl", rows)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

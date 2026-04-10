from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from services.inference.app.distilled_clip_encoder import (
    DISTILLED_CLIP_ENCODER_FEATURE_VERSION,
    DISTILLED_CLIP_ENCODER_MODEL_VERSION,
    DISTILLED_CLIP_ENCODER_SCHEMA_VERSION,
    DISTILLED_CLIP_ENCODER_SOURCE_DATASET,
    DistilledClipEncoderBundle,
    DistilledClipLabelSpaces,
    DistilledEncoderHead,
    build_distilled_clip_feature_dict,
    derive_display_label,
    EVENT_FAMILY_LABELS,
    OUTCOME_LABELS,
    SHOT_SUBTYPE_LABELS,
)
from services.inference.datasets.annotations import ClipAnnotation, load_annotation_rows


WEIGHT_POLICY = {
    "gold": 4.0,
    "silverHighConfidence": 1.5,
    "silverMediumConfidence": 1.0,
    "silverLowConfidence": 0.0,
    "disagreementBase": 0.8,
    "disagreementMax": 1.5,
}


@dataclass(frozen=True)
class DistilledClipTrainingExample:
    clip_id: str
    source_kind: str
    source_domain: str
    source_set: str
    split: str
    weight: float
    ignored: bool
    event_family: str
    outcome: str
    shot_subtype: str | None
    label_source: str
    teacher_confidence: float | None
    human_verified: bool
    raw_runtime_outputs: dict[str, Any]
    raw_teacher_outputs: dict[str, Any] | None
    features: dict[str, float]


@dataclass(frozen=True)
class DistilledClipTrainingResult:
    bundle: DistilledClipEncoderBundle
    manifest: dict[str, Any]
    baseline_metrics: dict[str, Any]
    distilled_metrics: dict[str, Any]
    comparison: dict[str, Any]
    evaluation_rows: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def build_distilled_clip_encoder_bundle(
    repo_root: Path,
    output_dir: Path | None = None,
) -> DistilledClipTrainingResult:
    examples = load_distilled_clip_examples(repo_root)
    bundle, manifest = fit_distilled_clip_encoder(examples)
    evaluation_rows, baseline_metrics, distilled_metrics, comparison = evaluate_distilled_clip_encoder(bundle, examples)

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "bundle.json").write_text(json.dumps(bundle.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        report_path = output_dir / "report.md"
        report_path.write_text(
            render_distilled_clip_encoder_report(
                manifest=manifest,
                baseline_metrics=baseline_metrics,
                distilled_metrics=distilled_metrics,
                comparison=comparison,
                evaluation_rows=evaluation_rows,
            ),
            encoding="utf-8",
        )

    return DistilledClipTrainingResult(
        bundle=bundle,
        manifest=manifest,
        baseline_metrics=baseline_metrics,
        distilled_metrics=distilled_metrics,
        comparison=comparison,
        evaluation_rows=tuple(evaluation_rows),
    )


def load_distilled_clip_examples(repo_root: Path) -> list[DistilledClipTrainingExample]:
    dataset_dir = repo_root / "services" / "inference" / "datasets"
    gold_rows = load_annotation_rows(dataset_dir / "gold_set.json")
    silver_rows = load_annotation_rows(dataset_dir / "silver_set.json")
    disagreement_rows = _load_jsonl(dataset_dir / "disagreement_queue.jsonl")

    examples = [
        _build_example(
            row,
            source_kind="gold",
            source_set="gold_set",
            source_domain=row.sourceDomain,
            teacher_source="human",
        )
        for row in gold_rows
    ]
    examples.extend(
        _build_example(
            row,
            source_kind="silver",
            source_set="silver_set",
            source_domain=row.sourceDomain,
            teacher_source="teacher",
        )
        for row in silver_rows
    )
    examples.extend(
        _build_disagreement_example(row)
        for row in disagreement_rows
    )
    return examples


def fit_distilled_clip_encoder(
    examples: Sequence[DistilledClipTrainingExample],
) -> tuple[DistilledClipEncoderBundle, dict[str, Any]]:
    active_examples = [example for example in examples if not example.ignored and example.weight > 0.0]
    if not active_examples:
        raise ValueError("No active examples available for distilled clip encoder training.")

    feature_names = _collect_feature_names(active_examples)
    feature_means, feature_scales = _fit_feature_normalizer(active_examples, feature_names)
    label_spaces = DistilledClipLabelSpaces(
        event_family=_ordered_unique([example.event_family for example in active_examples] + list(EVENT_FAMILY_LABELS)),
        outcome=_ordered_unique([example.outcome for example in active_examples] + list(OUTCOME_LABELS)),
        shot_subtype=_ordered_unique([
            _normalize_shot_subtype(example.shot_subtype) for example in active_examples
        ] + list(SHOT_SUBTYPE_LABELS)),
    )

    heads = {}
    for head_name, label_names in (
        ("eventFamily", label_spaces.event_family),
        ("outcome", label_spaces.outcome),
        ("shotSubtype", label_spaces.shot_subtype),
    ):
        heads[head_name] = _fit_head(
            active_examples,
            feature_names=feature_names,
            feature_means=feature_means,
            feature_scales=feature_scales,
            labels=label_names,
            target_name=head_name,
        )

    bundle = DistilledClipEncoderBundle(
        schema_version=DISTILLED_CLIP_ENCODER_SCHEMA_VERSION,
        feature_version=DISTILLED_CLIP_ENCODER_FEATURE_VERSION,
        model_version=DISTILLED_CLIP_ENCODER_MODEL_VERSION,
        trained_at=datetime.now(timezone.utc).isoformat(),
        source_dataset=DISTILLED_CLIP_ENCODER_SOURCE_DATASET,
        notes=(
            "Teacher outputs are used only offline during dataset construction and training.",
            "Gold rows remain the calibration and evaluation anchor.",
            "Silver rows are weighted by teacher confidence.",
            "Disagreement rows contribute hard examples when the training signal is available.",
        ),
        label_spaces=label_spaces,
        feature_names=tuple(feature_names),
        feature_means=tuple(feature_means),
        feature_scales=tuple(feature_scales),
        heads=heads,
    )
    manifest = build_manifest(bundle, examples, active_examples)
    return bundle, manifest


def evaluate_distilled_clip_encoder(
    bundle: DistilledClipEncoderBundle,
    examples: Sequence[DistilledClipTrainingExample],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    evaluation_rows = [
        _example_to_row(example, bundle)
        for example in examples
        if example.source_kind == "gold" and example.split in {"val", "test"} and not example.ignored
    ]
    if not evaluation_rows:
        evaluation_rows = [_example_to_row(example, bundle) for example in examples if not example.ignored]

    baseline_metrics = _compute_metrics(evaluation_rows, use_distilled=False)
    distilled_metrics = _compute_metrics(evaluation_rows, use_distilled=True, bundle=bundle)
    comparison = {
        "eventFamilyDelta": round(distilled_metrics["eventFamilyAccuracy"] - baseline_metrics["eventFamilyAccuracy"], 4),
        "outcomeDelta": round(distilled_metrics["outcomeAccuracy"] - baseline_metrics["outcomeAccuracy"], 4),
        "shotSubtypeDelta": round(distilled_metrics["shotSubtypeAccuracy"] - baseline_metrics["shotSubtypeAccuracy"], 4),
        "uncertaintyDelta": round(distilled_metrics["uncertaintyRate"] - baseline_metrics["uncertaintyRate"], 4),
        "flatLabelSpreadDelta": int(distilled_metrics["flatLabelSpread"] - baseline_metrics["flatLabelSpread"]),
    }
    return evaluation_rows, baseline_metrics, distilled_metrics, comparison


def render_distilled_clip_encoder_report(
    *,
    manifest: dict[str, Any],
    baseline_metrics: dict[str, Any],
    distilled_metrics: dict[str, Any],
    comparison: dict[str, Any],
    evaluation_rows: Sequence[dict[str, Any]],
) -> str:
    lines = [
        "# Distilled Clip Encoder Report",
        "",
        f"- Schema version: `{manifest['schemaVersion']}`",
        f"- Feature version: `{manifest['featureVersion']}`",
        f"- Model version: `{manifest['modelVersion']}`",
        f"- Source dataset: `{manifest['sourceDataset']}`",
        "",
        "## Comparative Metrics",
        f"- Event family accuracy: baseline `{baseline_metrics['eventFamilyAccuracy']}` -> distilled `{distilled_metrics['eventFamilyAccuracy']}`",
        f"- Outcome accuracy: baseline `{baseline_metrics['outcomeAccuracy']}` -> distilled `{distilled_metrics['outcomeAccuracy']}`",
        f"- Shot subtype accuracy: baseline `{baseline_metrics['shotSubtypeAccuracy']}` -> distilled `{distilled_metrics['shotSubtypeAccuracy']}`",
        f"- Uncertainty rate: baseline `{baseline_metrics['uncertaintyRate']}` -> distilled `{distilled_metrics['uncertaintyRate']}`",
        f"- Flat label spread: baseline `{baseline_metrics['flatLabelSpread']}` -> distilled `{distilled_metrics['flatLabelSpread']}`",
        "",
        "## Notes",
    ]
    for note in manifest.get("notes", []):
        lines.append(f"- {note}")
    lines.extend(
        [
            "",
            "## Evaluation Rows",
        ]
    )
    for row in evaluation_rows[:8]:
        lines.append(
            f"- `{row['clipId']}`: baseline `{row['baselineDisplayLabel']}` / distilled `{row['distilledDisplayLabel']}` "
            f"({row['distilledEventFamily']} / {row['distilledOutcome']} / {row['distilledShotSubtype']})"
        )
    lines.extend(
        [
            "",
            "## Comparison",
        ]
    )
    for key, value in comparison.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def build_manifest(
    bundle: DistilledClipEncoderBundle,
    all_examples: Sequence[DistilledClipTrainingExample],
    active_examples: Sequence[DistilledClipTrainingExample],
) -> dict[str, Any]:
    split_counts = Counter(example.split for example in all_examples)
    source_counts = Counter(example.source_kind for example in all_examples)
    label_source_counts = Counter(example.label_source for example in all_examples)
    return {
        "schemaVersion": bundle.schema_version,
        "featureVersion": bundle.feature_version,
        "modelVersion": bundle.model_version,
        "trainedAt": bundle.trained_at,
        "sourceDataset": bundle.source_dataset,
        "notes": list(bundle.notes),
        "labelSpaces": {
            "eventFamily": list(bundle.label_spaces.event_family),
            "outcome": list(bundle.label_spaces.outcome),
            "shotSubtype": list(bundle.label_spaces.shot_subtype),
        },
        "summary": {
            "totalExamples": len(all_examples),
            "activeExamples": len(active_examples),
            "splitCounts": dict(split_counts),
            "sourceCounts": dict(source_counts),
            "labelSourceCounts": dict(label_source_counts),
        },
        "weightPolicy": WEIGHT_POLICY,
    }


def _build_example(
    row: ClipAnnotation,
    *,
    source_kind: str,
    source_set: str,
    source_domain: str,
    teacher_source: str,
) -> DistilledClipTrainingExample:
    raw_runtime = row.rawRuntimeOutputs or {}
    raw_teacher = row.rawTeacherOutputs or {}
    label_source = "human" if row.humanVerified else teacher_source
    resolved_event_family = str(raw_teacher.get("eventFamily") or row.eventFamily)
    resolved_outcome = str(raw_teacher.get("outcome") or row.outcome)
    resolved_shot_subtype = raw_teacher.get("shotSubtype")
    if resolved_shot_subtype is None:
        resolved_shot_subtype = row.shotSubtype
    teacher_confidence = _coerce_optional_float(raw_teacher.get("confidence") or row.teacherConfidence)
    weight = _example_weight(source_kind, teacher_confidence, row.humanVerified)
    ignored = weight <= 0.0
    split = _assign_split(source_kind, row.clipId, row.eventFamily, row.outcome, row.shotSubtype, teacher_confidence)
    feature_snapshot = {
        "sourceKind": source_kind,
        "sourceDomain": source_domain,
        "sourceSet": source_set,
        "humanVerified": row.humanVerified,
        "ballVisible": row.ballVisible,
        "hoopVisible": row.hoopVisible,
        "ballNearRim": row.ballNearRim,
        "ballThroughHoopLikelihood": row.ballThroughHoopLikelihood,
        "possessionChangeLikelihood": row.possessionChangeLikelihood,
        "transitionLikelihood": row.transitionLikelihood,
        "rawRuntimeOutputs": raw_runtime,
        "clipDurationSeconds": _clip_duration_from_runtime(raw_runtime),
        "eventCenterSeconds": _coerce_optional_float(raw_runtime.get("eventCenterSeconds")),
        "preRollSeconds": _coerce_optional_float(raw_runtime.get("preRollSeconds")),
        "postRollSeconds": _coerce_optional_float(raw_runtime.get("postRollSeconds")),
        "sourceEventCount": _coerce_optional_float(raw_runtime.get("sourceEventCount")) or 1.0,
        "wasMerged": bool(raw_runtime.get("wasMerged", False)),
        "rawRuntimeOutputs": raw_runtime,
    }
    features = build_distilled_clip_feature_dict(feature_snapshot)
    return DistilledClipTrainingExample(
        clip_id=row.clipId,
        source_kind=source_kind,
        source_domain=source_domain,
        source_set=source_set,
        split=split,
        weight=weight,
        ignored=ignored,
        event_family=resolved_event_family,
        outcome=resolved_outcome,
        shot_subtype=resolved_shot_subtype if resolved_shot_subtype is None else str(resolved_shot_subtype),
        label_source=label_source,
        teacher_confidence=teacher_confidence,
        human_verified=row.humanVerified,
        raw_runtime_outputs=raw_runtime,
        raw_teacher_outputs=row.rawTeacherOutputs,
        features=features,
    )


def _build_disagreement_example(row: dict[str, Any]) -> DistilledClipTrainingExample:
    gold = row.get("gold", {})
    teacher = row.get("teacher", {})
    runtime = row.get("runtime", {})
    clip_id = str(row.get("clipId"))
    source_domain = str(row.get("sourceDomain") or "disagreement_queue")
    teacher_confidence = _coerce_optional_float(teacher.get("confidence"))
    priority = _coerce_optional_float(row.get("priorityScore"))
    weight = _disagreement_weight(teacher_confidence, priority)
    ignored = weight <= 0.0 or not row.get("sourceRef")
    split = _assign_disagreement_split(clip_id, str(gold.get("eventFamily") or "other"), str(gold.get("outcome") or "uncertain"), gold.get("shotSubtype"), teacher_confidence, priority)
    features = build_distilled_clip_feature_dict(
        {
            "sourceKind": "disagreement",
            "sourceDomain": source_domain,
            "sourceSet": "disagreement_queue",
            "humanVerified": False,
            "ballVisible": row.get("ballVisible"),
            "hoopVisible": row.get("hoopVisible"),
            "ballNearRim": row.get("ballNearRim"),
            "ballThroughHoopLikelihood": row.get("ballThroughHoopLikelihood"),
            "possessionChangeLikelihood": row.get("possessionChangeLikelihood"),
            "transitionLikelihood": row.get("transitionLikelihood"),
            "rawRuntimeOutputs": runtime,
            "clipDurationSeconds": _coerce_optional_float(runtime.get("clipDurationSeconds")),
            "eventCenterSeconds": _coerce_optional_float(runtime.get("eventCenterSeconds")),
            "preRollSeconds": _coerce_optional_float(runtime.get("preRollSeconds")),
            "postRollSeconds": _coerce_optional_float(runtime.get("postRollSeconds")),
            "sourceEventCount": _coerce_optional_float(runtime.get("sourceEventCount")) or 1.0,
            "wasMerged": bool(runtime.get("wasMerged", False)),
            "priorityScore": priority,
        }
    )
    return DistilledClipTrainingExample(
        clip_id=clip_id,
        source_kind="disagreement",
        source_domain=source_domain,
        source_set="disagreement_queue",
        split=split,
        weight=weight,
        ignored=ignored,
        event_family=str(gold.get("eventFamily") or "other"),
        outcome=str(gold.get("outcome") or "uncertain"),
        shot_subtype=None if gold.get("shotSubtype") is None else str(gold.get("shotSubtype")),
        label_source="teacher" if teacher else "runtime",
        teacher_confidence=teacher_confidence,
        human_verified=False,
        raw_runtime_outputs=runtime,
        raw_teacher_outputs=teacher or None,
        features=features,
    )


def _fit_head(
    examples: Sequence[DistilledClipTrainingExample],
    *,
    feature_names: Sequence[str],
    feature_means: Sequence[float],
    feature_scales: Sequence[float],
    labels: Sequence[str],
    target_name: str,
) -> DistilledEncoderHead:
    x = _matrix_from_examples(examples, feature_names, feature_means, feature_scales)
    y = np.zeros((len(examples), len(labels)), dtype=np.float64)
    weights = np.asarray([example.weight for example in examples], dtype=np.float64)
    label_to_index = {label: index for index, label in enumerate(labels)}
    for row_index, example in enumerate(examples):
        label = getattr(example, _target_attr(target_name))
        label = _normalize_shot_subtype(label) if target_name == "shotSubtype" else str(label)
        column = label_to_index.get(label, label_to_index.get("null" if target_name == "shotSubtype" else "uncertain", 0))
        y[row_index, column] = 1.0

    coefficients, intercept = _weighted_ridge_fit(x, y, weights)
    uncertainty_threshold, margin_threshold = _target_thresholds(target_name)
    return DistilledEncoderHead(
        labels=tuple(str(label) for label in labels),
        coefficients=tuple(tuple(float(value) for value in row) for row in coefficients),
        intercept=tuple(float(value) for value in intercept),
        uncertainty_threshold=uncertainty_threshold,
        margin_threshold=margin_threshold,
    )


def _weighted_ridge_fit(
    x: np.ndarray,
    y: np.ndarray,
    sample_weights: np.ndarray,
    *,
    ridge: float = 1e-2,
) -> tuple[np.ndarray, np.ndarray]:
    if x.size == 0:
        raise ValueError("No features available for ridge fit.")
    if x.shape[0] != y.shape[0]:
        raise ValueError("Feature and target row counts must match.")
    weights = np.clip(np.asarray(sample_weights, dtype=np.float64), 0.0, None)
    if not np.any(weights):
        weights = np.ones_like(weights)
    x_aug = np.concatenate([x, np.ones((x.shape[0], 1), dtype=np.float64)], axis=1)
    sw = np.sqrt(weights)[:, None]
    xw = x_aug * sw
    yw = y * sw
    identity = np.eye(xw.shape[1], dtype=np.float64)
    identity[-1, -1] = 0.0
    lhs = xw.T @ xw + ridge * identity
    rhs = xw.T @ yw
    solution = np.linalg.solve(lhs, rhs)
    return solution[:-1, :], solution[-1, :]


def _target_thresholds(target_name: str) -> tuple[float, float]:
    if target_name == "eventFamily":
        return 0.34, 0.08
    if target_name == "outcome":
        return 0.36, 0.08
    if target_name == "shotSubtype":
        return 0.28, 0.05
    return 0.4, 0.08


def _matrix_from_examples(
    examples: Sequence[DistilledClipTrainingExample],
    feature_names: Sequence[str],
    feature_means: Sequence[float],
    feature_scales: Sequence[float],
) -> np.ndarray:
    name_to_index = {name: index for index, name in enumerate(feature_names)}
    means = np.asarray(feature_means, dtype=np.float64)
    scales = np.asarray(feature_scales, dtype=np.float64)
    matrix = np.zeros((len(examples), len(feature_names)), dtype=np.float64)
    for row_index, example in enumerate(examples):
        for name, value in example.features.items():
            column = name_to_index.get(name)
            if column is None:
                continue
            matrix[row_index, column] = float(value)
    return (matrix - means) / scales


def _fit_feature_normalizer(
    examples: Sequence[DistilledClipTrainingExample],
    feature_names: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.zeros((len(examples), len(feature_names)), dtype=np.float64)
    name_to_index = {name: index for index, name in enumerate(feature_names)}
    for row_index, example in enumerate(examples):
        for name, value in example.features.items():
            column = name_to_index.get(name)
            if column is None:
                continue
            matrix[row_index, column] = float(value)
    means = np.mean(matrix, axis=0)
    scales = np.std(matrix, axis=0)
    scales = np.where(scales < 1e-6, 1.0, scales)
    return means, scales


def _collect_feature_names(examples: Sequence[DistilledClipTrainingExample]) -> list[str]:
    names = sorted({name for example in examples for name in example.features})
    return names


def _example_weight(source_kind: str, teacher_confidence: float | None, human_verified: bool) -> float:
    if human_verified or source_kind == "gold":
        return WEIGHT_POLICY["gold"]
    if source_kind == "silver":
        confidence = teacher_confidence or 0.0
        if confidence < 0.75:
            return WEIGHT_POLICY["silverLowConfidence"]
        if confidence >= 0.9:
            return WEIGHT_POLICY["silverHighConfidence"]
        return WEIGHT_POLICY["silverMediumConfidence"]
    return 1.0


def _disagreement_weight(teacher_confidence: float | None, priority_score: float | None) -> float:
    confidence = teacher_confidence or 0.0
    priority = priority_score or 0.5
    base = WEIGHT_POLICY["disagreementBase"] + 0.4 * confidence + 0.4 * priority
    return float(min(WEIGHT_POLICY["disagreementMax"], round(base, 2)))


def _assign_split(
    source_kind: str,
    clip_id: str,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
    teacher_confidence: float | None,
) -> str:
    bucket = _stable_bucket(f"{source_kind}:{clip_id}:{event_family}:{outcome}:{shot_subtype or 'null'}")
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
    return "train"


def _assign_disagreement_split(
    clip_id: str,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
    teacher_confidence: float | None,
    priority_score: float | None,
) -> str:
    bucket = _stable_bucket(f"disagreement:{clip_id}:{event_family}:{outcome}:{shot_subtype or 'null'}")
    priority = priority_score or 0.0
    if priority >= 0.8:
        return "train" if bucket % 10 < 8 else "val"
    if teacher_confidence and teacher_confidence >= 0.9:
        return "train"
    return "train" if bucket % 10 < 9 else "test"


def _stable_bucket(value: str) -> int:
    return int(hashlib.sha1(value.encode("utf-8")).hexdigest(), 16)


def _compute_metrics(
    evaluation_rows: Sequence[dict[str, Any]],
    *,
    use_distilled: bool,
    bundle: DistilledClipEncoderBundle | None = None,
) -> dict[str, Any]:
    event_family_correct = 0
    outcome_correct = 0
    subtype_correct = 0
    uncertain = 0
    flat_labels: Counter[str] = Counter()
    family_confusions: Counter[tuple[str, str]] = Counter()
    outcome_confusions: Counter[tuple[str, str]] = Counter()
    subtype_confusions: Counter[tuple[str, str]] = Counter()

    for row in evaluation_rows:
        if use_distilled:
            assert bundle is not None
            prediction = bundle.predict_from_snapshot(row)
            event_family = prediction.event_family
            outcome = prediction.outcome
            shot_subtype = prediction.shot_subtype
            display_label = prediction.display_label
            is_uncertain = prediction.is_uncertain
        else:
            event_family = str(row["baselineEventFamily"])
            outcome = str(row["baselineOutcome"])
            shot_subtype = row["baselineShotSubtype"]
            display_label = str(row["baselineDisplayLabel"])
            is_uncertain = bool(row["baselineUncertain"])
        flat_labels[display_label] += 1
        family_confusions[(str(row["goldEventFamily"]), event_family)] += 1
        outcome_confusions[(str(row["goldOutcome"]), outcome)] += 1
        subtype_confusions[(str(row["goldShotSubtype"]), str(shot_subtype or "null"))] += 1
        event_family_correct += int(event_family == row["goldEventFamily"])
        outcome_correct += int(outcome == row["goldOutcome"])
        subtype_correct += int(_normalize_shot_subtype(shot_subtype) == _normalize_shot_subtype(row["goldShotSubtype"]))
        uncertain += int(is_uncertain)

    total = max(len(evaluation_rows), 1)
    return {
        "sampleCount": len(evaluation_rows),
        "eventFamilyAccuracy": round(event_family_correct / total, 4),
        "outcomeAccuracy": round(outcome_correct / total, 4),
        "shotSubtypeAccuracy": round(subtype_correct / total, 4),
        "uncertaintyRate": round(uncertain / total, 4),
        "flatLabelSpread": len(flat_labels),
        "flatLabelDistribution": dict(flat_labels),
        "familyConfusions": _top_confusions(family_confusions),
        "outcomeConfusions": _top_confusions(outcome_confusions),
        "shotSubtypeConfusions": _top_confusions(subtype_confusions),
    }


def _example_to_row(example: DistilledClipTrainingExample, bundle: DistilledClipEncoderBundle) -> dict[str, Any]:
    snapshot = {
        "sourceKind": example.source_kind,
        "sourceDomain": example.source_domain,
        "sourceSet": example.source_set,
        "humanVerified": example.human_verified,
        "ballVisible": example.features.get("ballVisible", 0.0) > 0.5,
        "hoopVisible": example.features.get("hoopVisible", 0.0) > 0.5,
        "ballNearRim": example.features.get("ballNearRim"),
        "ballThroughHoopLikelihood": example.features.get("ballThroughHoopLikelihood"),
        "possessionChangeLikelihood": example.features.get("possessionChangeLikelihood"),
        "transitionLikelihood": example.features.get("transitionLikelihood"),
        "clipDurationSeconds": example.features.get("clipDurationSeconds"),
        "eventCenterSeconds": example.features.get("eventCenterSeconds"),
        "preRollSeconds": example.features.get("preRollSeconds"),
        "postRollSeconds": example.features.get("postRollSeconds"),
        "sourceEventCount": example.features.get("sourceEventCount"),
        "wasMerged": example.features.get("wasMerged", 0.0) > 0.5,
        "rawRuntimeOutputs": example.raw_runtime_outputs,
    }
    distilled = bundle.predict_from_snapshot(snapshot)
    baseline_event_family = str(example.raw_runtime_outputs.get("eventFamily") or example.event_family)
    baseline_outcome = str(example.raw_runtime_outputs.get("outcome") or example.outcome)
    baseline_shot_subtype = example.raw_runtime_outputs.get("shotSubtype") or example.shot_subtype
    baseline_display_label = derive_display_label(
        baseline_event_family,
        baseline_outcome,
        baseline_shot_subtype if baseline_shot_subtype is None else str(baseline_shot_subtype),
    )[1]
    return {
        "clipId": example.clip_id,
        "goldEventFamily": example.event_family,
        "goldOutcome": example.outcome,
        "goldShotSubtype": example.shot_subtype,
        "baselineEventFamily": baseline_event_family,
        "baselineOutcome": baseline_outcome,
        "baselineShotSubtype": baseline_shot_subtype,
        "baselineDisplayLabel": baseline_display_label,
        "baselineUncertain": baseline_display_label == "Highlight" or baseline_outcome == "uncertain",
        "distilledEventFamily": distilled.event_family,
        "distilledOutcome": distilled.outcome,
        "distilledShotSubtype": distilled.shot_subtype,
        "distilledDisplayLabel": distilled.display_label,
        "distilledUncertain": distilled.is_uncertain,
        "distilledConfidence": distilled.confidence_after_mapping,
        "sourceKind": example.source_kind,
        "sourceDomain": example.source_domain,
        "sourceSet": example.source_set,
        "weight": example.weight,
        "split": example.split,
        "rawRuntimeOutputs": example.raw_runtime_outputs,
        "rawTeacherOutputs": example.raw_teacher_outputs,
        "features": example.features,
    }


def _top_confusions(counter: Counter[tuple[str, str]], *, limit: int = 6) -> list[dict[str, Any]]:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    return [
        {"gold": gold, "predicted": predicted, "count": count}
        for (gold, predicted), count in items[:limit]
    ]


def _target_attr(target_name: str) -> str:
    if target_name == "eventFamily":
        return "event_family"
    if target_name == "outcome":
        return "outcome"
    if target_name == "shotSubtype":
        return "shot_subtype"
    raise ValueError(f"Unsupported target: {target_name}")


def _clip_duration_from_runtime(raw_runtime: dict[str, Any]) -> float | None:
    duration = raw_runtime.get("clipDurationSeconds")
    if duration is None:
        return None
    return _coerce_optional_float(duration)


def _normalize_shot_subtype(value: Any) -> str:
    if value is None or value == "":
        return "null"
    text = str(value).strip().lower().replace(" ", "_")
    return text


def _normalize_label(value: Any) -> str:
    if value is None:
        return "null"
    return str(value).strip().lower().replace(" ", "_")


def _ordered_unique(items: Iterable[Any]) -> tuple[str, ...]:
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
    return tuple(ordered)


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows

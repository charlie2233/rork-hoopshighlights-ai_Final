from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Sequence

from services.inference.app.distilled_clip_encoder import (
    DistilledClipEncoderBundle,
    DistilledClipLabelSpaces,
    DistilledEncoderHead,
    EVENT_FAMILY_LABELS,
    OUTCOME_LABELS,
    SHOT_SUBTYPE_LABELS,
    build_distilled_clip_feature_dict,
    derive_display_label,
)
from services.inference.datasets.annotations import ClipAnnotation, load_annotation_rows
from services.inference.training.distilled_clip_encoder import (
    DistilledClipTrainingExample,
    _coerce_optional_float,
    _compute_metrics,
    _fit_feature_normalizer,
    _fit_head,
    _load_jsonl,
    _normalize_shot_subtype,
    _ordered_unique,
    _top_confusions,
    _target_attr,
    load_distilled_clip_examples,
)
from services.inference.training.hard_negative_mining import hard_example_multiplier, hard_example_signal


TEACHER_DISTILLED_STUDENT_SCHEMA_VERSION = "teacher-distilled-clip-student-v1"
TEACHER_DISTILLED_STUDENT_FEATURE_VERSION = "teacher-distilled-clip-features-v1"
TEACHER_DISTILLED_STUDENT_MODEL_VERSION = "teacher-distilled-clip-student-v1"
TEACHER_DISTILLED_STUDENT_SOURCE_DATASET = (
    "services/inference/datasets/gold_set.json + silver_set.json + disagreement_queue.jsonl + offline_teacher"
)


@dataclass(frozen=True)
class TeacherDistilledStudentResult:
    bundle: DistilledClipEncoderBundle
    manifest: dict[str, Any]
    baseline_metrics: dict[str, Any]
    distilled_metrics: dict[str, Any]
    comparison: dict[str, Any]
    evaluation_rows: tuple[dict[str, Any], ...]


def build_teacher_distilled_student_bundle(
    repo_root: Path,
    output_dir: Path | None = None,
) -> TeacherDistilledStudentResult:
    examples = load_teacher_distilled_examples(repo_root)
    bundle, manifest = fit_teacher_distilled_student(examples)
    evaluation_rows, baseline_metrics, distilled_metrics, comparison = evaluate_teacher_distilled_student(bundle, examples)

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "bundle.json").write_text(json.dumps(bundle.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        (output_dir / "report.md").write_text(
            render_teacher_distilled_student_report(
                manifest=manifest,
                baseline_metrics=baseline_metrics,
                distilled_metrics=distilled_metrics,
                comparison=comparison,
                evaluation_rows=evaluation_rows,
            ),
            encoding="utf-8",
        )

    return TeacherDistilledStudentResult(
        bundle=bundle,
        manifest=manifest,
        baseline_metrics=baseline_metrics,
        distilled_metrics=distilled_metrics,
        comparison=comparison,
        evaluation_rows=tuple(evaluation_rows),
    )


def load_teacher_distilled_examples(repo_root: Path) -> list[DistilledClipTrainingExample]:
    base_examples = load_distilled_clip_examples(repo_root)
    return [
        _augment_example(example)
        for example in base_examples
    ]


def fit_teacher_distilled_student(
    examples: Sequence[DistilledClipTrainingExample],
) -> tuple[DistilledClipEncoderBundle, dict[str, Any]]:
    active_examples = [example for example in examples if not example.ignored and example.weight > 0.0]
    if not active_examples:
        raise ValueError("No active examples available for teacher-distilled student training.")

    feature_names = _collect_feature_names(active_examples)
    feature_means, feature_scales = _fit_feature_normalizer(active_examples, feature_names)
    label_spaces = DistilledClipLabelSpaces(
        event_family=_ordered_unique([example.event_family for example in active_examples] + list(EVENT_FAMILY_LABELS)),
        outcome=_ordered_unique([example.outcome for example in active_examples] + list(OUTCOME_LABELS)),
        shot_subtype=_ordered_unique([
            _normalize_shot_subtype(example.shot_subtype) for example in active_examples
        ] + list(SHOT_SUBTYPE_LABELS)),
    )

    heads: dict[str, DistilledEncoderHead] = {}
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
        schema_version=TEACHER_DISTILLED_STUDENT_SCHEMA_VERSION,
        feature_version=TEACHER_DISTILLED_STUDENT_FEATURE_VERSION,
        model_version=TEACHER_DISTILLED_STUDENT_MODEL_VERSION,
        trained_at=datetime.now(timezone.utc).isoformat(),
        source_dataset=TEACHER_DISTILLED_STUDENT_SOURCE_DATASET,
        notes=(
            "Teacher outputs remain offline/training-only.",
            "Gold rows anchor calibration and evaluation.",
            "Silver rows are weighted by teacher confidence and pseudo-label eligibility.",
            "Disagreement rows with strong teacher support are retained as hard examples.",
            "Candidate-window duration and teacher evidence are explicit student features.",
        ),
        label_spaces=label_spaces,
        feature_names=tuple(feature_names),
        feature_means=tuple(feature_means),
        feature_scales=tuple(feature_scales),
        heads=heads,
    )
    manifest = build_manifest(bundle, examples, active_examples)
    return bundle, manifest


def evaluate_teacher_distilled_student(
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


def render_teacher_distilled_student_report(
    *,
    manifest: dict[str, Any],
    baseline_metrics: dict[str, Any],
    distilled_metrics: dict[str, Any],
    comparison: dict[str, Any],
    evaluation_rows: Sequence[dict[str, Any]],
) -> str:
    lines = [
        "# Teacher-Distilled Student Report",
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
    lines.extend(["", "## Evaluation Rows"])
    for row in evaluation_rows[:8]:
        lines.append(
            f"- `{row['clipId']}`: baseline `{row['baselineDisplayLabel']}` / distilled `{row['distilledDisplayLabel']}` "
            f"({row['distilledEventFamily']} / {row['distilledOutcome']} / {row['distilledShotSubtype']})"
        )
    lines.extend(["", "## Comparison"])
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
    total_weight = round(sum(example.weight for example in all_examples), 4)
    active_weight = round(sum(example.weight for example in active_examples), 4)
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
            "totalWeight": total_weight,
            "activeWeight": active_weight,
            "splitCounts": dict(split_counts),
            "sourceCounts": dict(source_counts),
            "labelSourceCounts": dict(label_source_counts),
        },
    }


def _augment_example(example: DistilledClipTrainingExample) -> DistilledClipTrainingExample:
    raw_teacher = example.raw_teacher_outputs or {}
    pseudo_label = raw_teacher.get("pseudoLabel") or {}
    evidence = raw_teacher.get("evidence") or {}
    structured = evidence.get("structuredSignals") or {}
    perception = evidence.get("perceptionSummary") or {}
    runtime = dict(example.raw_runtime_outputs or {})
    teacher_confidence = _coerce_optional_float(raw_teacher.get("teacherConfidence") or raw_teacher.get("confidence"))
    teacher_evidence_strength = _teacher_evidence_strength(structured, perception)
    hard_example_weight = hard_example_multiplier(
        source_kind=example.source_kind,
        source_domain=example.source_domain,
        teacher_confidence=teacher_confidence,
        reasons=raw_teacher.get("reasons") or raw_teacher.get("priorityReasons") or (),
        base_multiplier=0.35,
    )
    candidate_snapshot = {
        **example.features,
        "candidateWindowDurationSeconds": _coerce_optional_float(runtime.get("clipDurationSeconds")) or 0.0,
        "candidateWindowCenterSeconds": _coerce_optional_float(runtime.get("eventCenterSeconds")) or 0.0,
        "candidateWindowPreRollSeconds": _coerce_optional_float(runtime.get("preRollSeconds")) or 0.0,
        "candidateWindowPostRollSeconds": _coerce_optional_float(runtime.get("postRollSeconds")) or 0.0,
        "candidateWindowSourceEventCount": _coerce_optional_float(runtime.get("sourceEventCount")) or 1.0,
        "candidateWindowMerged": 1.0 if runtime.get("wasMerged") else 0.0,
        "teacherConfidence": teacher_confidence or 0.0,
        "teacherPseudoLabelEligible": 1.0 if pseudo_label.get("eligible") else 0.0,
        "teacherEvidenceStrength": teacher_evidence_strength,
        "teacherEvidenceBallVisible": 1.0 if perception.get("ballVisible") else 0.0,
        "teacherEvidenceHoopVisible": 1.0 if perception.get("hoopVisible") else 0.0,
        "teacherEvidenceBallNearRim": _coerce_optional_float(structured.get("ballNearRim")) or 0.0,
        "teacherEvidenceBallThroughHoopLikelihood": _coerce_optional_float(structured.get("ballThroughHoopLikelihood")) or 0.0,
        "teacherEvidencePossessionChangeLikelihood": _coerce_optional_float(structured.get("possessionChangeLikelihood")) or 0.0,
        "teacherEvidenceTransitionLikelihood": _coerce_optional_float(structured.get("transitionLikelihood")) or 0.0,
        "teacherNotesLength": float(len(str(raw_teacher.get("notes") or ""))),
    }
    features = build_distilled_clip_feature_dict(
        {
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
            "clipDurationSeconds": candidate_snapshot["candidateWindowDurationSeconds"],
            "eventCenterSeconds": candidate_snapshot["candidateWindowCenterSeconds"],
            "preRollSeconds": candidate_snapshot["candidateWindowPreRollSeconds"],
            "postRollSeconds": candidate_snapshot["candidateWindowPostRollSeconds"],
            "sourceEventCount": candidate_snapshot["candidateWindowSourceEventCount"],
            "wasMerged": bool(runtime.get("wasMerged", False)),
            "priorityScore": example.features.get("priorityScore"),
            "rawRuntimeOutputs": runtime,
            "rawTeacherOutputs": raw_teacher,
            "structuredSignals": {
                "ballNearRim": example.features.get("ballNearRim", 0.0),
                "ballThroughHoopLikelihood": example.features.get("ballThroughHoopLikelihood", 0.0),
                "possessionChangeLikelihood": example.features.get("possessionChangeLikelihood", 0.0),
                "transitionLikelihood": example.features.get("transitionLikelihood", 0.0),
            },
            **candidate_snapshot,
        }
    )
    return replace(example, weight=round(example.weight * hard_example_weight, 4), features=features)


def _teacher_evidence_strength(structured: dict[str, Any], perception: dict[str, Any]) -> float:
    ball_visible = 1.0 if perception.get("ballVisible") else 0.0
    hoop_visible = 1.0 if perception.get("hoopVisible") else 0.0
    support = [
        ball_visible,
        hoop_visible,
        _coerce_optional_float(structured.get("ballNearRim")) or 0.0,
        _coerce_optional_float(structured.get("ballThroughHoopLikelihood")) or 0.0,
        _coerce_optional_float(structured.get("possessionChangeLikelihood")) or 0.0,
        _coerce_optional_float(structured.get("transitionLikelihood")) or 0.0,
    ]
    return round(sum(support) / max(len(support), 1), 4)


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
        "clipDurationSeconds": example.features.get("candidateWindowDurationSeconds") or example.features.get("clipDurationSeconds"),
        "eventCenterSeconds": example.features.get("candidateWindowCenterSeconds") or example.features.get("eventCenterSeconds"),
        "preRollSeconds": example.features.get("candidateWindowPreRollSeconds") or example.features.get("preRollSeconds"),
        "postRollSeconds": example.features.get("candidateWindowPostRollSeconds") or example.features.get("postRollSeconds"),
        "sourceEventCount": example.features.get("candidateWindowSourceEventCount") or example.features.get("sourceEventCount"),
        "wasMerged": example.features.get("candidateWindowMerged", 0.0) > 0.5,
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


def _collect_feature_names(examples: Sequence[DistilledClipTrainingExample]) -> list[str]:
    return sorted({name for example in examples for name in example.features})

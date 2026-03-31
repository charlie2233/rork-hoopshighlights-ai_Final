from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from hashlib import sha1
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from services.inference.app.runtime_model import derive_runtime_display_label
from services.inference.app.runtime_models.temporal_student import (
    EVENT_FAMILIES,
    OUTCOMES,
    SHOT_SUBTYPES,
    TEMPORAL_STUDENT_FEATURE_SCHEMA_VERSION,
    TEMPORAL_STUDENT_MODEL_VERSION,
    TEMPORAL_STUDENT_SCHEMA_VERSION,
    TemporalStudentBundle,
    TemporalStudentObservation,
    TemporalStudentTargetPrediction,
    build_temporal_student_feature_map,
    default_temporal_student_feature_names,
    write_temporal_student_bundle,
)
from services.inference.datasets.annotations import ClipAnnotation, load_annotation_rows
from services.inference.datasets.runtime_training import example_weight
from services.inference.training.hard_negative_mining import hard_example_multiplier, hard_example_signal

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover - exercised only in non-ML environments
    torch = None
    nn = None
    F = None


TEMPORAL_STUDENT_OUTPUT_DIR_NAME = "temporal_student"


@dataclass(frozen=True)
class TemporalStudentTrainingExample:
    clip_id: str
    observations: tuple[TemporalStudentObservation, ...]
    event_family: str
    outcome: str
    shot_subtype: str | None
    source_kind: str = "unknown"
    source_domain: str = "unknown"
    split: str = "train"
    weight: float = 1.0
    teacher_confidence: float | None = None
    human_verified: bool = False
    raw_runtime_outputs: dict[str, Any] | None = None
    raw_teacher_outputs: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "clipId": self.clip_id,
            "sourceKind": self.source_kind,
            "sourceDomain": self.source_domain,
            "split": self.split,
            "weight": round(self.weight, 4),
            "eventFamily": self.event_family,
            "outcome": self.outcome,
            "shotSubtype": self.shot_subtype,
            "teacherConfidence": self.teacher_confidence,
            "humanVerified": self.human_verified,
            "rawRuntimeOutputs": self.raw_runtime_outputs,
            "rawTeacherOutputs": self.raw_teacher_outputs,
            "observations": [
                {
                    "timestampSeconds": observation.timestamp_seconds,
                    "structuredSignals": dict(observation.structured_signals),
                    "perceptionFeatures": dict(observation.perception_features),
                    "detectionFeatures": dict(observation.detection_features),
                    "trackingFeatures": dict(observation.tracking_features),
                    "runtimeFeatures": dict(observation.runtime_features),
                }
                for observation in self.observations
            ],
        }


@dataclass(frozen=True)
class TemporalStudentTrainingResult:
    bundle: TemporalStudentBundle
    metrics: dict[str, Any]
    training_examples: int


def load_temporal_student_examples(repo_root: Path) -> list[TemporalStudentTrainingExample]:
    dataset_dir = repo_root / "services" / "inference" / "datasets"
    rows = [
        *_load_annotation_rows(dataset_dir / "gold_set.json", source_set="gold_set"),
        *_load_annotation_rows(dataset_dir / "silver_set.json", source_set="silver_set"),
        *_load_jsonl_rows(dataset_dir / "disagreement_queue.jsonl", source_set="disagreement_queue"),
    ]
    examples = [
        TemporalStudentTrainingExample(
            clip_id=row.clipId,
            observations=_synthesize_temporal_student_observations(row),
            event_family=row.eventFamily,
            outcome=row.outcome,
            shot_subtype=row.shotSubtype,
            source_kind=row.sourceKind,
            source_domain=row.sourceDomain,
            split=_assign_temporal_split(row.clipId, row.sourceKind),
            weight=_example_weight(row),
            teacher_confidence=row.teacherConfidence,
            human_verified=row.humanVerified,
            raw_runtime_outputs=dict(row.rawRuntimeOutputs or {}),
            raw_teacher_outputs=dict(row.rawTeacherOutputs or {}) or None,
        )
        for row in rows
    ]
    return _promote_missing_classes(examples)


def train_temporal_student_from_repo(
    repo_root: Path,
    *,
    output_path: Path | None = None,
    hidden_size: int = 16,
    epochs: int = 120,
    learning_rate: float = 0.03,
) -> TemporalStudentTrainingResult:
    examples = load_temporal_student_examples(repo_root)
    result = train_temporal_student(
        examples,
        hidden_size=hidden_size,
        epochs=epochs,
        learning_rate=learning_rate,
    )
    if output_path is not None:
        write_temporal_student_bundle(output_path, result.bundle)
    return result


def train_temporal_student(
    examples: Sequence[TemporalStudentTrainingExample],
    *,
    hidden_size: int = 16,
    epochs: int = 120,
    learning_rate: float = 0.03,
) -> TemporalStudentTrainingResult:
    if torch is None or nn is None or F is None:  # pragma: no cover - depends on torch availability
        raise RuntimeError("torch is required to train the temporal student")
    if not examples:
        raise ValueError("At least one training example is required.")

    input_feature_names = default_temporal_student_feature_names()
    label_spaces = {
        "eventFamily": EVENT_FAMILIES,
        "outcome": OUTCOMES,
        "shotSubtype": SHOT_SUBTYPES,
    }
    dataset = build_training_tensors(examples, input_feature_names=input_feature_names)
    model = TorchTemporalStudent(len(input_feature_names), hidden_size, label_spaces)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    for _ in range(epochs):
        optimizer.zero_grad()
        logits, _ = model(dataset["inputs"])
        loss = compute_temporal_student_loss(
            logits=logits,
            targets=dataset["targets"],
            weights=dataset["weights"],
            shot_mask=dataset["shot_mask"],
        )
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits, _ = model(dataset["inputs"])
        metrics = compute_temporal_student_metrics(logits=logits, dataset=dataset, label_spaces=label_spaces)
    bundle = export_temporal_student_bundle(
        model=model,
        input_feature_names=input_feature_names,
        label_spaces=label_spaces,
        source_dataset="gold_silver_disagreement_temporal_student",
    )
    return TemporalStudentTrainingResult(
        bundle=bundle,
        metrics=metrics,
        training_examples=len(examples),
    )


def evaluate_temporal_student_bundle(
    bundle: TemporalStudentBundle,
    examples: Sequence[TemporalStudentTrainingExample],
) -> dict[str, Any]:
    evaluation_examples = [
        example
        for example in examples
        if example.source_kind == "gold" and example.split in {"val", "test"}
    ]
    if not evaluation_examples:
        evaluation_examples = [example for example in examples if example.source_kind == "gold"] or list(examples)

    rows: list[dict[str, Any]] = []
    for example in evaluation_examples:
        prediction = bundle.predict(example.observations)
        rows.append(
            {
                "clipId": example.clip_id,
                "sourceKind": example.source_kind,
                "sourceDomain": example.source_domain,
                "expectedEventFamily": example.event_family,
                "expectedOutcome": example.outcome,
                "expectedShotSubtype": example.shot_subtype or "null",
                "predictedEventFamily": prediction.eventFamily or "other",
                "predictedOutcome": prediction.outcome or "uncertain",
                "predictedShotSubtype": prediction.shotSubtype or "null",
                "predictedDisplayLabel": prediction.label,
                "isUncertain": bool(prediction.isUncertain),
            }
        )

    total = max(len(rows), 1)
    event_family_accuracy = round(
        sum(1 for row in rows if row["expectedEventFamily"] == row["predictedEventFamily"]) / total,
        4,
    )
    outcome_accuracy = round(
        sum(1 for row in rows if row["expectedOutcome"] == row["predictedOutcome"]) / total,
        4,
    )
    subtype_rows = [row for row in rows if row["expectedEventFamily"] == "shot_attempt"]
    subtype_total = max(len(subtype_rows), 1)
    shot_subtype_accuracy = round(
        sum(1 for row in subtype_rows if row["expectedShotSubtype"] == row["predictedShotSubtype"]) / subtype_total,
        4,
    )
    uncertainty_rate = round(sum(1 for row in rows if row["isUncertain"]) / total, 4)
    display_label_distribution = dict(sorted(Counter(row["predictedDisplayLabel"] for row in rows).items()))
    event_family_distribution = dict(sorted(Counter(row["predictedEventFamily"] for row in rows).items()))
    outcome_distribution = dict(sorted(Counter(row["predictedOutcome"] for row in rows).items()))
    subtype_distribution = dict(sorted(Counter(row["predictedShotSubtype"] for row in rows).items()))
    miss_vs_made_confusion = {
        "missedPredictedAsMadeShot": sum(
            1
            for row in rows
            if row["expectedOutcome"] == "missed" and row["predictedDisplayLabel"] == "Made Shot"
        ),
        "madePredictedAsHighlight": sum(
            1
            for row in rows
            if row["expectedOutcome"] == "made" and row["predictedDisplayLabel"] == "Highlight"
        ),
    }
    return {
        "eventFamilyAccuracy": event_family_accuracy,
        "outcomeAccuracy": outcome_accuracy,
        "shotSubtypeAccuracy": shot_subtype_accuracy,
        "uncertaintyRate": uncertainty_rate,
        "flatLabelSpread": len(display_label_distribution),
        "highlightDominance": round(display_label_distribution.get("Highlight", 0) / total, 4),
        "otherDominance": round(event_family_distribution.get("other", 0) / total, 4),
        "displayLabelDistribution": display_label_distribution,
        "eventFamilyDistribution": event_family_distribution,
        "outcomeDistribution": outcome_distribution,
        "shotSubtypeDistribution": subtype_distribution,
        "missVsMadeConfusion": miss_vs_made_confusion,
        "sourceDomainSplit": dict(sorted(Counter(row["sourceDomain"] for row in rows).items())),
        "evaluationRows": rows,
    }


def render_temporal_student_report(
    *,
    metrics: dict[str, Any],
    evaluation_rows: Sequence[dict[str, Any]],
) -> str:
    lines = [
        "# Temporal Student Report",
        "",
        f"- eventFamilyAccuracy: `{metrics['eventFamilyAccuracy']}`",
        f"- outcomeAccuracy: `{metrics['outcomeAccuracy']}`",
        f"- shotSubtypeAccuracy: `{metrics['shotSubtypeAccuracy']}`",
        f"- uncertaintyRate: `{metrics['uncertaintyRate']}`",
        f"- flatLabelSpread: `{metrics['flatLabelSpread']}`",
        f"- highlightDominance: `{metrics['highlightDominance']}`",
        f"- otherDominance: `{metrics['otherDominance']}`",
        "",
        "## Distributions",
        f"- display labels: `{metrics['displayLabelDistribution']}`",
        f"- event families: `{metrics['eventFamilyDistribution']}`",
        f"- outcomes: `{metrics['outcomeDistribution']}`",
        f"- shot subtypes: `{metrics['shotSubtypeDistribution']}`",
        "",
        "## Miss vs Made Confusion",
        f"- `{metrics['missVsMadeConfusion']}`",
        "",
        "## Sample Rows",
    ]
    for row in evaluation_rows[:8]:
        lines.append(
            f"- `{row['clipId']}`: predicted `{row['predictedDisplayLabel']}` "
            f"({row['predictedEventFamily']} / {row['predictedOutcome']} / {row['predictedShotSubtype']})"
        )
    return "\n".join(lines) + "\n"


def build_training_tensors(
    examples: Sequence[TemporalStudentTrainingExample],
    *,
    input_feature_names: Sequence[str],
) -> dict[str, Any]:
    if torch is None:  # pragma: no cover - depends on torch availability
        raise RuntimeError("torch is required to build training tensors")
    sequence_lengths = [len(example.observations) for example in examples]
    if len(set(sequence_lengths)) != 1:
        raise ValueError("Temporal student training examples must be padded to equal length before training.")
    inputs = torch.tensor(
        [
            [
                [float(build_temporal_student_feature_map(observation).get(name, 0.0)) for name in input_feature_names]
                for observation in example.observations
            ]
            for example in examples
        ],
        dtype=torch.float32,
    )
    targets = {
        "eventFamily": torch.tensor([EVENT_FAMILIES.index(example.event_family) for example in examples], dtype=torch.long),
        "outcome": torch.tensor([OUTCOMES.index(example.outcome) for example in examples], dtype=torch.long),
        "shotSubtype": torch.tensor(
            [SHOT_SUBTYPES.index(example.shot_subtype or "null") for example in examples],
            dtype=torch.long,
        ),
    }
    weights = torch.tensor([float(max(example.weight, 0.0)) for example in examples], dtype=torch.float32)
    shot_mask = torch.tensor([1.0 if example.event_family == "shot_attempt" else 0.0 for example in examples], dtype=torch.float32)
    return {
        "inputs": inputs,
        "targets": targets,
        "weights": weights,
        "shot_mask": shot_mask,
    }


def compute_temporal_student_loss(
    *,
    logits: dict[str, Any],
    targets: dict[str, Any],
    weights: Any,
    shot_mask: Any,
) -> Any:
    if F is None:  # pragma: no cover - depends on torch availability
        raise RuntimeError("torch is required to compute temporal student loss")
    family_loss = F.cross_entropy(logits["eventFamily"], targets["eventFamily"], reduction="none")
    outcome_loss = F.cross_entropy(logits["outcome"], targets["outcome"], reduction="none")
    subtype_loss = F.cross_entropy(logits["shotSubtype"], targets["shotSubtype"], reduction="none") * shot_mask
    combined = (1.25 * family_loss + 1.0 * outcome_loss + 0.85 * subtype_loss) * weights
    normalizer = max(float(torch.sum(weights).item()), 1e-6)
    return torch.sum(combined) / normalizer


def compute_temporal_student_metrics(
    *,
    logits: dict[str, Any],
    dataset: dict[str, Any],
    label_spaces: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for target_name, classes in label_spaces.items():
        prediction = torch.argmax(logits[target_name], dim=1)
        targets = dataset["targets"][target_name]
        if target_name == "shotSubtype":
            mask = dataset["shot_mask"] > 0
            correct = torch.sum((prediction[mask] == targets[mask]).float()).item() if torch.any(mask) else 0.0
            total = int(torch.sum(mask).item())
        else:
            correct = torch.sum((prediction == targets).float()).item()
            total = int(targets.shape[0])
        metrics[target_name] = {
            "accuracy": round(correct / max(total, 1), 4),
            "classes": list(classes),
        }
    return metrics


def build_target_model(
    *,
    name: str,
    classes: Sequence[str],
    weight: np.ndarray,
    bias: np.ndarray,
    top_k: int,
) -> Any:
    from services.inference.app.temporal_encoder import TemporalTargetModel

    return TemporalTargetModel(
        name=name,
        classes=tuple(str(item) for item in classes),
        weight=_to_nested_tuple(weight),
        bias=tuple(float(value) for value in bias.tolist()),
        temperature=1.0,
        uncertainty_threshold=0.45,
        margin_threshold=0.05,
        top_k=top_k,
    )


def export_temporal_student_bundle(
    *,
    model: Any,
    input_feature_names: Sequence[str],
    label_spaces: dict[str, tuple[str, ...]],
    source_dataset: str,
    model_version: str = TEMPORAL_STUDENT_MODEL_VERSION,
) -> TemporalStudentBundle:
    if torch is None:  # pragma: no cover - depends on torch availability
        raise RuntimeError("torch is required to export the temporal student bundle")
    projection_weight = _to_nested_tuple(model.projection.weight.detach().cpu().numpy())
    projection_bias = tuple(float(value) for value in model.projection.bias.detach().cpu().numpy().tolist())
    attention_weight = tuple(float(value) for value in model.attention.weight.detach().cpu().numpy().reshape(-1).tolist())
    attention_bias = float(model.attention.bias.detach().cpu().numpy().reshape(-1)[0])
    target_models = {
        "eventFamily": build_target_model(
            name="eventFamily",
            classes=label_spaces["eventFamily"],
            weight=model.event_family_head.weight.detach().cpu().numpy(),
            bias=model.event_family_head.bias.detach().cpu().numpy(),
            top_k=3,
        ),
        "outcome": build_target_model(
            name="outcome",
            classes=label_spaces["outcome"],
            weight=model.outcome_head.weight.detach().cpu().numpy(),
            bias=model.outcome_head.bias.detach().cpu().numpy(),
            top_k=3,
        ),
        "shotSubtype": build_target_model(
            name="shotSubtype",
            classes=label_spaces["shotSubtype"],
            weight=model.shot_subtype_head.weight.detach().cpu().numpy(),
            bias=model.shot_subtype_head.bias.detach().cpu().numpy(),
            top_k=3,
        ),
    }
    return TemporalStudentBundle(
        schema_version=TEMPORAL_STUDENT_SCHEMA_VERSION,
        feature_schema_version=TEMPORAL_STUDENT_FEATURE_SCHEMA_VERSION,
        model_version=model_version,
        trained_at=datetime.now(timezone.utc).isoformat(),
        source_dataset=source_dataset,
        notes=(
            "Perception-first temporal student over structured basketball signals.",
            "Detection and tracking summaries are first-class inputs when present in the training snapshot.",
            "Teacher outputs remain offline/training-only and are not consumed at inference time.",
        ),
        input_feature_names=tuple(str(name) for name in input_feature_names),
        hidden_size=len(projection_bias),
        projection_weight=projection_weight,
        projection_bias=projection_bias,
        attention_weight=attention_weight,
        attention_bias=attention_bias,
        targets=target_models,
    )


def build_temporal_student_report(
    *,
    metrics: dict[str, Any],
    evaluation_rows: Sequence[dict[str, Any]],
) -> str:
    return render_temporal_student_report(metrics=metrics, evaluation_rows=evaluation_rows)


if torch is not None:
    class TorchTemporalStudent(nn.Module):
        def __init__(self, input_size: int, hidden_size: int, label_spaces: dict[str, tuple[str, ...]]) -> None:
            super().__init__()
            self.projection = nn.Linear(input_size, hidden_size)
            self.attention = nn.Linear(hidden_size, 1)
            pooled_size = hidden_size * 4
            self.event_family_head = nn.Linear(pooled_size, len(label_spaces["eventFamily"]))
            self.outcome_head = nn.Linear(pooled_size, len(label_spaces["outcome"]))
            self.shot_subtype_head = nn.Linear(pooled_size, len(label_spaces["shotSubtype"]))

        def forward(self, batch_inputs: torch.Tensor) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
            hidden = torch.tanh(self.projection(batch_inputs))
            attention_logits = self.attention(hidden).squeeze(-1)
            attention = torch.softmax(attention_logits, dim=1)
            weighted_mean = torch.sum(hidden * attention.unsqueeze(-1), dim=1)
            pooled_max, _ = torch.max(hidden, dim=1)
            pooled_last = hidden[:, -1, :]
            pooled_delta = hidden[:, -1, :] - hidden[:, 0, :]
            pooled = torch.cat([weighted_mean, pooled_max, pooled_last, pooled_delta], dim=-1)
            logits = {
                "eventFamily": self.event_family_head(pooled),
                "outcome": self.outcome_head(pooled),
                "shotSubtype": self.shot_subtype_head(pooled),
            }
            return logits, attention


def _load_annotation_rows(path: Path, *, source_set: str) -> list[ClipAnnotation]:
    if source_set == "disagreement_queue":
        rows = _load_jsonl_rows(path, source_set=source_set)
    else:
        rows = load_annotation_rows(path)
    return rows


def _load_jsonl_rows(path: Path, *, source_set: str) -> list[ClipAnnotation]:
    rows: list[ClipAnnotation] = []
    for item in _load_jsonl(path):
        rows.append(ClipAnnotation(**_normalize_row(item, source_set=source_set)))
    return rows


def _normalize_row(row: dict[str, Any], *, source_set: str) -> dict[str, Any]:
    normalized = dict(row)
    normalized.setdefault("sourceKind", "disagreement" if source_set == "disagreement_queue" else normalized.get("sourceKind", "gold"))
    normalized.setdefault("sourceDomain", normalized.get("sourceDomain", "unknown"))
    normalized.setdefault("schemaVersion", TEMPORAL_STUDENT_SCHEMA_VERSION)
    normalized.setdefault(
        "sourceRef",
        _default_source_ref(
            normalized.get("outcome"),
            normalized.get("shotSubtype"),
        ),
    )
    normalized.setdefault("ballVisible", False)
    normalized.setdefault("hoopVisible", False)
    normalized.setdefault("ballNearRim", 0.0)
    normalized.setdefault("ballThroughHoopLikelihood", 0.0)
    normalized.setdefault("possessionChangeLikelihood", 0.0)
    normalized.setdefault("transitionLikelihood", 0.0)
    normalized.setdefault("teacherConfidence", None)
    normalized.setdefault("humanVerified", False)
    normalized.setdefault("reviewerNotes", "")
    normalized.setdefault("rawRuntimeOutputs", {})
    normalized.setdefault("rawTeacherOutputs", {})
    normalized.setdefault("shotSubtype", None)
    return normalized


def _assign_temporal_split(clip_id: str, source_kind: str) -> str:
    bucket = int(sha1(clip_id.encode("utf-8")).hexdigest()[:8], 16) % 10
    if source_kind == "gold":
        return "val" if bucket < 5 else "test"
    if source_kind == "silver":
        return "train" if bucket < 8 else "val"
    if source_kind == "disagreement":
        return "train" if bucket < 7 else "test"
    return "train"


def _example_weight(row: ClipAnnotation) -> float:
    teacher_confidence = row.teacherConfidence
    base_weight = example_weight(row.sourceKind, teacher_confidence, row.sourceDomain)
    hard_multiplier = hard_example_multiplier(
        {
            "sourceKind": row.sourceKind,
            "sourceDomain": row.sourceDomain,
            "priorityScore": _priority_score(row),
            "teacherConfidence": teacher_confidence,
            "priorityReasons": _priority_reasons(row),
            "reasons": _priority_reasons(row),
        },
        base_multiplier=1.6,
    )
    return round(base_weight * hard_multiplier, 4) if base_weight > 0.0 else 0.0


def _priority_reasons(row: ClipAnnotation) -> list[str]:
    reasons: list[str] = []
    if row.sourceDomain == "hard_negative":
        reasons.append("hard negative")
    if row.sourceKind == "disagreement":
        reasons.append("runtime teacher disagree")
    if row.outcome == "missed" and (row.rawRuntimeOutputs or {}).get("outcome") == "made":
        reasons.append("miss vs made conflict")
    if row.rawRuntimeOutputs and (row.rawRuntimeOutputs.get("label") == "Highlight"):
        reasons.append("app facing label only highlight")
    return reasons


def _priority_score(row: ClipAnnotation) -> float:
    score = 0.0
    if row.sourceKind == "disagreement":
        score += 0.45
    if row.sourceDomain == "hard_negative":
        score += 0.3
    if row.teacherConfidence is not None:
        score += 0.2 * max(min(float(row.teacherConfidence), 1.0), 0.0)
    if row.humanVerified:
        score += 0.1
    return min(score, 1.0)


def _synthesize_temporal_student_observations(row: ClipAnnotation) -> tuple[TemporalStudentObservation, ...]:
    runtime = dict(row.rawRuntimeOutputs or {})
    clip_duration = _coerce_float(runtime.get("clipDurationSeconds"), default=4.5)
    runtime_label = _normalize_text_label(runtime.get("label") or runtime.get("canonicalLabel") or row.eventFamily)
    runtime_event_family = _normalize_text_label(runtime.get("eventFamily") or row.eventFamily)
    runtime_outcome = _normalize_text_label(runtime.get("outcome") or row.outcome)
    runtime_shot_subtype = _normalize_text_label(runtime.get("shotSubtype") or row.shotSubtype or "null")
    source_kind = _normalize_text_label(row.sourceKind)
    source_domain = _normalize_text_label(row.sourceDomain)

    phase_positions = (0.15, 0.45, 0.7, 0.9)
    observations: list[TemporalStudentObservation] = []
    for position in phase_positions:
        scales = _phase_scale(row.eventFamily, row.outcome, position)
        structured_signals = {
            "ballNearRim": _scaled_signal(row.ballNearRim or _signal_default(row.eventFamily, row.shotSubtype, "ballNearRim"), scales.get("ballNearRim", scales["default"])),
            "ballAboveRim": _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "ballAboveRim"), scales.get("ballAboveRim", scales["default"])),
            "ballArcApex": _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "ballArcApex"), scales.get("ballArcApex", scales["default"])),
            "ballThroughHoopLikelihood": _scaled_signal(row.ballThroughHoopLikelihood or 0.0, scales.get("ballThroughHoopLikelihood", scales["default"])),
            "possessionChangeLikelihood": _scaled_signal(row.possessionChangeLikelihood or 0.0, scales.get("possessionChangeLikelihood", scales["default"])),
            "transitionLikelihood": _scaled_signal(row.transitionLikelihood or 0.0, scales.get("transitionLikelihood", scales["default"])),
            "playerToRimDistance": _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "playerToRimDistance"), scales.get("playerToRimDistance", scales["default"])),
            "ballCarrierSpeed": _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "ballCarrierSpeed"), scales.get("ballCarrierSpeed", scales["default"])),
            "transitionSpeedScore": _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "transitionSpeedScore"), scales.get("transitionSpeedScore", scales["default"])),
            "defenderProximityAtShot": _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "defenderProximityAtShot"), scales.get("defenderProximityAtShot", scales["default"])),
            "shotReleaseCandidate": _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "shotReleaseCandidate"), scales.get("shotReleaseCandidate", scales["default"])),
            "samePlayContinuityScore": _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "samePlayContinuityScore"), scales.get("samePlayContinuityScore", scales["default"])),
        }

        if row.eventFamily == "shot_attempt" and row.outcome == "made" and position >= 0.7:
            structured_signals["ballThroughHoopLikelihood"] = max(structured_signals["ballThroughHoopLikelihood"], 0.86)
        if row.eventFamily == "shot_attempt" and row.outcome == "missed" and position >= 0.7:
            structured_signals["ballThroughHoopLikelihood"] = min(structured_signals["ballThroughHoopLikelihood"], 0.18)
        if row.eventFamily == "turnover" and position >= 0.45:
            structured_signals["possessionChangeLikelihood"] = max(structured_signals["possessionChangeLikelihood"], 0.82)
        if row.eventFamily == "transition":
            structured_signals["transitionLikelihood"] = max(structured_signals["transitionLikelihood"], 0.74)
            structured_signals["transitionSpeedScore"] = max(structured_signals["transitionSpeedScore"], 0.72)
        if row.eventFamily == "defensive_event":
            structured_signals["defenderProximityAtShot"] = max(structured_signals["defenderProximityAtShot"], 0.8)

        ball_visible = 1.0 if row.ballVisible else 0.0
        hoop_visible = 1.0 if row.hoopVisible else 0.0
        ball_detection_confidence = 0.94 if row.ballVisible else 0.05
        hoop_detection_confidence = 0.92 if row.hoopVisible else 0.05
        player_count = _player_count_for_example(row.eventFamily)
        tracked_player_count = max(player_count - 1.0, 1.0)
        ball_track_count = 1.0 if row.ballVisible else 0.0
        rim_track_count = 1.0 if row.hoopVisible else 0.0
        tracked_ball_confidence = 0.9 if row.ballVisible else 0.05
        tracking_continuity = _scaled_signal(_signal_default(row.eventFamily, row.shotSubtype, "samePlayContinuityScore"), 0.96)

        perception_features = {
            "basketballConfidence": 0.95 if row.ballVisible else 0.1,
            "rimConfidence": 0.92 if row.hoopVisible else 0.08,
            "playerCount": player_count,
            "trackedPlayerCount": tracked_player_count,
            "trackedBallConfidence": tracked_ball_confidence,
            "ballVisible": bool(row.ballVisible),
            "hoopVisible": bool(row.hoopVisible),
        }
        detection_features = {
            "ballVisible": bool(row.ballVisible),
            "hoopVisible": bool(row.hoopVisible),
            "ballDetectionConfidence": ball_detection_confidence,
            "hoopDetectionConfidence": hoop_detection_confidence,
            "ballTrackCount": ball_track_count,
            "rimTrackCount": rim_track_count,
            "detectionDensity": min(max((ball_visible + hoop_visible + player_count / 10.0) / 3.0, 0.0), 1.0),
        }
        tracking_features = {
            "playerTrackCount": player_count,
            "trackedPlayerCount": tracked_player_count,
            "trackedBallConfidence": tracked_ball_confidence,
            "trackingContinuity": tracking_continuity,
            "trackingDensity": min(max((tracked_player_count / 8.0) + (ball_track_count * 0.2), 0.0), 1.0),
            "ballTrackCount": ball_track_count,
            "rimTrackCount": rim_track_count,
            "ballTrackConfidence": tracked_ball_confidence,
        }
        runtime_features = {
            "label": runtime_label,
            "eventFamily": runtime_event_family,
            "outcome": runtime_outcome,
            "shotSubtype": runtime_shot_subtype,
            "confidence": _coerce_float(runtime.get("confidence"), default=row.teacherConfidence or 0.0),
            "sourceKind": row.sourceKind,
            "sourceDomain": row.sourceDomain,
            "sourceSet": _source_set_for_kind(row.sourceKind),
            "ballVisible": bool(row.ballVisible),
            "hoopVisible": bool(row.hoopVisible),
            "sourceRefPresent": bool(row.sourceRef),
            "humanVerified": bool(row.humanVerified),
            "clipDurationSeconds": clip_duration,
            "sourceEventCount": 1.0,
            "wasMerged": False,
        }
        observations.append(
            TemporalStudentObservation(
                timestamp_seconds=round(position * clip_duration, 4),
                structured_signals=structured_signals,
                perception_features=perception_features,
                detection_features=detection_features,
                tracking_features=tracking_features,
                runtime_features=runtime_features,
            )
        )
    return tuple(observations)


def _phase_scale(event_family: str, outcome: str, position: float) -> dict[str, float]:
    default = 0.55 if position < 0.3 else 0.85 if position < 0.8 else 0.7
    scales = {"default": default}
    if event_family == "shot_attempt":
        scales.update(
            {
                "ballNearRim": 0.45 if position < 0.3 else 0.95 if position < 0.8 else 0.7,
                "ballAboveRim": 0.35 if position < 0.3 else 0.9 if position < 0.7 else 0.55,
                "ballArcApex": 0.25 if position < 0.3 else 0.88 if position < 0.7 else 0.4,
                "shotReleaseCandidate": 0.5 if position < 0.3 else 0.95 if position < 0.6 else 0.45,
                "defenderProximityAtShot": 0.6 if outcome == "blocked" else 0.75,
                "samePlayContinuityScore": 0.7,
            }
        )
    elif event_family == "turnover":
        scales.update(
            {
                "possessionChangeLikelihood": 0.4 if position < 0.3 else 0.95,
                "samePlayContinuityScore": 0.35,
                "transitionSpeedScore": 0.45,
            }
        )
    elif event_family == "transition":
        scales.update(
            {
                "transitionLikelihood": 0.72 if position < 0.3 else 0.95,
                "transitionSpeedScore": 0.68 if position < 0.3 else 0.92,
                "ballCarrierSpeed": 0.62 if position < 0.3 else 0.8,
            }
        )
    else:
        scales["samePlayContinuityScore"] = 0.45
    return scales


def _signal_default(event_family: str, shot_subtype: str | None, signal_name: str) -> float:
    if signal_name == "ballAboveRim":
        if shot_subtype == "dunk":
            return 0.9
        if shot_subtype == "layup":
            return 0.52
        return 0.34 if event_family == "shot_attempt" else 0.08
    if signal_name == "ballArcApex":
        if shot_subtype in {"jumper", "three"}:
            return 0.78
        if shot_subtype == "dunk":
            return 0.3
        return 0.46 if event_family == "shot_attempt" else 0.06
    if signal_name == "playerToRimDistance":
        if shot_subtype == "dunk":
            return 0.16
        if shot_subtype == "layup":
            return 0.22
        if shot_subtype == "putback":
            return 0.14
        return 0.58 if event_family == "shot_attempt" else 0.42
    if signal_name == "ballCarrierSpeed":
        return 0.74 if event_family == "transition" else 0.28
    if signal_name == "transitionSpeedScore":
        return 0.82 if event_family == "transition" else 0.2
    if signal_name == "defenderProximityAtShot":
        return 0.78 if event_family == "defensive_event" else 0.34
    if signal_name == "shotReleaseCandidate":
        return 0.82 if event_family == "shot_attempt" else 0.12
    if signal_name == "samePlayContinuityScore":
        return 0.78 if event_family == "shot_attempt" else 0.4
    if signal_name == "ballNearRim":
        if shot_subtype == "dunk":
            return 0.88
        if shot_subtype == "layup":
            return 0.74
        return 0.52 if event_family == "shot_attempt" else 0.1
    return 0.0


def _scaled_signal(value: float | None, scale: float) -> float:
    return round(float(max(min((value or 0.0) * scale, 1.0), 0.0)), 4)


def _player_count_for_example(event_family: str) -> float:
    if event_family in {"shot_attempt", "turnover"}:
        return 5.0
    if event_family == "transition":
        return 6.0
    if event_family == "defensive_event":
        return 4.0
    return 3.0


def _source_set_for_kind(source_kind: str) -> str:
    if source_kind == "gold":
        return "gold_set"
    if source_kind == "silver":
        return "silver_set"
    if source_kind == "disagreement":
        return "disagreement_queue"
    return "unknown"


def _to_nested_tuple(array: np.ndarray) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(value) for value in row.tolist()) for row in array)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _promote_missing_classes(examples: list[TemporalStudentTrainingExample]) -> list[TemporalStudentTrainingExample]:
    train_rows = [example for example in examples if example.split == "train"]
    present = {
        target: {
            getattr(example, target) if target != "shot_subtype" else (example.shot_subtype or "null")
            for example in train_rows
        }
        for target in ("event_family", "outcome", "shot_subtype")
    }
    missing_families = [label for label in EVENT_FAMILIES if label not in present["event_family"]]
    missing_outcomes = [label for label in OUTCOMES if label not in present["outcome"]]
    missing_subtypes = [label for label in SHOT_SUBTYPES if label not in present["shot_subtype"]]

    promoted_ids: set[str] = set()
    examples_by_id = {example.clip_id: example for example in examples}

    def promote(label: str, key: str) -> None:
        for example in examples:
            if example.clip_id in promoted_ids or example.split == "train":
                continue
            value = getattr(example, key) if key != "shot_subtype" else (example.shot_subtype or "null")
            if value != label:
                continue
            promoted_ids.add(example.clip_id)
            examples_by_id[example.clip_id] = TemporalStudentTrainingExample(
                clip_id=example.clip_id,
                observations=example.observations,
                event_family=example.event_family,
                outcome=example.outcome,
                shot_subtype=example.shot_subtype,
                source_kind=example.source_kind,
                source_domain=example.source_domain,
                split="train",
                weight=example.weight,
                teacher_confidence=example.teacher_confidence,
                human_verified=example.human_verified,
                raw_runtime_outputs=example.raw_runtime_outputs,
                raw_teacher_outputs=example.raw_teacher_outputs,
            )
            return

    for label in missing_families:
        promote(label, "event_family")
    for label in missing_outcomes:
        promote(label, "outcome")
    for label in missing_subtypes:
        promote(label, "shot_subtype")

    return list(examples_by_id.values())


def _default_source_ref(outcome: Any, shot_subtype: Any) -> str:
    normalized_outcome = _normalize_text_label(outcome)
    normalized_subtype = _normalize_text_label(shot_subtype)
    if normalized_outcome == "made":
        return "backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4"
    if normalized_outcome == "missed":
        return "backend/.external/HoopCut_FH/main/static/clips/miss_2_3.13s.mp4"
    if normalized_subtype in {"dunk", "layup", "jumper", "three", "putback"}:
        return "backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4"
    return "backend/.external/HoopCut_FH/main/static/clips/miss_1_0.00s.mp4"


def _normalize_text_label(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return text.replace(" ", "_").replace("-", "_")


def _coerce_float(value: Any, *, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(parsed) or np.isinf(parsed):
        return default
    return parsed


def build_temporal_student_report(
    *,
    metrics: dict[str, Any],
    evaluation_rows: Sequence[dict[str, Any]],
) -> str:
    return render_temporal_student_report(metrics=metrics, evaluation_rows=evaluation_rows)


def build_temporal_student_dataset_manifest(examples: Sequence[TemporalStudentTrainingExample]) -> dict[str, Any]:
    return {
        "schemaVersion": TEMPORAL_STUDENT_SCHEMA_VERSION,
        "featureSchemaVersion": TEMPORAL_STUDENT_FEATURE_SCHEMA_VERSION,
        "modelVersion": TEMPORAL_STUDENT_MODEL_VERSION,
        "summary": {
            "totalExamples": len(examples),
            "trainExamples": sum(1 for example in examples if example.split == "train"),
            "valExamples": sum(1 for example in examples if example.split == "val"),
            "testExamples": sum(1 for example in examples if example.split == "test"),
        },
        "counts": {
            "sourceKind": dict(sorted(Counter(example.source_kind for example in examples).items())),
            "sourceDomain": dict(sorted(Counter(example.source_domain for example in examples).items())),
            "eventFamily": dict(sorted(Counter(example.event_family for example in examples).items())),
            "outcome": dict(sorted(Counter(example.outcome for example in examples).items())),
            "shotSubtype": dict(sorted(Counter(example.shot_subtype or "null" for example in examples).items())),
        },
    }

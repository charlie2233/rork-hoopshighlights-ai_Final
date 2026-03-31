from __future__ import annotations

from collections import Counter
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from services.inference.app.runtime_models.temporal_student import (
    EVENT_FAMILIES,
    OUTCOMES,
    SHOT_SUBTYPES,
    TemporalStudentBundle,
    TemporalStudentObservation,
    TemporalStudentTargetPrediction,
    default_temporal_student_feature_names,
    vectorize_temporal_student_observation,
    write_temporal_student_bundle,
)
from services.inference.training.perception_supervision import (
    PerceptionSupervisionExample,
    extract_perception_context,
    load_perception_supervision_examples,
)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover - depends on torch availability
    torch = None
    nn = None
    F = None


TEMPORAL_STUDENT_MODEL_VERSION = "temporal-student-v1"


@dataclass(frozen=True)
class TemporalStudentTrainingExample:
    clip_id: str
    observations: tuple[TemporalStudentObservation, ...]
    event_family: str
    outcome: str
    shot_subtype: str | None
    source_kind: str
    split: str = "train"
    weight: float = 1.0
    source_domain: str = "unknown"
    has_event_localization: bool = False


@dataclass(frozen=True)
class TemporalStudentTrainingResult:
    bundle: TemporalStudentBundle
    metrics: dict[str, Any]
    training_examples: int


if nn is not None:
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


def load_temporal_student_examples(repo_root: Path) -> list[TemporalStudentTrainingExample]:
    perception_examples = load_perception_supervision_examples(repo_root)
    examples: list[TemporalStudentTrainingExample] = []
    for example in perception_examples:
        if example.ignored:
            continue
        event_family = example.event_family if example.event_family in EVENT_FAMILIES else "other"
        outcome = example.outcome if example.outcome in OUTCOMES else "uncertain"
        shot_subtype = example.shot_subtype if example.shot_subtype in SHOT_SUBTYPES else None
        examples.append(
            TemporalStudentTrainingExample(
                clip_id=example.clip_id,
                observations=_build_observations(example),
                event_family=event_family,
                outcome=outcome,
                shot_subtype=shot_subtype,
                source_kind=example.source_kind,
                source_domain=example.source_domain,
                split=example.split,
                weight=example.weight,
                has_event_localization=any(
                    value is not None
                    for value in (
                        example.event_start_seconds,
                        example.event_center_seconds,
                        example.event_end_seconds,
                        example.shot_release_time_seconds,
                        example.ball_near_rim_time_seconds,
                        example.ball_through_hoop_time_seconds,
                        example.possession_change_time_seconds,
                        example.transition_start_time_seconds,
                    )
                ),
            )
        )
    return examples


def train_temporal_student_from_repo(
    repo_root: Path,
    *,
    output_path: Path | None = None,
    hidden_size: int = 16,
    epochs: int = 140,
    learning_rate: float = 0.025,
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
    epochs: int = 140,
    learning_rate: float = 0.025,
) -> TemporalStudentTrainingResult:
    if torch is None or nn is None or F is None:  # pragma: no cover
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
        loss = compute_student_loss(
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
        metrics = compute_training_metrics(logits=logits, dataset=dataset, label_spaces=label_spaces)
    bundle = export_temporal_student_bundle(
        model=model,
        input_feature_names=input_feature_names,
        label_spaces=label_spaces,
        source_dataset="perception_supervision+teacher_backed",
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
                "expectedEventFamily": example.event_family,
                "expectedOutcome": example.outcome,
                "expectedShotSubtype": example.shot_subtype or "null",
                "predictedEventFamily": prediction.eventFamily or "other",
                "predictedOutcome": prediction.outcome or "uncertain",
                "predictedShotSubtype": prediction.shotSubtype or "null",
                "predictedDisplayLabel": prediction.label,
                "isUncertain": bool(prediction.isUncertain),
                "hasEventLocalization": bool(example.has_event_localization),
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
    flat_label_spread = len({row["predictedDisplayLabel"] for row in rows})
    flat_label_distribution = dict(sorted(Counter(row["predictedDisplayLabel"] for row in rows).items()))
    event_family_distribution = dict(sorted(Counter(row["predictedEventFamily"] for row in rows).items()))
    outcome_distribution = dict(sorted(Counter(row["predictedOutcome"] for row in rows).items()))
    subtype_distribution = dict(sorted(Counter(row["predictedShotSubtype"] for row in rows).items()))
    highlight_dominance = round(flat_label_distribution.get("Highlight", 0) / total, 4)
    other_dominance = round(event_family_distribution.get("other", 0) / total, 4)
    miss_vs_made_confusion = sum(
        1
        for row in rows
        if row["expectedOutcome"] == "missed" and row["predictedDisplayLabel"] == "Made Shot"
    )
    localized_rows = [row for row in rows if row["hasEventLocalization"]]
    true_positive = sum(
        1
        for row in localized_rows
        if row["expectedEventFamily"] != "other" and row["predictedEventFamily"] != "other"
    )
    false_positive = sum(
        1
        for row in localized_rows
        if row["expectedEventFamily"] == "other" and row["predictedEventFamily"] != "other"
    )
    false_negative = sum(
        1
        for row in localized_rows
        if row["expectedEventFamily"] != "other" and row["predictedEventFamily"] == "other"
    )
    event_detection_precision = round(
        true_positive / max(true_positive + false_positive, 1),
        4,
    )
    event_detection_recall = round(
        true_positive / max(true_positive + false_negative, 1),
        4,
    )
    return {
        "eventFamilyAccuracy": event_family_accuracy,
        "outcomeAccuracy": outcome_accuracy,
        "shotSubtypeAccuracy": shot_subtype_accuracy,
        "uncertaintyRate": uncertainty_rate,
        "flatLabelSpread": flat_label_spread,
        "flatLabelDistribution": flat_label_distribution,
        "eventFamilyDistribution": event_family_distribution,
        "outcomeDistribution": outcome_distribution,
        "shotSubtypeDistribution": subtype_distribution,
        "highlightDominance": highlight_dominance,
        "otherDominance": other_dominance,
        "missVsMadeConfusion": miss_vs_made_confusion,
        "eventDetectionPrecision": event_detection_precision,
        "eventDetectionRecall": event_detection_recall,
        "eventDetectionLabeledRows": len(localized_rows),
        "evaluationRows": rows,
    }


def build_training_tensors(
    examples: Sequence[TemporalStudentTrainingExample],
    *,
    input_feature_names: Sequence[str],
) -> dict[str, Any]:
    if torch is None:  # pragma: no cover
        raise RuntimeError("torch is required to build temporal student tensors")
    sequence_lengths = [len(example.observations) for example in examples]
    if len(set(sequence_lengths)) != 1:
        raise ValueError("Temporal student training examples must be padded to equal length before training.")
    inputs = torch.tensor(
        [
            [
                [float(vectorize_temporal_student_observation(observation, input_feature_names)[i]) for i in range(len(input_feature_names))]
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


def compute_student_loss(
    *,
    logits: dict[str, Any],
    targets: dict[str, Any],
    weights,
    shot_mask,
):
    event_loss = F.cross_entropy(logits["eventFamily"], targets["eventFamily"], reduction="none")
    outcome_loss = F.cross_entropy(logits["outcome"], targets["outcome"], reduction="none")
    subtype_loss = F.cross_entropy(logits["shotSubtype"], targets["shotSubtype"], reduction="none")

    weighted_event = event_loss * weights
    weighted_outcome = outcome_loss * weights
    weighted_subtype = subtype_loss * weights * shot_mask
    normalizer = torch.clamp(weights.sum(), min=1e-6)
    subtype_normalizer = torch.clamp((weights * shot_mask).sum(), min=1e-6)
    return (
        weighted_event.sum() / normalizer
        + weighted_outcome.sum() / normalizer
        + weighted_subtype.sum() / subtype_normalizer
    )


def compute_training_metrics(
    *,
    logits: dict[str, Any],
    dataset: dict[str, Any],
    label_spaces: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key, labels in label_spaces.items():
        predictions = torch.argmax(logits[key], dim=1)
        accuracy = (predictions == dataset["targets"][key]).float().mean().item()
        metrics[f"{key}Accuracy"] = round(float(accuracy), 4)
        metrics[f"{key}Labels"] = labels
    return metrics


def export_temporal_student_bundle(
    *,
    model,
    input_feature_names: Sequence[str],
    label_spaces: dict[str, tuple[str, ...]],
    source_dataset: str,
) -> TemporalStudentBundle:
    projection_weight = tuple(
        tuple(float(value) for value in row)
        for row in model.projection.weight.detach().cpu().numpy().tolist()
    )
    projection_bias = tuple(float(value) for value in model.projection.bias.detach().cpu().numpy().tolist())
    attention_weight = tuple(float(value) for value in model.attention.weight.detach().cpu().numpy()[0].tolist())
    attention_bias = float(model.attention.bias.detach().cpu().numpy()[0])

    targets = {}
    for name, labels, head in (
        ("eventFamily", label_spaces["eventFamily"], model.event_family_head),
        ("outcome", label_spaces["outcome"], model.outcome_head),
        ("shotSubtype", label_spaces["shotSubtype"], model.shot_subtype_head),
    ):
        targets[name] = _export_target(
            name=name,
            labels=labels,
            weight_matrix=head.weight.detach().cpu().numpy(),
            bias_vector=head.bias.detach().cpu().numpy(),
        )

    return TemporalStudentBundle(
        schema_version="temporal-student-v1",
        feature_schema_version="temporal-student-feature-v1",
        model_version=TEMPORAL_STUDENT_MODEL_VERSION,
        trained_at=datetime.now(timezone.utc).isoformat(),
        source_dataset=source_dataset,
        notes=(
            "Perception-first temporal student trained on structured basketball signals.",
            "Gold examples anchor evaluation and weighting remains source-aware.",
            "Candidate windows stay frozen; only labels and perception features change.",
        ),
        input_feature_names=tuple(input_feature_names),
        hidden_size=int(model.projection.out_features),
        projection_weight=projection_weight,
        projection_bias=projection_bias,
        attention_weight=attention_weight,
        attention_bias=attention_bias,
        targets=targets,
    )


def build_temporal_student_report(
    *,
    metrics: dict[str, Any],
    evaluation_rows: Sequence[dict[str, Any]],
) -> str:
    lines = [
        "# Temporal Student Report",
        "",
        f"- Event family accuracy: `{metrics.get('eventFamilyAccuracy')}`",
        f"- Outcome accuracy: `{metrics.get('outcomeAccuracy')}`",
        f"- Shot subtype accuracy: `{metrics.get('shotSubtypeAccuracy')}`",
        f"- Uncertainty rate: `{metrics.get('uncertaintyRate')}`",
        f"- Flat label spread: `{metrics.get('flatLabelSpread')}`",
        f"- Highlight dominance: `{metrics.get('highlightDominance')}`",
        f"- EventFamily=other dominance: `{metrics.get('otherDominance')}`",
        f"- Miss-vs-made confusion: `{metrics.get('missVsMadeConfusion')}`",
        f"- Event-detection precision: `{metrics.get('eventDetectionPrecision')}`",
        f"- Event-detection recall: `{metrics.get('eventDetectionRecall')}`",
        "",
        "## Distributions",
        f"- Flat labels: `{metrics.get('flatLabelDistribution')}`",
        f"- Event family: `{metrics.get('eventFamilyDistribution')}`",
        f"- Outcome: `{metrics.get('outcomeDistribution')}`",
        f"- Shot subtype: `{metrics.get('shotSubtypeDistribution')}`",
        "",
        "## Evaluation Rows",
    ]
    for row in evaluation_rows[:12]:
        lines.append(
            f"- `{row['clipId']}`: `{row['predictedDisplayLabel']}` "
            f"({row['predictedEventFamily']} / {row['predictedOutcome']} / {row['predictedShotSubtype']})"
        )
    return "\n".join(lines) + "\n"


def _export_target(*, name: str, labels: Sequence[str], weight_matrix: np.ndarray, bias_vector: np.ndarray):
    from services.inference.app.temporal_encoder import TemporalTargetModel

    return TemporalTargetModel(
        name=name,
        classes=tuple(str(label) for label in labels),
        weight=tuple(tuple(float(value) for value in row) for row in weight_matrix.tolist()),
        bias=tuple(float(value) for value in bias_vector.tolist()),
        temperature=1.0,
        uncertainty_threshold=0.48 if name == "eventFamily" else 0.46,
        margin_threshold=0.06 if name == "eventFamily" else 0.05,
        top_k=3,
    )


def _build_observations(example: PerceptionSupervisionExample) -> tuple[TemporalStudentObservation, ...]:
    context = {
        "structuredSignals": dict(example.perception_context.get("structuredSignals") or {}),
        "perceptionSummary": dict(example.perception_context.get("perceptionSummary") or {}),
        "sourceDomainTag": example.perception_context.get("sourceDomainTag"),
    }
    runtime = dict(example.raw_runtime_outputs or {})
    clip_duration = _coerce_float(runtime.get("clipDurationSeconds"), default=4.5)
    positions = (0.12, 0.38, 0.68, 0.9)
    observations: list[TemporalStudentObservation] = []
    for position in positions:
        observations.append(
            TemporalStudentObservation(
                timestamp_seconds=round(position * clip_duration, 4),
                structured_signals=_phase_structured_signals(example, context["structuredSignals"], position),
                perception_features=_phase_perception_features(example, context["perceptionSummary"], position),
                detection_features=_phase_detection_features(example, context["perceptionSummary"], position),
                tracking_features=_phase_tracking_features(example, context["perceptionSummary"], position),
                runtime_features=_runtime_features(example, runtime, clip_duration),
            )
        )
    return tuple(observations)


def _phase_structured_signals(
    example: PerceptionSupervisionExample,
    structured_signals: dict[str, Any],
    position: float,
) -> dict[str, float]:
    clip_duration = max(_coerce_float((example.raw_runtime_outputs or {}).get("clipDurationSeconds"), default=0.0), 1.0)
    timestamp_seconds = round(position * clip_duration, 4)
    signals = {
        "ballNearRim": _coerce_float(structured_signals.get("ballNearRim"), default=_coerce_float(example.features.get("signal.ballNearRim"), default=0.0)),
        "ballAboveRim": _coerce_float(structured_signals.get("ballAboveRim"), default=0.0),
        "ballArcApex": _coerce_float(structured_signals.get("ballArcApex"), default=0.0),
        "ballThroughHoopLikelihood": _coerce_float(structured_signals.get("ballThroughHoopLikelihood"), default=_coerce_float(example.features.get("signal.ballThroughHoopLikelihood"), default=0.0)),
        "possessionChangeLikelihood": _coerce_float(structured_signals.get("possessionChangeLikelihood"), default=_coerce_float(example.features.get("signal.possessionChangeLikelihood"), default=0.0)),
        "transitionLikelihood": _coerce_float(structured_signals.get("transitionLikelihood"), default=_coerce_float(example.features.get("signal.transitionLikelihood"), default=0.0)),
        "playerToRimDistance": _coerce_float(structured_signals.get("playerToRimDistance"), default=0.0),
        "ballCarrierSpeed": _coerce_float(structured_signals.get("ballCarrierSpeed"), default=0.0),
        "transitionSpeedScore": _coerce_float(structured_signals.get("transitionSpeedScore"), default=0.0),
        "defenderProximityAtShot": _coerce_float(structured_signals.get("defenderProximityAtShot"), default=0.0),
        "shotReleaseCandidate": _coerce_float(structured_signals.get("shotReleaseCandidate"), default=0.0),
        "samePlayContinuityScore": _coerce_float(structured_signals.get("samePlayContinuityScore"), default=0.0),
    }
    if example.event_family == "shot_attempt":
        if position >= 0.55:
            signals["shotReleaseCandidate"] = max(signals["shotReleaseCandidate"], 0.82)
            signals["ballNearRim"] = max(signals["ballNearRim"], 0.6)
        if example.outcome == "made" and position >= 0.7:
            signals["ballThroughHoopLikelihood"] = max(signals["ballThroughHoopLikelihood"], 0.78)
        if example.outcome == "missed" and position >= 0.7:
            signals["ballThroughHoopLikelihood"] = min(signals["ballThroughHoopLikelihood"], 0.2)
    if example.event_family == "transition":
        signals["transitionLikelihood"] = max(signals["transitionLikelihood"], 0.72)
        signals["transitionSpeedScore"] = max(signals["transitionSpeedScore"], 0.68)
    if example.event_family == "turnover" and position >= 0.4:
        signals["possessionChangeLikelihood"] = max(signals["possessionChangeLikelihood"], 0.7)
    release_activation = _localization_activation(timestamp_seconds, example.shot_release_time_seconds, width_seconds=0.45)
    near_rim_activation = _localization_activation(timestamp_seconds, example.ball_near_rim_time_seconds, width_seconds=0.55)
    through_hoop_activation = _localization_activation(timestamp_seconds, example.ball_through_hoop_time_seconds, width_seconds=0.55)
    possession_activation = _localization_activation(timestamp_seconds, example.possession_change_time_seconds, width_seconds=0.6)
    transition_activation = _localization_activation(timestamp_seconds, example.transition_start_time_seconds, width_seconds=0.8)
    if release_activation > 0.0:
        signals["shotReleaseCandidate"] = max(signals["shotReleaseCandidate"], 0.65 + (0.3 * release_activation))
    if near_rim_activation > 0.0:
        signals["ballNearRim"] = max(signals["ballNearRim"], 0.55 + (0.35 * near_rim_activation))
    if through_hoop_activation > 0.0:
        signals["ballThroughHoopLikelihood"] = max(signals["ballThroughHoopLikelihood"], 0.55 + (0.35 * through_hoop_activation))
    if possession_activation > 0.0:
        signals["possessionChangeLikelihood"] = max(signals["possessionChangeLikelihood"], 0.55 + (0.35 * possession_activation))
    if transition_activation > 0.0:
        signals["transitionLikelihood"] = max(signals["transitionLikelihood"], 0.55 + (0.35 * transition_activation))
        signals["transitionSpeedScore"] = max(signals["transitionSpeedScore"], 0.5 + (0.32 * transition_activation))
    return {key: round(max(min(value, 1.0), 0.0), 4) for key, value in signals.items()}


def _phase_perception_features(
    example: PerceptionSupervisionExample,
    perception_summary: dict[str, Any],
    position: float,
) -> dict[str, float]:
    detection_counts = dict(perception_summary.get("detectionCounts") or {})
    track_counts = dict(perception_summary.get("trackCounts") or {})
    basketball_confidence = _coerce_float(example.features.get("perception.primaryBallTrack.averageConfidence"), default=0.0)
    rim_confidence = _coerce_float(example.features.get("perception.primaryRimTrack.averageConfidence"), default=0.0)
    return {
        "ballVisible": 1.0 if example.ball_visible else 0.0,
        "hoopVisible": 1.0 if example.hoop_visible else 0.0,
        "basketballConfidence": max(basketball_confidence, 0.68 if example.ball_visible else 0.0),
        "rimConfidence": max(rim_confidence, 0.7 if example.hoop_visible else 0.0),
        "playerCount": float(_coerce_int(detection_counts.get("player")) or _coerce_int(track_counts.get("player")) or 6),
        "trackedPlayerCount": float(_coerce_int(track_counts.get("player")) or 4),
        "trackedBallConfidence": max(
            _coerce_float(example.features.get("perception.primaryBallTrack.averageConfidence"), default=0.0),
            0.72 if example.ball_visible and position >= 0.4 else 0.0,
        ),
        "detectionDensity": _coerce_float(example.features.get("perception.detectionCount.total"), default=0.0) / max(
            _coerce_float(example.features.get("perception.sampledFrameCount"), default=1.0),
            1.0,
        ),
        "trackingDensity": _coerce_float(example.features.get("perception.trackCount.total"), default=0.0) / 6.0,
    }


def _phase_detection_features(
    example: PerceptionSupervisionExample,
    perception_summary: dict[str, Any],
    position: float,
) -> dict[str, float]:
    detection_counts = dict(perception_summary.get("detectionCounts") or {})
    return {
        "ballVisible": 1.0 if example.ball_visible else 0.0,
        "hoopVisible": 1.0 if example.hoop_visible else 0.0,
        "ballDetectionConfidence": max(
            _coerce_float(example.features.get("perception.detectionCount.ball"), default=0.0) / max(_coerce_float(example.features.get("perception.sampledFrameCount"), default=1.0), 1.0),
            0.74 if example.ball_visible and position >= 0.4 else 0.0,
        ),
        "hoopDetectionConfidence": max(
            _coerce_float(example.features.get("perception.detectionCount.rim"), default=0.0) / max(_coerce_float(example.features.get("perception.sampledFrameCount"), default=1.0), 1.0),
            0.72 if example.hoop_visible else 0.0,
        ),
        "detectionDensity": float(sum(_coerce_int(value) for value in detection_counts.values())) / max(
            _coerce_float(example.features.get("perception.sampledFrameCount"), default=1.0),
            1.0,
        ),
    }


def _phase_tracking_features(
    example: PerceptionSupervisionExample,
    perception_summary: dict[str, Any],
    position: float,
) -> dict[str, float]:
    track_counts = dict(perception_summary.get("trackCounts") or {})
    continuity = _coerce_float(example.features.get("signal.samePlayContinuityScore"), default=0.0)
    if example.event_family == "transition":
        continuity = max(continuity, 0.66)
    return {
        "playerTrackCount": float(_coerce_int(track_counts.get("player")) or 3),
        "trackedPlayerCount": float(_coerce_int(track_counts.get("player")) or 3),
        "trackedBallConfidence": max(
            _coerce_float(example.features.get("perception.primaryBallTrack.averageConfidence"), default=0.0),
            0.7 if example.ball_visible and position >= 0.45 else 0.0,
        ),
        "ballTrackCount": float(_coerce_int(track_counts.get("basketball")) or (1 if example.ball_visible else 0)),
        "rimTrackCount": float(_coerce_int(track_counts.get("rim")) or (1 if example.hoop_visible else 0)),
        "trackingContinuity": continuity,
        "trackingDensity": _coerce_float(example.features.get("perception.trackCount.total"), default=0.0) / 6.0,
    }


def _runtime_features(
    example: PerceptionSupervisionExample,
    runtime: dict[str, Any],
    clip_duration: float,
) -> dict[str, Any]:
    return {
        "label": runtime.get("label"),
        "canonicalLabel": runtime.get("canonicalLabel") or runtime.get("label"),
        "displayLabel": runtime.get("label"),
        "eventFamily": runtime.get("eventFamily") or example.event_family,
        "outcome": runtime.get("outcome") or example.outcome,
        "shotSubtype": runtime.get("shotSubtype") or example.shot_subtype,
        "confidence": runtime.get("confidence", 0.0),
        "topCount": len(runtime.get("topKLabels") or []),
        "sourceRef": example.source_ref,
        "humanVerified": example.human_verified,
        "clipDurationSeconds": runtime.get("clipDurationSeconds", clip_duration),
        "eventStartSeconds": runtime.get("eventStartSeconds", example.event_start_seconds),
        "eventCenterSeconds": runtime.get("eventCenterSeconds", example.event_center_seconds if example.event_center_seconds is not None else clip_duration / 2.0),
        "eventEndSeconds": runtime.get("eventEndSeconds", example.event_end_seconds),
        "shotReleaseTimeSeconds": runtime.get("shotReleaseTimeSeconds", example.shot_release_time_seconds),
        "ballNearRimTimeSeconds": runtime.get("ballNearRimTimeSeconds", example.ball_near_rim_time_seconds),
        "ballThroughHoopTimeSeconds": runtime.get("ballThroughHoopTimeSeconds", example.ball_through_hoop_time_seconds),
        "possessionChangeTimeSeconds": runtime.get("possessionChangeTimeSeconds", example.possession_change_time_seconds),
        "transitionStartTimeSeconds": runtime.get("transitionStartTimeSeconds", example.transition_start_time_seconds),
        "preRollSeconds": runtime.get("preRollSeconds", clip_duration / 2.0),
        "postRollSeconds": runtime.get("postRollSeconds", clip_duration / 2.0),
        "sourceEventCount": runtime.get("sourceEventCount", 1),
        "wasMerged": runtime.get("wasMerged", False),
        "sourceDomain": example.source_domain,
        "sourceSet": example.source_set,
        "sourceKind": example.source_kind,
        "videoMAE": {"topLabel": _top_label(runtime.get("videoMAE"))},
        "xclip": {"topLabel": _top_label(runtime.get("xclip"))},
    }


def _top_label(payload: Any) -> str | None:
    if isinstance(payload, dict):
        top_k = payload.get("topK")
        if isinstance(top_k, list) and top_k:
            first = top_k[0]
            if isinstance(first, dict):
                return first.get("label")
        return payload.get("topLabel")
    return None


def _coerce_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _localization_activation(timestamp_seconds: float, event_time_seconds: float | None, *, width_seconds: float) -> float:
    if event_time_seconds is None:
        return 0.0
    distance = abs(float(timestamp_seconds) - float(event_time_seconds))
    if distance >= width_seconds:
        return 0.0
    return round(1.0 - (distance / max(width_seconds, 1e-6)), 4)

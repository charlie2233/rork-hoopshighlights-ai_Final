from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from services.inference.app.runtime_models.temporal_event_detector import (
    EVENT_FAMILIES,
    OUTCOMES,
    SHOT_SUBTYPES,
    TemporalConvLayer,
    TemporalEventDetectorBundle,
    build_temporal_event_detector_feature_map,
    default_temporal_event_detector_feature_names,
    vectorize_temporal_event_detector_observation,
    write_temporal_event_detector_bundle,
)
from services.inference.training.temporal_student import (
    TemporalStudentTrainingExample as TemporalTrainingExample,
    _export_target,
    load_temporal_student_examples,
)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover
    torch = None
    nn = None
    F = None


DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED = 11


@dataclass(frozen=True)
class TemporalEventDetectorTrainingResult:
    bundle: TemporalEventDetectorBundle
    metrics: dict[str, Any]
    training_examples: int


if nn is not None:
    class TorchTemporalEventDetector(nn.Module):
        def __init__(self, input_size: int, hidden_size: int, architecture: str) -> None:
            super().__init__()
            self.architecture = architecture
            self.projection = nn.Linear(input_size, hidden_size)
            self.temporal_layers = nn.ModuleList()
            if architecture == "actionformer":
                self.temporal_layers.append(nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=1))
            elif architecture == "tridet":
                self.temporal_layers.append(nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=1))
                self.temporal_layers.append(nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=2, dilation=2))
            else:  # pragma: no cover - guarded by parse-time validation
                raise ValueError(f"Unsupported architecture: {architecture}")
            self.eventness_head = nn.Linear(hidden_size, 1)
            self.frame_family_head = nn.Linear(hidden_size, len(EVENT_FAMILIES))
            self.start_head = nn.Linear(hidden_size, 1)
            self.end_head = nn.Linear(hidden_size, 1)
            self.segment_attention = nn.Linear(hidden_size, 1)
            pooled_size = hidden_size * 4
            self.segment_family_head = nn.Linear(pooled_size, len(EVENT_FAMILIES))
            self.outcome_head = nn.Linear(pooled_size, len(OUTCOMES))
            self.shot_subtype_head = nn.Linear(pooled_size, len(SHOT_SUBTYPES))

        def forward(self, inputs: torch.Tensor, segment_mask: torch.Tensor) -> dict[str, torch.Tensor]:
            hidden = torch.tanh(self.projection(inputs))
            hidden_t = hidden.transpose(1, 2)
            if self.architecture == "actionformer":
                temporal_hidden = torch.tanh(self.temporal_layers[0](hidden_t)).transpose(1, 2)
            else:
                branches = [torch.tanh(layer(hidden_t)) for layer in self.temporal_layers]
                temporal_hidden = torch.tanh((hidden_t + sum(branches)) / float(len(branches) + 1)).transpose(1, 2)
            segment_mask = segment_mask.float()
            if segment_mask.dim() != 2:
                raise ValueError("Expected segment mask to have shape [batch, time].")
            expanded_mask = segment_mask.unsqueeze(-1)
            attention_logits = self.segment_attention(temporal_hidden).squeeze(-1)
            masked_attention_logits = attention_logits.masked_fill(segment_mask <= 0, -1e9)
            attention = torch.softmax(masked_attention_logits, dim=1)
            fallback_attention = torch.softmax(attention_logits, dim=1)
            use_fallback = (segment_mask.sum(dim=1, keepdim=True) <= 0).float()
            attention = (attention * (1.0 - use_fallback)) + (fallback_attention * use_fallback)
            weighted_mean = torch.sum(temporal_hidden * attention.unsqueeze(-1), dim=1)
            masked_hidden = temporal_hidden * expanded_mask
            pooled_max = torch.max(
                masked_hidden + ((1.0 - expanded_mask) * -1e9),
                dim=1,
            ).values
            pooled_max = torch.where(torch.isfinite(pooled_max), pooled_max, torch.max(temporal_hidden, dim=1).values)
            end_indices = torch.argmax(segment_mask, dim=1)
            has_segment = segment_mask.sum(dim=1) > 0
            end_indices = torch.where(has_segment, torch.argmax(torch.flip(segment_mask, dims=(1,)), dim=1), torch.full_like(end_indices, temporal_hidden.shape[1] - 1))
            end_indices = temporal_hidden.shape[1] - 1 - end_indices
            start_indices = torch.where(has_segment, torch.argmax(segment_mask, dim=1), torch.zeros_like(end_indices))
            batch_indices = torch.arange(temporal_hidden.shape[0], device=temporal_hidden.device)
            pooled_last = temporal_hidden[batch_indices, end_indices]
            pooled_first = temporal_hidden[batch_indices, start_indices]
            pooled_delta = pooled_last - pooled_first
            pooled = torch.cat([weighted_mean, pooled_max, pooled_last, pooled_delta], dim=-1)
            return {
                "hidden": temporal_hidden,
                "eventness": self.eventness_head(temporal_hidden).squeeze(-1),
                "frameFamily": self.frame_family_head(temporal_hidden),
                "start": self.start_head(temporal_hidden).squeeze(-1),
                "end": self.end_head(temporal_hidden).squeeze(-1),
                "segmentFamily": self.segment_family_head(pooled),
                "outcome": self.outcome_head(pooled),
                "shotSubtype": self.shot_subtype_head(pooled),
            }


def load_temporal_event_detector_examples(repo_root: Path) -> list[TemporalTrainingExample]:
    return load_temporal_student_examples(repo_root)


def train_temporal_event_detector_from_repo(
    repo_root: Path,
    *,
    architecture: str,
    output_path: Path | None = None,
    hidden_size: int = 18,
    epochs: int = 180,
    learning_rate: float = 0.02,
) -> TemporalEventDetectorTrainingResult:
    examples = load_temporal_event_detector_examples(repo_root)
    result = train_temporal_event_detector(
        examples,
        architecture=architecture,
        hidden_size=hidden_size,
        epochs=epochs,
        learning_rate=learning_rate,
    )
    if output_path is not None:
        write_temporal_event_detector_bundle(output_path, result.bundle)
    return result


def train_temporal_event_detector(
    examples: Sequence[TemporalTrainingExample],
    *,
    architecture: str,
    hidden_size: int = 18,
    epochs: int = 180,
    learning_rate: float = 0.02,
    random_seed: int = DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED,
) -> TemporalEventDetectorTrainingResult:
    if torch is None or nn is None or F is None:  # pragma: no cover
        raise RuntimeError("torch is required to train the temporal event detector")
    if not examples:
        raise ValueError("At least one training example is required.")

    np.random.seed(int(random_seed))
    torch.manual_seed(int(random_seed))
    if torch.cuda.is_available():  # pragma: no cover
        torch.cuda.manual_seed_all(int(random_seed))

    input_feature_names = derive_temporal_event_detector_feature_names(examples)
    dataset = build_training_tensors(examples, input_feature_names=input_feature_names)
    model = TorchTemporalEventDetector(len(input_feature_names), hidden_size, architecture)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    for _ in range(epochs):
        optimizer.zero_grad()
        logits = model(dataset["inputs"], dataset["segmentMask"])
        loss = compute_detector_loss(logits=logits, dataset=dataset)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits = model(dataset["inputs"], dataset["segmentMask"])
        metrics = compute_training_metrics(logits=logits, dataset=dataset)
    bundle = export_temporal_event_detector_bundle(
        model=model,
        input_feature_names=input_feature_names,
        architecture=architecture,
        source_dataset="perception_supervision+phase4_event_localization_queue+teacher_backed",
    )
    bundle = calibrate_temporal_event_detector_bundle(bundle, examples)
    return TemporalEventDetectorTrainingResult(
        bundle=bundle,
        metrics=metrics,
        training_examples=len(examples),
    )


def derive_temporal_event_detector_feature_names(
    examples: Sequence[TemporalTrainingExample],
) -> tuple[str, ...]:
    feature_names = set(default_temporal_event_detector_feature_names())
    for example in examples:
        for observation in example.observations:
            feature_names.update(build_temporal_event_detector_feature_map(observation).keys())
    return tuple(sorted(feature_names))


def build_training_tensors(
    examples: Sequence[TemporalTrainingExample],
    *,
    input_feature_names: Sequence[str],
) -> dict[str, Any]:
    if torch is None:  # pragma: no cover
        raise RuntimeError("torch is required to build temporal event detector tensors")
    sequence_lengths = [len(example.observations) for example in examples]
    if len(set(sequence_lengths)) != 1:
        raise ValueError("Temporal event detector examples must use a fixed observation count.")
    inputs = torch.tensor(
        [
            [
                [
                    float(vectorize_temporal_event_detector_observation(observation, input_feature_names)[feature_index])
                    for feature_index in range(len(input_feature_names))
                ]
                for observation in example.observations
            ]
            for example in examples
        ],
        dtype=torch.float32,
    )
    frame_event_targets = []
    frame_family_targets = []
    start_indices = []
    end_indices = []
    center_indices = []
    segment_masks = []
    event_mask = []
    shot_mask = []
    localization_mask = []
    weights = []
    outcome_targets = []
    subtype_targets = []
    family_targets = []
    for example in examples:
        target = derive_frame_targets(example)
        frame_event_targets.append(target["frameEventTargets"])
        frame_family_targets.append(target["frameFamilyTargets"])
        start_indices.append(target["startIndex"])
        end_indices.append(target["endIndex"])
        center_indices.append(target["centerIndex"])
        segment_masks.append(target["segmentMask"])
        event_mask.append(1.0 if example.event_family != "other" else 0.0)
        shot_mask.append(1.0 if example.event_family == "shot_attempt" else 0.0)
        localization_mask.append(1.0 if example.has_event_localization else 0.0)
        weights.append(float(max(example.weight, 0.0)))
        family_targets.append(EVENT_FAMILIES.index(example.event_family))
        outcome_targets.append(OUTCOMES.index(example.outcome))
        subtype_targets.append(SHOT_SUBTYPES.index(example.shot_subtype or "null"))
    return {
        "inputs": inputs,
        "frameEventTargets": torch.tensor(frame_event_targets, dtype=torch.float32),
        "frameFamilyTargets": torch.tensor(frame_family_targets, dtype=torch.long),
        "startIndices": torch.tensor(start_indices, dtype=torch.long),
        "endIndices": torch.tensor(end_indices, dtype=torch.long),
        "centerIndices": torch.tensor(center_indices, dtype=torch.long),
        "segmentMask": torch.tensor(segment_masks, dtype=torch.float32),
        "weights": torch.tensor(weights, dtype=torch.float32),
        "eventMask": torch.tensor(event_mask, dtype=torch.float32),
        "shotMask": torch.tensor(shot_mask, dtype=torch.float32),
        "localizationMask": torch.tensor(localization_mask, dtype=torch.float32),
        "familyTargets": torch.tensor(family_targets, dtype=torch.long),
        "outcomeTargets": torch.tensor(outcome_targets, dtype=torch.long),
        "subtypeTargets": torch.tensor(subtype_targets, dtype=torch.long),
    }


def derive_frame_targets(example: TemporalTrainingExample) -> dict[str, Any]:
    timestamps = [float(observation.timestamp_seconds) for observation in example.observations]
    runtime = example.observations[0].runtime_features if example.observations else {}
    center_time = _resolve_time(
        runtime.get("eventCenterSeconds"),
        default=timestamps[len(timestamps) // 2],
    )
    start_time = _resolve_time(runtime.get("eventStartSeconds"), default=center_time)
    end_time = _resolve_time(runtime.get("eventEndSeconds"), default=center_time)
    if example.event_family != "other" and end_time < start_time:
        end_time = start_time
    if example.event_family != "other" and not example.has_event_localization:
        half_step = _median_step(timestamps) / 2.0
        start_time = max(center_time - half_step, timestamps[0])
        end_time = min(center_time + half_step, timestamps[-1])
    center_index = _closest_index(timestamps, center_time)
    start_index = _closest_index(timestamps, start_time)
    end_index = _closest_index(timestamps, end_time)
    if end_index < start_index:
        end_index = start_index
    segment_mask = [0.0 for _ in timestamps]
    frame_event_targets = [0.0 for _ in timestamps]
    frame_family_targets = [EVENT_FAMILIES.index("other") for _ in timestamps]
    if example.event_family != "other":
        for index in range(start_index, end_index + 1):
            segment_mask[index] = 1.0
            frame_event_targets[index] = 1.0
            frame_family_targets[index] = EVENT_FAMILIES.index(example.event_family)
        frame_event_targets[center_index] = 1.0
        frame_family_targets[center_index] = EVENT_FAMILIES.index(example.event_family)
    return {
        "frameEventTargets": frame_event_targets,
        "frameFamilyTargets": frame_family_targets,
        "startIndex": start_index,
        "endIndex": end_index,
        "centerIndex": center_index,
        "segmentMask": segment_mask,
    }


def compute_detector_loss(*, logits: dict[str, Any], dataset: dict[str, Any]):
    eventness_loss = F.binary_cross_entropy_with_logits(
        logits["eventness"],
        dataset["frameEventTargets"],
        reduction="none",
    )
    family_loss = F.cross_entropy(
        logits["frameFamily"].transpose(1, 2),
        dataset["frameFamilyTargets"],
        reduction="none",
    )
    pooled_family_loss = F.cross_entropy(logits["segmentFamily"], dataset["familyTargets"], reduction="none")
    outcome_loss = F.cross_entropy(logits["outcome"], dataset["outcomeTargets"], reduction="none")
    subtype_loss = F.cross_entropy(logits["shotSubtype"], dataset["subtypeTargets"], reduction="none")
    start_loss = F.cross_entropy(logits["start"], dataset["startIndices"], reduction="none")
    end_loss = F.cross_entropy(logits["end"], dataset["endIndices"], reduction="none")

    weights = dataset["weights"]
    event_mask = dataset["eventMask"]
    shot_mask = dataset["shotMask"]
    localization_mask = dataset["localizationMask"]
    negative_mask = 1.0 - event_mask
    frame_weights = weights.unsqueeze(1) * (1.15 + (0.45 * negative_mask.unsqueeze(1)) + (0.2 * localization_mask.unsqueeze(1)))
    frame_family_weights = weights.unsqueeze(1) * (1.0 + (0.25 * event_mask.unsqueeze(1)))
    eventness_loss = _focalize(eventness_loss, logits["eventness"], dataset["frameEventTargets"], gamma=2.0)
    weighted_eventness = (eventness_loss * frame_weights).sum() / torch.clamp(frame_weights.sum(), min=1e-6)
    weighted_frame_family = (family_loss * frame_family_weights).sum() / torch.clamp(frame_family_weights.sum(), min=1e-6)
    family_weights = weights * (1.0 + (0.25 * event_mask) + (0.15 * localization_mask))
    weighted_pooled_family = (pooled_family_loss * family_weights).sum() / torch.clamp(family_weights.sum(), min=1e-6)
    outcome_weights = weights * event_mask
    weighted_outcome = (outcome_loss * outcome_weights).sum() / torch.clamp(outcome_weights.sum(), min=1e-6)
    subtype_weights = weights * shot_mask
    weighted_subtype = (subtype_loss * subtype_weights).sum() / torch.clamp(subtype_weights.sum(), min=1e-6)
    boundary_weights = weights * event_mask * (1.0 + (0.5 * localization_mask))
    weighted_start = (start_loss * boundary_weights).sum() / torch.clamp(boundary_weights.sum(), min=1e-6)
    weighted_end = (end_loss * boundary_weights).sum() / torch.clamp(boundary_weights.sum(), min=1e-6)
    return (
        weighted_eventness
        + weighted_frame_family
        + weighted_pooled_family
        + weighted_outcome
        + weighted_subtype
        + (0.35 * weighted_start)
        + (0.35 * weighted_end)
    )


def _focalize(base_loss, logits, targets, *, gamma: float):
    probabilities = torch.sigmoid(logits)
    pt = torch.where(targets > 0.5, probabilities, 1.0 - probabilities)
    modulation = torch.pow(1.0 - pt, gamma)
    return base_loss * modulation


def compute_training_metrics(*, logits: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    frame_event_predictions = (torch.sigmoid(logits["eventness"]) >= 0.5).float()
    frame_family_predictions = torch.argmax(logits["frameFamily"], dim=-1)
    family_predictions = torch.argmax(logits["segmentFamily"], dim=-1)
    outcome_predictions = torch.argmax(logits["outcome"], dim=-1)
    subtype_predictions = torch.argmax(logits["shotSubtype"], dim=-1)
    metrics = {
        "frameEventAccuracy": round(float((frame_event_predictions == dataset["frameEventTargets"]).float().mean().item()), 4),
        "frameFamilyAccuracy": round(float((frame_family_predictions == dataset["frameFamilyTargets"]).float().mean().item()), 4),
        "segmentFamilyAccuracy": round(float((family_predictions == dataset["familyTargets"]).float().mean().item()), 4),
        "outcomeAccuracy": round(float((outcome_predictions == dataset["outcomeTargets"]).float().mean().item()), 4),
        "shotSubtypeAccuracy": round(float((subtype_predictions == dataset["subtypeTargets"]).float().mean().item()), 4),
    }
    return metrics


def evaluate_temporal_event_detector_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
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
        metadata = prediction.metadata or {}
        predicted_spotter_family = str(
            metadata.get("temporal_event_detector_event_family")
            or metadata.get("temporal_student_event_spotter_family")
            or prediction.eventFamily
            or "other"
        )
        rows.append(
            {
                "clipId": example.clip_id,
                "expectedEventFamily": example.event_family,
                "expectedOutcome": example.outcome,
                "expectedShotSubtype": example.shot_subtype or "null",
                "predictedSpotterFamily": predicted_spotter_family,
                "predictedSpotterLikelyEvent": bool(
                    metadata.get("temporal_event_detector_gate_open")
                    if "temporal_event_detector_gate_open" in metadata
                    else metadata.get("temporal_student_event_spotter_likely_event")
                ),
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
    labeled_rows = [row for row in rows if row["expectedEventFamily"] in EVENT_FAMILIES]
    true_positive = sum(
        1
        for row in labeled_rows
        if row["expectedEventFamily"] != "other" and row["predictedSpotterFamily"] != "other"
    )
    false_positive = sum(
        1
        for row in labeled_rows
        if row["expectedEventFamily"] == "other" and row["predictedSpotterFamily"] != "other"
    )
    false_negative = sum(
        1
        for row in labeled_rows
        if row["expectedEventFamily"] != "other" and row["predictedSpotterFamily"] == "other"
    )
    event_detection_precision = round(true_positive / max(true_positive + false_positive, 1), 4)
    event_detection_recall = round(true_positive / max(true_positive + false_negative, 1), 4)
    other_examples = [row for row in rows if row["predictedEventFamily"] == "other"]
    true_missed_events_in_other = sum(1 for row in other_examples if row["expectedEventFamily"] != "other")
    return {
        "eventFamilyAccuracy": event_family_accuracy,
        "outcomeAccuracy": outcome_accuracy,
        "shotSubtypeAccuracy": shot_subtype_accuracy,
        "uncertaintyRate": uncertainty_rate,
        "flatLabelSpread": len(flat_label_distribution),
        "flatLabelDistribution": flat_label_distribution,
        "eventFamilyDistribution": event_family_distribution,
        "outcomeDistribution": outcome_distribution,
        "shotSubtypeDistribution": subtype_distribution,
        "highlightDominance": highlight_dominance,
        "otherDominance": other_dominance,
        "missVsMadeConfusion": miss_vs_made_confusion,
        "eventSpotterPrecision": event_detection_precision,
        "eventSpotterRecall": event_detection_recall,
        "eventDetectionPrecision": event_detection_precision,
        "eventDetectionRecall": event_detection_recall,
        "eventDetectionLabeledRows": len(labeled_rows),
        "predictedOtherTrueMissRate": round(true_missed_events_in_other / max(len(other_examples), 1), 4),
        "evaluationRows": rows,
    }


def calibrate_temporal_event_detector_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> TemporalEventDetectorBundle:
    calibration_examples = [
        example
        for example in examples
        if example.source_kind == "gold" and example.split in {"val", "test"}
    ]
    if not calibration_examples:
        return bundle
    best_bundle = bundle
    best_metrics = evaluate_temporal_event_detector_bundle(bundle, calibration_examples)
    best_score = candidate_score(best_metrics)
    for threshold in (0.18, 0.22, 0.26, 0.3, 0.34, 0.38, 0.42):
        for margin in (0.02, 0.035, 0.05, 0.065, 0.08):
            candidate_bundle = replace(
                bundle,
                event_score_threshold=float(threshold),
                event_margin_threshold=float(margin),
            )
            metrics = evaluate_temporal_event_detector_bundle(candidate_bundle, calibration_examples)
            score = candidate_score(metrics)
            if score <= best_score:
                continue
            best_bundle = candidate_bundle
            best_metrics = metrics
            best_score = score
    return best_bundle


def export_temporal_event_detector_bundle(
    *,
    model,
    input_feature_names: Sequence[str],
    architecture: str,
    source_dataset: str,
) -> TemporalEventDetectorBundle:
    projection_weight = tuple(tuple(float(value) for value in row) for row in model.projection.weight.detach().cpu().numpy().tolist())
    projection_bias = tuple(float(value) for value in model.projection.bias.detach().cpu().numpy().tolist())
    temporal_layers = tuple(
        TemporalConvLayer(
            weight=tuple(
                tuple(tuple(float(value) for value in kernel) for kernel in channel)
                for channel in layer.weight.detach().cpu().numpy().tolist()
            ),
            bias=tuple(float(value) for value in layer.bias.detach().cpu().numpy().tolist()),
            dilation=int(layer.dilation[0]),
        )
        for layer in model.temporal_layers
    )
    return TemporalEventDetectorBundle(
        schema_version="temporal-event-detector-v1",
        feature_schema_version="temporal-event-detector-feature-v1",
        model_version=f"temporal-event-detector-{architecture}-v1",
        detector_family=architecture,
        trained_at=datetime.now(timezone.utc).isoformat(),
        source_dataset=source_dataset,
        notes=(
            f"{architecture} temporal detector over structured basketball signals, perception features, and clip-runtime cues.",
            "A first-stage detector predicts event family and segment boundaries before outcome/subtype gating.",
            "Outcome and subtype remain gated on confident detector output to avoid Highlight/other collapse from false positives.",
        ),
        input_feature_names=tuple(input_feature_names),
        hidden_size=int(model.projection.out_features),
        projection_weight=projection_weight,
        projection_bias=projection_bias,
        temporal_layers=temporal_layers,
        segment_attention_weight=tuple(float(value) for value in model.segment_attention.weight.detach().cpu().numpy()[0].tolist()),
        segment_attention_bias=float(model.segment_attention.bias.detach().cpu().numpy()[0]),
        eventness_weight=tuple(float(value) for value in model.eventness_head.weight.detach().cpu().numpy()[0].tolist()),
        eventness_bias=float(model.eventness_head.bias.detach().cpu().numpy()[0]),
        frame_family_weight=tuple(
            tuple(float(value) for value in row)
            for row in model.frame_family_head.weight.detach().cpu().numpy().tolist()
        ),
        frame_family_bias=tuple(float(value) for value in model.frame_family_head.bias.detach().cpu().numpy().tolist()),
        start_weight=tuple(float(value) for value in model.start_head.weight.detach().cpu().numpy()[0].tolist()),
        start_bias=float(model.start_head.bias.detach().cpu().numpy()[0]),
        end_weight=tuple(float(value) for value in model.end_head.weight.detach().cpu().numpy()[0].tolist()),
        end_bias=float(model.end_head.bias.detach().cpu().numpy()[0]),
        event_score_threshold=0.38 if architecture == "actionformer" else 0.36,
        event_margin_threshold=0.05 if architecture == "actionformer" else 0.045,
        targets={
            "eventFamily": _export_target(
                name="eventFamily",
                labels=EVENT_FAMILIES,
                weight_matrix=model.segment_family_head.weight.detach().cpu().numpy(),
                bias_vector=model.segment_family_head.bias.detach().cpu().numpy(),
            ),
            "outcome": _export_target(
                name="outcome",
                labels=OUTCOMES,
                weight_matrix=model.outcome_head.weight.detach().cpu().numpy(),
                bias_vector=model.outcome_head.bias.detach().cpu().numpy(),
            ),
            "shotSubtype": _export_target(
                name="shotSubtype",
                labels=SHOT_SUBTYPES,
                weight_matrix=model.shot_subtype_head.weight.detach().cpu().numpy(),
                bias_vector=model.shot_subtype_head.bias.detach().cpu().numpy(),
            ),
        },
    )


def build_temporal_event_detector_report(
    *,
    baseline_metrics: dict[str, Any],
    actionformer_metrics: dict[str, Any],
    tridet_metrics: dict[str, Any],
    winner: str,
) -> str:
    lines = [
        "# Temporal Event Detector Candidates",
        "",
        f"- Winner: `{winner}`",
        "",
        "## Candidate Metrics",
    ]
    for name, metrics in (
        ("phase4bBaseline", baseline_metrics),
        ("actionformer", actionformer_metrics),
        ("tridet", tridet_metrics),
    ):
        lines.extend(
            [
                f"### {name}",
                f"- eventFamilyAccuracy: `{metrics.get('eventFamilyAccuracy')}`",
                f"- outcomeAccuracy: `{metrics.get('outcomeAccuracy')}`",
                f"- shotSubtypeAccuracy: `{metrics.get('shotSubtypeAccuracy')}`",
                f"- eventDetectionPrecision / Recall: `{metrics.get('eventDetectionPrecision')}` / `{metrics.get('eventDetectionRecall')}`",
                f"- uncertaintyRate: `{metrics.get('uncertaintyRate')}`",
                f"- highlightDominance: `{metrics.get('highlightDominance')}`",
                f"- otherDominance: `{metrics.get('otherDominance')}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def candidate_score(metrics: dict[str, Any]) -> float:
    return (
        float(metrics.get("eventFamilyAccuracy", 0.0))
        + float(metrics.get("outcomeAccuracy", 0.0))
        + float(metrics.get("eventDetectionPrecision", 0.0))
        + float(metrics.get("eventDetectionRecall", 0.0))
        + (0.4 * float(metrics.get("shotSubtypeAccuracy", 0.0)))
        - float(metrics.get("uncertaintyRate", 0.0))
        - (0.6 * float(metrics.get("highlightDominance", 0.0)))
        - (0.6 * float(metrics.get("otherDominance", 0.0)))
    )


def _resolve_time(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _closest_index(timestamps: Sequence[float], target: float) -> int:
    return min(range(len(timestamps)), key=lambda index: abs(float(timestamps[index]) - float(target)))


def _median_step(timestamps: Sequence[float]) -> float:
    if len(timestamps) < 2:
        return 0.75
    deltas = [max(float(timestamps[index + 1]) - float(timestamps[index]), 0.0) for index in range(len(timestamps) - 1)]
    sorted_deltas = sorted(delta for delta in deltas if delta > 0.0)
    if not sorted_deltas:
        return 0.75
    return float(sorted_deltas[len(sorted_deltas) // 2])

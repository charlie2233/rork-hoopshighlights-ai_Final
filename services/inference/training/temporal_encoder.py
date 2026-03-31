from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from services.inference.app.temporal_encoder import (
    EVENT_FAMILIES,
    MAX_TEMPORAL_TOPK,
    OUTCOMES,
    SHOT_SUBTYPES,
    TEMPORAL_ENCODER_SCHEMA_VERSION,
    TemporalObservation,
    TemporalEncoderBundle,
    TemporalTargetModel,
    build_temporal_feature_map,
    default_temporal_feature_names,
)
from services.inference.training.distilled_clip_encoder import load_distilled_clip_examples

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover - exercised only in non-ML environments
    torch = None
    nn = None
    F = None


TEMPORAL_ENCODER_MODEL_VERSION = "temporal-encoder-lite-v1"


@dataclass(frozen=True)
class TemporalTrainingExample:
    clip_id: str
    observations: tuple[TemporalObservation, ...]
    event_family: str
    outcome: str
    shot_subtype: str | None
    source_kind: str = "unknown"
    split: str = "train"
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "clipId": self.clip_id,
            "eventFamily": self.event_family,
            "outcome": self.outcome,
            "shotSubtype": self.shot_subtype,
            "weight": self.weight,
            "observations": [
                {
                    "timestampSeconds": observation.timestamp_seconds,
                    "structuredSignals": dict(observation.structured_signals),
                    "perceptionFeatures": dict(observation.perception_features),
                }
                for observation in self.observations
            ],
        }


@dataclass(frozen=True)
class TemporalTrainingResult:
    bundle: TemporalEncoderBundle
    metrics: dict[str, Any]
    training_examples: int


def load_temporal_training_examples(repo_root: Path) -> list[TemporalTrainingExample]:
    distilled_examples = load_distilled_clip_examples(repo_root)
    temporal_examples: list[TemporalTrainingExample] = []
    for example in distilled_examples:
        if example.ignored:
            continue
        temporal_examples.append(
            TemporalTrainingExample(
                clip_id=example.clip_id,
                observations=_synthesize_observations(example),
                event_family=example.event_family,
                outcome=example.outcome,
                shot_subtype=example.shot_subtype,
                source_kind=example.source_kind,
                split=example.split,
                weight=example.weight,
            )
        )
    return temporal_examples


def train_temporal_encoder_from_repo(
    repo_root: Path,
    *,
    output_path: Path | None = None,
    hidden_size: int = 12,
    epochs: int = 120,
    learning_rate: float = 0.03,
) -> TemporalTrainingResult:
    examples = load_temporal_training_examples(repo_root)
    result = train_temporal_encoder(
        examples,
        hidden_size=hidden_size,
        epochs=epochs,
        learning_rate=learning_rate,
    )
    if output_path is not None:
        write_temporal_encoder_bundle(output_path, result.bundle)
    return result


def _synthesize_observations(example) -> tuple[TemporalObservation, ...]:
    features = dict(example.features or {})
    runtime = dict(example.raw_runtime_outputs or {})
    clip_duration = _coerce_float(features.get("clipDurationSeconds"), default=4.5)
    signal_snapshot = {
        "ballNearRim": _coerce_float(features.get("ballNearRim"), default=0.0),
        "ballAboveRim": _signal_default(example.event_family, example.shot_subtype, "ballAboveRim"),
        "ballArcApex": _signal_default(example.event_family, example.shot_subtype, "ballArcApex"),
        "ballThroughHoopLikelihood": _coerce_float(features.get("ballThroughHoopLikelihood"), default=0.0),
        "possessionChangeLikelihood": _coerce_float(features.get("possessionChangeLikelihood"), default=0.0),
        "transitionLikelihood": _coerce_float(features.get("transitionLikelihood"), default=0.0),
        "playerToRimDistance": _signal_default(example.event_family, example.shot_subtype, "playerToRimDistance"),
        "ballCarrierSpeed": _signal_default(example.event_family, example.shot_subtype, "ballCarrierSpeed"),
        "transitionSpeedScore": _signal_default(example.event_family, example.shot_subtype, "transitionSpeedScore"),
        "defenderProximityAtShot": _signal_default(example.event_family, example.shot_subtype, "defenderProximityAtShot"),
        "shotReleaseCandidate": _signal_default(example.event_family, example.shot_subtype, "shotReleaseCandidate"),
        "samePlayContinuityScore": _signal_default(example.event_family, example.shot_subtype, "samePlayContinuityScore"),
    }
    perception = {
        "basketballConfidence": 0.92 if _coerce_float(features.get("ballVisible"), default=0.0) > 0.0 else 0.0,
        "rimConfidence": 0.9 if _coerce_float(features.get("hoopVisible"), default=0.0) > 0.0 else 0.0,
        "playerCount": 6.0 if example.event_family in {"shot_attempt", "transition", "turnover"} else 4.0,
        "trackedPlayerCount": 4.0 if example.event_family in {"shot_attempt", "transition"} else 2.0,
        "trackedBallConfidence": 0.88 if _coerce_float(features.get("ballVisible"), default=0.0) > 0.0 else 0.0,
    }
    phase_positions = (0.15, 0.45, 0.7, 0.9)
    phase_scales = (_phase_scale(example.event_family, example.outcome, position) for position in phase_positions)
    observations: list[TemporalObservation] = []
    for position, scales in zip(phase_positions, phase_scales):
        structured_signals = {
            key: _scaled_signal(signal_snapshot[key], scales.get(key, scales["default"]))
            for key in signal_snapshot
        }
        if example.event_family == "shot_attempt" and example.outcome == "made" and position >= 0.7:
            structured_signals["ballThroughHoopLikelihood"] = max(structured_signals["ballThroughHoopLikelihood"], 0.82)
        if example.event_family == "shot_attempt" and example.outcome == "missed" and position >= 0.7:
            structured_signals["ballThroughHoopLikelihood"] = min(structured_signals["ballThroughHoopLikelihood"], 0.18)
        if example.event_family == "turnover" and position >= 0.45:
            structured_signals["possessionChangeLikelihood"] = max(structured_signals["possessionChangeLikelihood"], 0.78)
        if example.event_family == "transition":
            structured_signals["transitionLikelihood"] = max(structured_signals["transitionLikelihood"], 0.72)
            structured_signals["transitionSpeedScore"] = max(structured_signals["transitionSpeedScore"], 0.68)
        observations.append(
            TemporalObservation(
                timestamp_seconds=round(position * clip_duration, 4),
                structured_signals=structured_signals,
                perception_features=dict(perception),
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
    return 0.0


def _scaled_signal(value: float | None, scale: float) -> float:
    return round(float(max(min((value or 0.0) * scale, 1.0), 0.0)), 4)


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed


if nn is not None:
    class TorchTemporalEncoder(nn.Module):
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


def train_temporal_encoder(
    examples: Sequence[TemporalTrainingExample],
    *,
    hidden_size: int = 12,
    epochs: int = 120,
    learning_rate: float = 0.03,
) -> TemporalTrainingResult:
    if torch is None or nn is None or F is None:  # pragma: no cover - depends on torch availability
        raise RuntimeError("torch is required to train the temporal encoder")
    if not examples:
        raise ValueError("At least one training example is required.")

    input_feature_names = default_temporal_feature_names()
    label_spaces = {
        "eventFamily": EVENT_FAMILIES,
        "outcome": OUTCOMES,
        "shotSubtype": SHOT_SUBTYPES,
    }
    dataset = build_training_tensors(examples, input_feature_names=input_feature_names)
    model = TorchTemporalEncoder(len(input_feature_names), hidden_size, label_spaces)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    for _ in range(epochs):
        optimizer.zero_grad()
        logits, _ = model(dataset["inputs"])
        loss = compute_temporal_loss(
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
    bundle = export_temporal_encoder_bundle(
        model=model,
        input_feature_names=input_feature_names,
        label_spaces=label_spaces,
        source_dataset="synthetic_or_runtime",
    )
    return TemporalTrainingResult(
        bundle=bundle,
        metrics=metrics,
        training_examples=len(examples),
    )


def evaluate_temporal_encoder_bundle(
    bundle: TemporalEncoderBundle,
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
    return {
        "eventFamilyAccuracy": event_family_accuracy,
        "outcomeAccuracy": outcome_accuracy,
        "shotSubtypeAccuracy": shot_subtype_accuracy,
        "uncertaintyRate": uncertainty_rate,
        "flatLabelSpread": flat_label_spread,
        "evaluationRows": rows,
    }


def build_training_tensors(
    examples: Sequence[TemporalTrainingExample],
    *,
    input_feature_names: Sequence[str],
) -> dict[str, Any]:
    if torch is None:  # pragma: no cover - depends on torch availability
        raise RuntimeError("torch is required to build training tensors")
    sequence_lengths = [len(example.observations) for example in examples]
    if len(set(sequence_lengths)) != 1:
        raise ValueError("Temporal training examples must be padded to equal length before training.")
    inputs = torch.tensor(
        [
            [
                [float(build_temporal_feature_map(observation).get(name, 0.0)) for name in input_feature_names]
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


def compute_temporal_loss(
    *,
    logits: dict[str, Any],
    targets: dict[str, Any],
    weights: Any,
    shot_mask: Any,
) -> Any:
    if F is None:  # pragma: no cover - depends on torch availability
        raise RuntimeError("torch is required to compute temporal loss")
    family_loss = F.cross_entropy(logits["eventFamily"], targets["eventFamily"], reduction="none")
    outcome_loss = F.cross_entropy(logits["outcome"], targets["outcome"], reduction="none")
    subtype_loss = F.cross_entropy(logits["shotSubtype"], targets["shotSubtype"], reduction="none") * shot_mask
    combined = (family_loss + outcome_loss + subtype_loss) * weights
    normalizer = max(float(torch.sum(weights).item()), 1e-6)
    return torch.sum(combined) / normalizer


def compute_training_metrics(
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


def export_temporal_encoder_bundle(
    *,
    model: Any,
    input_feature_names: Sequence[str],
    label_spaces: dict[str, tuple[str, ...]],
    source_dataset: str,
    model_version: str = TEMPORAL_ENCODER_MODEL_VERSION,
) -> TemporalEncoderBundle:
    if torch is None:  # pragma: no cover - depends on torch availability
        raise RuntimeError("torch is required to export the temporal encoder bundle")
    projection_weight = _to_nested_tuple(model.projection.weight.detach().cpu().numpy())
    projection_bias = tuple(float(value) for value in model.projection.bias.detach().cpu().numpy().tolist())
    attention_weight = tuple(float(value) for value in model.attention.weight.detach().cpu().numpy().reshape(-1).tolist())
    attention_bias = float(model.attention.bias.detach().cpu().numpy().reshape(-1)[0])
    pooled_size = model.event_family_head.weight.shape[1]
    target_models = {
        "eventFamily": build_target_model(
            name="eventFamily",
            classes=label_spaces["eventFamily"],
            weight=model.event_family_head.weight.detach().cpu().numpy(),
            bias=model.event_family_head.bias.detach().cpu().numpy(),
            top_k=MAX_TEMPORAL_TOPK,
        ),
        "outcome": build_target_model(
            name="outcome",
            classes=label_spaces["outcome"],
            weight=model.outcome_head.weight.detach().cpu().numpy(),
            bias=model.outcome_head.bias.detach().cpu().numpy(),
            top_k=MAX_TEMPORAL_TOPK,
        ),
        "shotSubtype": build_target_model(
            name="shotSubtype",
            classes=label_spaces["shotSubtype"],
            weight=model.shot_subtype_head.weight.detach().cpu().numpy(),
            bias=model.shot_subtype_head.bias.detach().cpu().numpy(),
            top_k=MAX_TEMPORAL_TOPK,
        ),
    }
    return TemporalEncoderBundle(
        schema_version=TEMPORAL_ENCODER_SCHEMA_VERSION,
        model_version=model_version,
        trained_at=datetime.now(timezone.utc).isoformat(),
        source_dataset=source_dataset,
        notes=(
            "Lightweight temporal encoder over structured basketball signals and perception features.",
            f"Projection hidden size={len(projection_bias)} pooled size={pooled_size}.",
        ),
        input_feature_names=tuple(str(name) for name in input_feature_names),
        hidden_size=len(projection_bias),
        projection_weight=projection_weight,
        projection_bias=projection_bias,
        attention_weight=attention_weight,
        attention_bias=attention_bias,
        targets=target_models,
    )


def write_temporal_encoder_bundle(path: Path, bundle: TemporalEncoderBundle) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": bundle.schema_version,
        "modelVersion": bundle.model_version,
        "trainedAt": bundle.trained_at,
        "sourceDataset": bundle.source_dataset,
        "notes": list(bundle.notes),
        "inputFeatureNames": list(bundle.input_feature_names),
        "hiddenSize": bundle.hidden_size,
        "projection": {
            "weight": [list(row) for row in bundle.projection_weight],
            "bias": list(bundle.projection_bias),
        },
        "attention": {
            "weight": list(bundle.attention_weight),
            "bias": bundle.attention_bias,
        },
        "targets": {
            name: {
                "classes": list(model.classes),
                "weight": [list(row) for row in model.weight],
                "bias": list(model.bias),
                "temperature": model.temperature,
                "uncertaintyThreshold": model.uncertainty_threshold,
                "marginThreshold": model.margin_threshold,
                "topK": model.top_k,
            }
            for name, model in bundle.targets.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_target_model(
    *,
    name: str,
    classes: Sequence[str],
    weight: np.ndarray,
    bias: np.ndarray,
    top_k: int,
) -> TemporalTargetModel:
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


def _to_nested_tuple(array: np.ndarray) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(value) for value in row.tolist()) for row in array)

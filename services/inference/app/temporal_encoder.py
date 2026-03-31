from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .models import ActionPrediction, LabelScore
from .runtime_model import derive_runtime_display_label


TEMPORAL_ENCODER_SCHEMA_VERSION = "temporal-encoder-v1"
TEMPORAL_ENCODER_BUNDLE_PATH = Path(__file__).resolve().parents[1] / "models" / "temporal_encoder_v1.json"
MAX_TEMPORAL_TOPK = 3

EVENT_FAMILIES = ("shot_attempt", "turnover", "defensive_event", "transition", "other")
OUTCOMES = ("made", "missed", "blocked", "uncertain")
SHOT_SUBTYPES = ("dunk", "layup", "jumper", "three", "putback", "null")


@dataclass(frozen=True)
class TemporalObservation:
    timestamp_seconds: float
    structured_signals: dict[str, Any]
    perception_features: dict[str, Any]


@dataclass(frozen=True)
class TemporalTargetPrediction:
    label: str
    confidence: float
    margin: float
    distribution: dict[str, float]
    top_labels: tuple[LabelScore, ...]
    is_uncertain: bool


@dataclass(frozen=True)
class TemporalTargetModel:
    name: str
    classes: tuple[str, ...]
    weight: tuple[tuple[float, ...], ...]
    bias: tuple[float, ...]
    temperature: float
    uncertainty_threshold: float
    margin_threshold: float
    top_k: int = MAX_TEMPORAL_TOPK

    def predict(self, pooled_vector: np.ndarray, *, model_version: str) -> TemporalTargetPrediction:
        logits = np.matmul(np.asarray(self.weight, dtype=np.float64), pooled_vector) + np.asarray(
            self.bias,
            dtype=np.float64,
        )
        probabilities = _softmax(logits / max(self.temperature, 1e-3))
        ranked = list(np.argsort(probabilities)[::-1])
        top_index = ranked[0]
        second_probability = float(probabilities[ranked[1]]) if len(ranked) > 1 else 0.0
        top_probability = float(probabilities[top_index])
        margin = max(top_probability - second_probability, 0.0)
        is_uncertain = top_probability < self.uncertainty_threshold or margin < self.margin_threshold
        distribution = {
            str(label): round(float(probabilities[index]), 4)
            for index, label in enumerate(self.classes)
        }
        top_labels = tuple(
            LabelScore(
                label=str(self.classes[index]),
                confidence=round(float(probabilities[index]), 4),
                modelVersion=model_version,
            )
            for index in ranked[: self.top_k]
        )
        return TemporalTargetPrediction(
            label=str(self.classes[top_index]),
            confidence=round(top_probability, 4),
            margin=round(margin, 4),
            distribution=distribution,
            top_labels=top_labels,
            is_uncertain=is_uncertain,
        )


@dataclass(frozen=True)
class TemporalEncoderBundle:
    schema_version: str
    model_version: str
    trained_at: str
    source_dataset: str
    notes: tuple[str, ...]
    input_feature_names: tuple[str, ...]
    hidden_size: int
    projection_weight: tuple[tuple[float, ...], ...]
    projection_bias: tuple[float, ...]
    attention_weight: tuple[float, ...]
    attention_bias: float
    targets: dict[str, TemporalTargetModel]

    def encode_observations(self, observations: Sequence[TemporalObservation]) -> tuple[np.ndarray, np.ndarray]:
        if not observations:
            raise ValueError("At least one temporal observation is required.")
        frame_matrix = np.asarray(
            [vectorize_temporal_observation(observation, self.input_feature_names) for observation in observations],
            dtype=np.float64,
        )
        hidden = np.tanh(
            np.matmul(frame_matrix, np.asarray(self.projection_weight, dtype=np.float64).T)
            + np.asarray(self.projection_bias, dtype=np.float64)
        )
        attention_logits = np.matmul(hidden, np.asarray(self.attention_weight, dtype=np.float64)) + float(self.attention_bias)
        attention = _softmax(attention_logits)
        return hidden, attention

    def pool_hidden_states(self, hidden: np.ndarray, attention: np.ndarray) -> np.ndarray:
        weighted_mean = np.sum(hidden * attention[:, np.newaxis], axis=0)
        pooled_max = np.max(hidden, axis=0)
        pooled_last = hidden[-1]
        pooled_delta = hidden[-1] - hidden[0]
        return np.concatenate([weighted_mean, pooled_max, pooled_last, pooled_delta], axis=0)

    def predict(self, observations: Sequence[TemporalObservation]) -> ActionPrediction:
        hidden, attention = self.encode_observations(observations)
        pooled = self.pool_hidden_states(hidden, attention)
        family_prediction = self.targets["eventFamily"].predict(pooled, model_version=self.model_version)
        outcome_prediction = self.targets["outcome"].predict(pooled, model_version=self.model_version)
        subtype_prediction = self.targets["shotSubtype"].predict(pooled, model_version=self.model_version)

        event_family = family_prediction.label if not family_prediction.is_uncertain else "other"
        outcome = _resolve_temporal_outcome(event_family, outcome_prediction)
        shot_subtype: str | None = None
        if event_family == "shot_attempt" and not subtype_prediction.is_uncertain and subtype_prediction.label != "null":
            shot_subtype = subtype_prediction.label

        canonical_label, display_label = derive_runtime_display_label(
            event_family=event_family,
            outcome=outcome,
            shot_subtype=shot_subtype,
        )
        is_uncertain = (
            family_prediction.is_uncertain
            or outcome_prediction.is_uncertain
            or (event_family == "shot_attempt" and shot_subtype is None and outcome != "made")
            or display_label == "Highlight"
        )
        confidence_before_mapping = family_prediction.confidence
        confidence_after_mapping = round(
            _resolve_temporal_confidence(
                display_label=display_label,
                family_prediction=family_prediction,
                outcome_prediction=outcome_prediction,
                subtype_prediction=subtype_prediction,
                is_uncertain=is_uncertain,
            ),
            4,
        )
        metadata = {
            "temporal_encoder_model_version": self.model_version,
            "temporal_encoder_schema_version": self.schema_version,
            "temporal_encoder_frame_count": len(observations),
            "temporal_encoder_attention": [round(float(value), 4) for value in attention.tolist()],
            "temporal_encoder_family_distribution": family_prediction.distribution,
            "temporal_encoder_outcome_distribution": outcome_prediction.distribution,
            "temporal_encoder_subtype_distribution": subtype_prediction.distribution,
            "temporal_encoder_family_top_labels": [item.model_dump(mode="json") for item in family_prediction.top_labels],
            "temporal_encoder_outcome_top_labels": [item.model_dump(mode="json") for item in outcome_prediction.top_labels],
            "temporal_encoder_subtype_top_labels": [item.model_dump(mode="json") for item in subtype_prediction.top_labels],
        }
        return ActionPrediction(
            label=display_label,
            canonicalLabel=canonical_label,
            confidence=confidence_after_mapping,
            modelVersion=self.model_version,
            detectionMethod="temporal_encoder",
            topLabels=list(family_prediction.top_labels),
            eventFamily=event_family,
            shotSubtype=shot_subtype,
            outcome=outcome,
            confidenceBeforeMapping=round(confidence_before_mapping, 4),
            confidenceAfterMapping=confidence_after_mapping,
            eventFamilyConfidenceBeforeMapping=family_prediction.confidence,
            eventFamilyConfidenceAfterMapping=round(
                max(family_prediction.confidence - (0.08 if family_prediction.is_uncertain else 0.0), 0.0),
                4,
            ),
            shotSubtypeConfidenceBeforeMapping=subtype_prediction.confidence if shot_subtype is not None else None,
            shotSubtypeConfidenceAfterMapping=(
                round(max(subtype_prediction.confidence - (0.06 if subtype_prediction.is_uncertain else 0.0), 0.0), 4)
                if shot_subtype is not None
                else None
            ),
            outcomeConfidenceBeforeMapping=outcome_prediction.confidence,
            outcomeConfidenceAfterMapping=round(
                max(outcome_prediction.confidence - (0.06 if outcome_prediction.is_uncertain else 0.0), 0.0),
                4,
            ),
            isUncertain=is_uncertain,
            metadata=metadata,
        )


def vectorize_temporal_observation(
    observation: TemporalObservation,
    input_feature_names: Sequence[str],
) -> np.ndarray:
    feature_values = build_temporal_feature_map(observation)
    return np.asarray([float(feature_values.get(name, 0.0)) for name in input_feature_names], dtype=np.float64)


def build_temporal_feature_map(observation: TemporalObservation) -> dict[str, float]:
    structured = observation.structured_signals or {}
    perception = observation.perception_features or {}
    return {
        "timestamp_seconds": float(observation.timestamp_seconds),
        "ball_near_rim": _coerce_float(structured.get("ballNearRim")),
        "ball_above_rim": _coerce_float(structured.get("ballAboveRim")),
        "ball_arc_apex": _coerce_float(structured.get("ballArcApex")),
        "ball_through_hoop_likelihood": _coerce_float(structured.get("ballThroughHoopLikelihood")),
        "possession_change_likelihood": _coerce_float(structured.get("possessionChangeLikelihood")),
        "transition_likelihood": _coerce_float(structured.get("transitionLikelihood")),
        "player_to_rim_distance": _coerce_float(structured.get("playerToRimDistance")),
        "ball_carrier_speed": _coerce_float(structured.get("ballCarrierSpeed")),
        "transition_speed_score": _coerce_float(structured.get("transitionSpeedScore")),
        "defender_proximity_at_shot": _coerce_float(structured.get("defenderProximityAtShot")),
        "shot_release_candidate": _coerce_float(structured.get("shotReleaseCandidate")),
        "same_play_continuity_score": _coerce_float(structured.get("samePlayContinuityScore")),
        "basketball_confidence": _coerce_float(perception.get("basketballConfidence", perception.get("ballConfidence"))),
        "rim_confidence": _coerce_float(perception.get("rimConfidence", perception.get("hoopConfidence"))),
        "player_count": _coerce_float(perception.get("playerCount")),
        "tracked_player_count": _coerce_float(perception.get("trackedPlayerCount")),
        "tracked_ball_confidence": _coerce_float(perception.get("trackedBallConfidence")),
    }


def load_temporal_encoder_bundle(path: Path | None = None) -> TemporalEncoderBundle:
    bundle_path = path or TEMPORAL_ENCODER_BUNDLE_PATH
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    targets = {
        str(target_name): TemporalTargetModel(
            name=str(target_name),
            classes=tuple(str(item) for item in target_payload.get("classes", [])),
            weight=tuple(tuple(float(value) for value in row) for row in target_payload.get("weight", [])),
            bias=tuple(float(value) for value in target_payload.get("bias", [])),
            temperature=float(target_payload.get("temperature", 1.0)),
            uncertainty_threshold=float(target_payload.get("uncertaintyThreshold", 0.45)),
            margin_threshold=float(target_payload.get("marginThreshold", 0.05)),
            top_k=int(target_payload.get("topK", MAX_TEMPORAL_TOPK)),
        )
        for target_name, target_payload in (payload.get("targets") or {}).items()
    }
    return TemporalEncoderBundle(
        schema_version=str(payload.get("schemaVersion", TEMPORAL_ENCODER_SCHEMA_VERSION)),
        model_version=str(payload.get("modelVersion", "temporal-encoder-v1")),
        trained_at=str(payload.get("trainedAt", "")),
        source_dataset=str(payload.get("sourceDataset", "")),
        notes=tuple(str(item) for item in payload.get("notes", []) if item is not None),
        input_feature_names=tuple(str(item) for item in payload.get("inputFeatureNames", [])),
        hidden_size=int(payload.get("hiddenSize", 0)),
        projection_weight=tuple(tuple(float(value) for value in row) for row in payload.get("projection", {}).get("weight", [])),
        projection_bias=tuple(float(value) for value in payload.get("projection", {}).get("bias", [])),
        attention_weight=tuple(float(value) for value in payload.get("attention", {}).get("weight", [])),
        attention_bias=float(payload.get("attention", {}).get("bias", 0.0)),
        targets=targets,
    )


@lru_cache(maxsize=1)
def get_temporal_encoder_bundle(path: str | None = None) -> TemporalEncoderBundle | None:
    bundle_path = Path(path) if path else TEMPORAL_ENCODER_BUNDLE_PATH
    if not bundle_path.exists():
        return None
    return load_temporal_encoder_bundle(bundle_path)


def default_temporal_feature_names() -> tuple[str, ...]:
    return (
        "timestamp_seconds",
        "ball_near_rim",
        "ball_above_rim",
        "ball_arc_apex",
        "ball_through_hoop_likelihood",
        "possession_change_likelihood",
        "transition_likelihood",
        "player_to_rim_distance",
        "ball_carrier_speed",
        "transition_speed_score",
        "defender_proximity_at_shot",
        "shot_release_candidate",
        "same_play_continuity_score",
        "basketball_confidence",
        "rim_confidence",
        "player_count",
        "tracked_player_count",
        "tracked_ball_confidence",
    )


def _resolve_temporal_outcome(event_family: str, prediction: TemporalTargetPrediction) -> str:
    if event_family == "defensive_event":
        return "blocked" if prediction.label == "blocked" and not prediction.is_uncertain else "uncertain"
    if event_family != "shot_attempt":
        return "uncertain"
    if prediction.is_uncertain:
        return "uncertain"
    return prediction.label


def _resolve_temporal_confidence(
    *,
    display_label: str,
    family_prediction: TemporalTargetPrediction,
    outcome_prediction: TemporalTargetPrediction,
    subtype_prediction: TemporalTargetPrediction,
    is_uncertain: bool,
) -> float:
    confidence = family_prediction.confidence
    if display_label in {"Dunk", "Layup", "Three Pointer"}:
        confidence = max(confidence, subtype_prediction.confidence)
    elif display_label == "Made Shot":
        confidence = min(max(confidence, subtype_prediction.confidence), max(outcome_prediction.confidence, 0.3))
    elif display_label == "Block":
        confidence = max(confidence, outcome_prediction.confidence)
    if is_uncertain:
        confidence -= 0.08
    return min(max(confidence, 0.0), 1.0)


def _softmax(logits: np.ndarray) -> np.ndarray:
    logits = np.asarray(logits, dtype=np.float64)
    if logits.ndim != 1:
        raise ValueError("Expected 1D logits.")
    shifted = logits - np.max(logits)
    exp_logits = np.exp(shifted)
    denominator = np.sum(exp_logits)
    if denominator <= 0.0:
        return np.ones_like(exp_logits) / max(len(exp_logits), 1)
    return exp_logits / denominator


def _coerce_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

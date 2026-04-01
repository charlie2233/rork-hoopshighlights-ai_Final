from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from services.inference.app.models import ActionPrediction, LabelScore
from services.inference.app.runtime_model import derive_runtime_display_label
from services.inference.app.temporal_encoder import TemporalTargetModel
from services.inference.app.runtime_models.temporal_student import (
    CONDITIONED_OUTCOME_LABELS,
    CONDITIONED_SUBTYPE_LABELS,
    EVENT_FAMILIES,
    OUTCOMES,
    SHOT_SUBTYPES,
    TemporalStudentObservation,
    TemporalStudentTargetPrediction,
    _classify_other_bucket,
    _fallback_temporal_prediction,
    _predict_conditioned_target,
    _resolve_student_confidence,
    build_temporal_student_feature_map,
    default_temporal_student_feature_names,
)


TEMPORAL_EVENT_DETECTOR_SCHEMA_VERSION = "temporal-event-detector-v1"
TEMPORAL_EVENT_DETECTOR_FEATURE_SCHEMA_VERSION = "temporal-event-detector-feature-v1"
TEMPORAL_EVENT_DETECTOR_MODEL_VERSION = "temporal-event-detector-actionformer-v1"
TEMPORAL_EVENT_DETECTOR_BUNDLE_PATH = (
    Path(__file__).resolve().parents[2] / "models" / "temporal_event_detector_v1.json"
)
MAX_TEMPORAL_EVENT_DETECTOR_TOPK = 3
TEMPORAL_EVENT_DETECTOR_EXCLUDED_FEATURE_PREFIXES = (
    "runtime_label",
    "runtime_display_label",
    "runtime_event_family",
    "runtime_outcome",
    "runtime_shot_subtype",
)
TEMPORAL_EVENT_DETECTOR_EXCLUDED_FEATURES = {
    "runtime_confidence",
}


@dataclass(frozen=True)
class TemporalConvLayer:
    weight: tuple[tuple[tuple[float, ...], ...], ...]
    bias: tuple[float, ...]
    dilation: int


@dataclass(frozen=True)
class TemporalEventDetectorBundle:
    schema_version: str
    feature_schema_version: str
    model_version: str
    detector_family: str
    trained_at: str
    source_dataset: str
    notes: tuple[str, ...]
    input_feature_names: tuple[str, ...]
    hidden_size: int
    projection_weight: tuple[tuple[float, ...], ...]
    projection_bias: tuple[float, ...]
    temporal_layers: tuple[TemporalConvLayer, ...]
    segment_attention_weight: tuple[float, ...]
    segment_attention_bias: float
    eventness_weight: tuple[float, ...]
    eventness_bias: float
    frame_family_weight: tuple[tuple[float, ...], ...]
    frame_family_bias: tuple[float, ...]
    start_weight: tuple[float, ...]
    start_bias: float
    end_weight: tuple[float, ...]
    end_bias: float
    event_score_threshold: float
    event_margin_threshold: float
    targets: dict[str, TemporalTargetModel]

    def predict(self, observations: Sequence[TemporalStudentObservation]) -> ActionPrediction:
        if not observations:
            raise ValueError("At least one temporal detector observation is required.")
        hidden = self.encode_observations(observations)
        frame_family_probabilities = _softmax_rows(
            np.matmul(hidden, np.asarray(self.frame_family_weight, dtype=np.float64).T)
            + np.asarray(self.frame_family_bias, dtype=np.float64),
        )
        eventness = _sigmoid(
            np.matmul(hidden, np.asarray(self.eventness_weight, dtype=np.float64))
            + float(self.eventness_bias),
        )
        start_scores = _softmax(
            np.matmul(hidden, np.asarray(self.start_weight, dtype=np.float64)) + float(self.start_bias)
        )
        end_scores = _softmax(
            np.matmul(hidden, np.asarray(self.end_weight, dtype=np.float64)) + float(self.end_bias)
        )

        center_index, spotted_event_family, event_spotter_prediction, best_event_score = self._spot_event(
            frame_family_probabilities=frame_family_probabilities,
            eventness=eventness,
            start_scores=start_scores,
            end_scores=end_scores,
        )
        gate_open = not event_spotter_prediction.is_uncertain and spotted_event_family != "other"
        start_index = 0
        end_index = len(observations) - 1
        if gate_open:
            start_index = int(np.argmax(start_scores[: center_index + 1]))
            end_index = int(center_index + np.argmax(end_scores[center_index:]))
            if end_index < start_index:
                end_index = start_index

        pooled, segment_attention = self._pool_segment(hidden, start_index=start_index, end_index=end_index)
        family_prediction = _predict_conditioned_target(
            self.targets["eventFamily"],
            pooled,
            model_version=self.model_version,
            allowed_labels=EVENT_FAMILIES if gate_open else ("other",),
        )
        if gate_open:
            if family_prediction.is_uncertain or family_prediction.label == "other":
                event_family = spotted_event_family
            else:
                event_family = family_prediction.label
            outcome_prediction = _predict_conditioned_target(
                self.targets["outcome"],
                pooled,
                model_version=self.model_version,
                allowed_labels=CONDITIONED_OUTCOME_LABELS.get(event_family, OUTCOMES),
            )
            subtype_prediction = _predict_conditioned_target(
                self.targets["shotSubtype"],
                pooled,
                model_version=self.model_version,
                allowed_labels=CONDITIONED_SUBTYPE_LABELS.get(event_family, SHOT_SUBTYPES),
            )
            outcome = _resolve_outcome(event_family, outcome_prediction)
        else:
            event_family = "other"
            family_prediction = _fallback_temporal_prediction(
                label="other",
                confidence=event_spotter_prediction.confidence,
                model_version=self.model_version,
            )
            outcome_prediction = _fallback_temporal_prediction(
                label="uncertain",
                confidence=event_spotter_prediction.confidence,
                model_version=self.model_version,
            )
            subtype_prediction = _fallback_temporal_prediction(
                label="null",
                confidence=event_spotter_prediction.confidence,
                model_version=self.model_version,
            )
            outcome = "uncertain"

        shot_subtype: str | None = None
        if gate_open and event_family == "shot_attempt" and not subtype_prediction.is_uncertain and subtype_prediction.label != "null":
            shot_subtype = subtype_prediction.label

        canonical_label, display_label = derive_runtime_display_label(
            event_family=event_family,
            outcome=outcome,
            shot_subtype=shot_subtype,
        )
        is_uncertain = (
            event_spotter_prediction.is_uncertain
            or (gate_open and family_prediction.is_uncertain)
            or (gate_open and outcome_prediction.is_uncertain)
            or (gate_open and event_family == "shot_attempt" and shot_subtype is None and outcome != "made")
            or (gate_open and display_label == "Highlight")
        )
        confidence_before_mapping = event_spotter_prediction.confidence if not gate_open else max(
            event_spotter_prediction.confidence,
            family_prediction.confidence,
        )
        confidence_after_mapping = round(
            _resolve_student_confidence(
                display_label=display_label,
                event_spotter_prediction=event_spotter_prediction,
                family_prediction=family_prediction,
                outcome_prediction=outcome_prediction,
                subtype_prediction=subtype_prediction,
                gate_open=gate_open,
                is_uncertain=is_uncertain,
            ),
            4,
        )
        other_bucket, other_bucket_reason, other_bucket_scores = _classify_other_bucket(
            observations=observations,
            event_family=event_family,
            event_spotter_prediction=event_spotter_prediction,
            family_prediction=family_prediction,
        )
        metadata = {
            "temporal_event_detector_model_version": self.model_version,
            "temporal_event_detector_schema_version": self.schema_version,
            "temporal_event_detector_feature_schema_version": self.feature_schema_version,
            "temporal_event_detector_family": self.detector_family,
            "temporal_event_detector_frame_count": len(observations),
            "temporal_event_detector_segment": {
                "startIndex": start_index,
                "centerIndex": center_index,
                "endIndex": end_index,
                "startSeconds": round(float(observations[start_index].timestamp_seconds), 4),
                "centerSeconds": round(float(observations[center_index].timestamp_seconds), 4),
                "endSeconds": round(float(observations[end_index].timestamp_seconds), 4),
            },
            "temporal_event_detector_event_score": round(best_event_score, 4),
            "temporal_event_detector_eventness": [round(float(value), 4) for value in eventness.tolist()],
            "temporal_event_detector_start_scores": [round(float(value), 4) for value in start_scores.tolist()],
            "temporal_event_detector_end_scores": [round(float(value), 4) for value in end_scores.tolist()],
            "temporal_event_detector_segment_attention": [round(float(value), 4) for value in segment_attention.tolist()],
            "temporal_event_detector_event_family": spotted_event_family,
            "temporal_event_detector_gate_open": gate_open,
            "temporal_event_detector_family_distribution": family_prediction.distribution,
            "temporal_event_detector_outcome_distribution": outcome_prediction.distribution,
            "temporal_event_detector_subtype_distribution": subtype_prediction.distribution,
            "temporal_event_detector_family_top_labels": [
                item.model_dump(mode="json") for item in family_prediction.top_labels
            ],
            "temporal_event_detector_outcome_top_labels": [
                item.model_dump(mode="json") for item in outcome_prediction.top_labels
            ],
            "temporal_event_detector_subtype_top_labels": [
                item.model_dump(mode="json") for item in subtype_prediction.top_labels
            ],
            "temporal_student_event_spotter_family": spotted_event_family,
            "temporal_student_event_spotter_likely_event": gate_open,
            "temporal_student_event_spotter_margin": round(event_spotter_prediction.margin, 4),
            "temporal_student_family_margin": round(family_prediction.margin, 4),
            "temporal_student_outcome_margin": round(outcome_prediction.margin, 4),
            "temporal_student_subtype_margin": round(subtype_prediction.margin, 4),
            "temporal_student_event_spotter_distribution": event_spotter_prediction.distribution,
            "temporal_student_event_spotter_top_labels": [
                item.model_dump(mode="json") for item in event_spotter_prediction.top_labels
            ],
            "temporal_student_family_distribution": family_prediction.distribution,
            "temporal_student_outcome_distribution": outcome_prediction.distribution,
            "temporal_student_subtype_distribution": subtype_prediction.distribution,
            "temporal_student_family_top_labels": [item.model_dump(mode="json") for item in family_prediction.top_labels],
            "temporal_student_outcome_top_labels": [item.model_dump(mode="json") for item in outcome_prediction.top_labels],
            "temporal_student_subtype_top_labels": [item.model_dump(mode="json") for item in subtype_prediction.top_labels],
            "eventFamilyOtherBucket": other_bucket,
            "eventFamilyOtherBucketReason": other_bucket_reason,
            "eventFamilyOtherBucketScores": other_bucket_scores,
        }
        return ActionPrediction(
            label=display_label,
            canonicalLabel=canonical_label,
            confidence=confidence_after_mapping,
            modelVersion=self.model_version,
            detectionMethod="temporal_event_detector",
            topLabels=list(family_prediction.top_labels),
            eventFamily=event_family,
            shotSubtype=shot_subtype,
            outcome=outcome,
            confidenceBeforeMapping=round(confidence_before_mapping, 4),
            confidenceAfterMapping=confidence_after_mapping,
            eventFamilyConfidenceBeforeMapping=event_spotter_prediction.confidence,
            eventFamilyConfidenceAfterMapping=round(
                max(
                    max(event_spotter_prediction.confidence, family_prediction.confidence)
                    - (0.08 if event_spotter_prediction.is_uncertain else 0.0),
                    0.0,
                ),
                4,
            ),
            shotSubtypeConfidenceBeforeMapping=subtype_prediction.confidence if gate_open and shot_subtype is not None else None,
            shotSubtypeConfidenceAfterMapping=(
                round(max(subtype_prediction.confidence - (0.06 if subtype_prediction.is_uncertain else 0.0), 0.0), 4)
                if gate_open and shot_subtype is not None
                else None
            ),
            outcomeConfidenceBeforeMapping=outcome_prediction.confidence if gate_open else None,
            outcomeConfidenceAfterMapping=(
                round(max(outcome_prediction.confidence - (0.06 if outcome_prediction.is_uncertain else 0.0), 0.0), 4)
                if gate_open
                else None
            ),
            isUncertain=is_uncertain,
            metadata=metadata,
        )

    def encode_observations(self, observations: Sequence[TemporalStudentObservation]) -> np.ndarray:
        frame_matrix = np.asarray(
            [vectorize_temporal_event_detector_observation(observation, self.input_feature_names) for observation in observations],
            dtype=np.float64,
        )
        base_hidden = np.tanh(
            np.matmul(frame_matrix, np.asarray(self.projection_weight, dtype=np.float64).T)
            + np.asarray(self.projection_bias, dtype=np.float64),
        )
        if not self.temporal_layers:
            return base_hidden
        if self.detector_family == "tridet" and len(self.temporal_layers) >= 2:
            branches = [
                np.tanh(_conv1d_same(base_hidden, layer))
                for layer in self.temporal_layers
            ]
            return np.tanh((base_hidden + sum(branches)) / float(len(branches) + 1))
        hidden = base_hidden
        for layer in self.temporal_layers:
            hidden = np.tanh(_conv1d_same(hidden, layer))
        return hidden

    def _pool_segment(self, hidden: np.ndarray, *, start_index: int, end_index: int) -> tuple[np.ndarray, np.ndarray]:
        segment = hidden[start_index : end_index + 1]
        attention_logits = np.matmul(segment, np.asarray(self.segment_attention_weight, dtype=np.float64)) + float(
            self.segment_attention_bias
        )
        attention = _softmax(attention_logits)
        weighted_mean = np.sum(segment * attention[:, np.newaxis], axis=0)
        pooled_max = np.max(segment, axis=0)
        pooled_last = segment[-1]
        pooled_delta = segment[-1] - segment[0]
        pooled = np.concatenate([weighted_mean, pooled_max, pooled_last, pooled_delta], axis=0)
        return pooled, attention

    def _spot_event(
        self,
        *,
        frame_family_probabilities: np.ndarray,
        eventness: np.ndarray,
        start_scores: np.ndarray,
        end_scores: np.ndarray,
    ) -> tuple[int, str, TemporalStudentTargetPrediction, float]:
        center_index = 0
        best_score = -1.0
        best_family = "other"
        best_distribution: dict[str, float] | None = None
        best_top_labels: tuple[LabelScore, ...] = ()
        best_margin = 0.0
        best_confidence = 0.0
        best_other_index = 0
        best_other_confidence = 0.0
        best_other_distribution: dict[str, float] | None = None
        best_other_top_labels: tuple[LabelScore, ...] = ()
        best_other_margin = 0.0
        for index in range(frame_family_probabilities.shape[0]):
            probabilities = frame_family_probabilities[index]
            ranking = list(np.argsort(probabilities)[::-1])
            top_index = ranking[0]
            top_probability = float(probabilities[top_index])
            non_other_indices = [item for item in ranking if EVENT_FAMILIES[item] != "other"]
            best_non_other_index = non_other_indices[0] if non_other_indices else ranking[0]
            best_non_other_probability = float(probabilities[best_non_other_index])
            second_probability = float(probabilities[ranking[1]]) if len(ranking) > 1 else 0.0
            boundary_score = 0.5 + 0.25 * float(np.max(start_scores[: index + 1])) + 0.25 * float(np.max(end_scores[index:]))
            ranking_score = float(eventness[index]) * best_non_other_probability * boundary_score
            confidence_score = min(
                max((0.5 * float(eventness[index])) + (0.35 * best_non_other_probability) + (0.15 * boundary_score), 0.0),
                1.0,
            )
            other_confidence = min(
                max((0.55 * top_probability) + (0.3 * (1.0 - float(eventness[index]))) + (0.15 * boundary_score), 0.0),
                1.0,
            ) if EVENT_FAMILIES[top_index] == "other" else 0.0
            distribution = {
                str(label): round(float(probabilities[label_index]), 4)
                for label_index, label in enumerate(EVENT_FAMILIES)
            }
            top_labels = tuple(
                LabelScore(
                    label=str(EVENT_FAMILIES[label_index]),
                    confidence=round(float(probabilities[label_index]), 4),
                    modelVersion=self.model_version,
                )
                for label_index in ranking[:MAX_TEMPORAL_EVENT_DETECTOR_TOPK]
            )
            if other_confidence > best_other_confidence:
                best_other_index = index
                best_other_confidence = other_confidence
                best_other_distribution = distribution
                best_other_top_labels = top_labels
                best_other_margin = round(max(top_probability - second_probability, 0.0), 4)
            if ranking_score <= best_score:
                continue
            best_score = ranking_score
            best_confidence = confidence_score
            center_index = index
            best_family = str(EVENT_FAMILIES[best_non_other_index]) if confidence_score >= self.event_score_threshold else "other"
            best_distribution = distribution
            best_top_labels = top_labels
            best_margin = round(max(best_non_other_probability - second_probability, 0.0), 4)
        if best_other_confidence >= max(best_confidence + 0.02, 0.5):
            center_index = best_other_index
            best_family = "other"
            best_confidence = best_other_confidence
            best_distribution = best_other_distribution
            best_top_labels = best_other_top_labels
            best_margin = best_other_margin
        prediction = TemporalStudentTargetPrediction(
            label=best_family,
            confidence=round(best_confidence, 4),
            margin=best_margin,
            distribution=best_distribution or {"other": 1.0},
            top_labels=best_top_labels or (
                LabelScore(label="other", confidence=1.0, modelVersion=self.model_version),
            ),
            is_uncertain=best_confidence < self.event_score_threshold or best_margin < self.event_margin_threshold,
        )
        return center_index, best_family, prediction, round(best_confidence, 4)


def vectorize_temporal_event_detector_observation(
    observation: TemporalStudentObservation,
    input_feature_names: Sequence[str],
) -> np.ndarray:
    feature_values = build_temporal_event_detector_feature_map(observation)
    return np.asarray([float(feature_values.get(name, 0.0)) for name in input_feature_names], dtype=np.float64)


def build_temporal_event_detector_feature_map(observation: TemporalStudentObservation) -> dict[str, float]:
    return {
        name: value
        for name, value in build_temporal_student_feature_map(observation).items()
        if _include_temporal_event_detector_feature(name)
    }


def default_temporal_event_detector_feature_names() -> tuple[str, ...]:
    return tuple(
        name
        for name in default_temporal_student_feature_names()
        if _include_temporal_event_detector_feature(name)
    )


def _include_temporal_event_detector_feature(name: str) -> bool:
    if name in TEMPORAL_EVENT_DETECTOR_EXCLUDED_FEATURES:
        return False
    return not any(name.startswith(prefix) for prefix in TEMPORAL_EVENT_DETECTOR_EXCLUDED_FEATURE_PREFIXES)


def load_temporal_event_detector_bundle(path: Path | None = None) -> TemporalEventDetectorBundle:
    bundle_path = path or TEMPORAL_EVENT_DETECTOR_BUNDLE_PATH
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    targets = {
        str(target_name): TemporalTargetModel(
            name=str(target_name),
            classes=tuple(str(item) for item in target_payload.get("classes", [])),
            weight=tuple(tuple(float(value) for value in row) for row in target_payload.get("weight", [])),
            bias=tuple(float(value) for value in target_payload.get("bias", [])),
            temperature=float(target_payload.get("temperature", 1.0)),
            uncertainty_threshold=float(target_payload.get("uncertaintyThreshold", 0.46)),
            margin_threshold=float(target_payload.get("marginThreshold", 0.05)),
            top_k=int(target_payload.get("topK", MAX_TEMPORAL_EVENT_DETECTOR_TOPK)),
        )
        for target_name, target_payload in (payload.get("targets") or {}).items()
    }
    temporal_layers = tuple(
        TemporalConvLayer(
            weight=tuple(
                tuple(tuple(float(value) for value in kernel) for kernel in channel)
                for channel in layer_payload.get("weight", [])
            ),
            bias=tuple(float(value) for value in layer_payload.get("bias", [])),
            dilation=int(layer_payload.get("dilation", 1)),
        )
        for layer_payload in payload.get("temporalLayers", [])
    )
    return TemporalEventDetectorBundle(
        schema_version=str(payload.get("schemaVersion", TEMPORAL_EVENT_DETECTOR_SCHEMA_VERSION)),
        feature_schema_version=str(payload.get("featureSchemaVersion", TEMPORAL_EVENT_DETECTOR_FEATURE_SCHEMA_VERSION)),
        model_version=str(payload.get("modelVersion", TEMPORAL_EVENT_DETECTOR_MODEL_VERSION)),
        detector_family=str(payload.get("detectorFamily", "actionformer")),
        trained_at=str(payload.get("trainedAt", "")),
        source_dataset=str(payload.get("sourceDataset", "")),
        notes=tuple(str(item) for item in payload.get("notes", []) if item is not None),
        input_feature_names=tuple(str(item) for item in payload.get("inputFeatureNames", [])),
        hidden_size=int(payload.get("hiddenSize", 0)),
        projection_weight=tuple(tuple(float(value) for value in row) for row in payload.get("projection", {}).get("weight", [])),
        projection_bias=tuple(float(value) for value in payload.get("projection", {}).get("bias", [])),
        temporal_layers=temporal_layers,
        segment_attention_weight=tuple(float(value) for value in payload.get("segmentAttention", {}).get("weight", [])),
        segment_attention_bias=float(payload.get("segmentAttention", {}).get("bias", 0.0)),
        eventness_weight=tuple(float(value) for value in payload.get("eventness", {}).get("weight", [])),
        eventness_bias=float(payload.get("eventness", {}).get("bias", 0.0)),
        frame_family_weight=tuple(
            tuple(float(value) for value in row) for row in payload.get("frameFamily", {}).get("weight", [])
        ),
        frame_family_bias=tuple(float(value) for value in payload.get("frameFamily", {}).get("bias", [])),
        start_weight=tuple(float(value) for value in payload.get("startHead", {}).get("weight", [])),
        start_bias=float(payload.get("startHead", {}).get("bias", 0.0)),
        end_weight=tuple(float(value) for value in payload.get("endHead", {}).get("weight", [])),
        end_bias=float(payload.get("endHead", {}).get("bias", 0.0)),
        event_score_threshold=float(payload.get("eventScoreThreshold", 0.38)),
        event_margin_threshold=float(payload.get("eventMarginThreshold", 0.05)),
        targets=targets,
    )


@lru_cache(maxsize=1)
def get_temporal_event_detector_bundle(path: str | None = None) -> TemporalEventDetectorBundle | None:
    bundle_path = Path(path) if path else TEMPORAL_EVENT_DETECTOR_BUNDLE_PATH
    if not bundle_path.exists():
        return None
    return load_temporal_event_detector_bundle(bundle_path)


def write_temporal_event_detector_bundle(path: Path, bundle: TemporalEventDetectorBundle) -> None:
    payload = {
        "schemaVersion": bundle.schema_version,
        "featureSchemaVersion": bundle.feature_schema_version,
        "modelVersion": bundle.model_version,
        "detectorFamily": bundle.detector_family,
        "trainedAt": bundle.trained_at,
        "sourceDataset": bundle.source_dataset,
        "notes": list(bundle.notes),
        "inputFeatureNames": list(bundle.input_feature_names),
        "hiddenSize": bundle.hidden_size,
        "projection": {
            "weight": [list(row) for row in bundle.projection_weight],
            "bias": list(bundle.projection_bias),
        },
        "temporalLayers": [
            {
                "weight": [[list(kernel) for kernel in channel] for channel in layer.weight],
                "bias": list(layer.bias),
                "dilation": layer.dilation,
            }
            for layer in bundle.temporal_layers
        ],
        "segmentAttention": {
            "weight": list(bundle.segment_attention_weight),
            "bias": bundle.segment_attention_bias,
        },
        "eventness": {
            "weight": list(bundle.eventness_weight),
            "bias": bundle.eventness_bias,
        },
        "frameFamily": {
            "weight": [list(row) for row in bundle.frame_family_weight],
            "bias": list(bundle.frame_family_bias),
        },
        "startHead": {
            "weight": list(bundle.start_weight),
            "bias": bundle.start_bias,
        },
        "endHead": {
            "weight": list(bundle.end_weight),
            "bias": bundle.end_bias,
        },
        "eventScoreThreshold": bundle.event_score_threshold,
        "eventMarginThreshold": bundle.event_margin_threshold,
        "targets": {
            name: {
                "classes": list(target.classes),
                "weight": [list(row) for row in target.weight],
                "bias": list(target.bias),
                "temperature": target.temperature,
                "uncertaintyThreshold": target.uncertainty_threshold,
                "marginThreshold": target.margin_threshold,
                "topK": target.top_k,
            }
            for name, target in bundle.targets.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _resolve_outcome(event_family: str, prediction: TemporalStudentTargetPrediction) -> str:
    if event_family == "defensive_event":
        return "blocked" if prediction.label == "blocked" and not prediction.is_uncertain else "uncertain"
    if event_family != "shot_attempt":
        return "uncertain"
    if prediction.is_uncertain:
        return "uncertain"
    return prediction.label


def _conv1d_same(hidden: np.ndarray, layer: TemporalConvLayer) -> np.ndarray:
    weights = np.asarray(layer.weight, dtype=np.float64)
    bias = np.asarray(layer.bias, dtype=np.float64)
    out_channels, in_channels, kernel_size = weights.shape
    if hidden.shape[1] != in_channels:
        raise ValueError("Temporal convolution input size mismatch.")
    padding = ((kernel_size - 1) // 2) * max(layer.dilation, 1)
    padded = np.pad(hidden, ((padding, padding), (0, 0)), mode="edge")
    output = np.zeros((hidden.shape[0], out_channels), dtype=np.float64)
    for time_index in range(hidden.shape[0]):
        for out_channel in range(out_channels):
            value = bias[out_channel]
            for kernel_index in range(kernel_size):
                padded_index = time_index + kernel_index * max(layer.dilation, 1)
                value += float(
                    np.dot(
                        padded[padded_index],
                        weights[out_channel, :, kernel_index],
                    )
                )
            output[time_index, out_channel] = value
    return output


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp_logits = np.exp(shifted)
    denominator = np.sum(exp_logits)
    if denominator <= 0.0:
        return np.ones_like(exp_logits) / max(len(exp_logits), 1)
    return exp_logits / denominator


def _softmax_rows(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp_logits = np.exp(shifted)
    denominator = np.sum(exp_logits, axis=1, keepdims=True)
    denominator[denominator <= 0.0] = 1.0
    return exp_logits / denominator


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))

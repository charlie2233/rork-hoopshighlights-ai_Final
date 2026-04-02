from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from services.inference.app.models import ActionPrediction, LabelScore
from services.inference.app.runtime_model import derive_runtime_display_label
from services.inference.app.temporal_encoder import TemporalTargetModel, TemporalTargetPrediction
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


TEMPORAL_EVENT_DETECTOR_SCHEMA_VERSION = "temporal-event-detector-v2"
TEMPORAL_EVENT_DETECTOR_FEATURE_SCHEMA_VERSION = "temporal-event-detector-feature-v2"
TEMPORAL_EVENT_DETECTOR_MODEL_VERSION = "temporal-event-detector-tridet-hybrid-v1"
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
PROPOSAL_REJECT_LABELS = (
    "real_event",
    "non_event",
    "setup",
    "dead_ball",
    "replay_or_reaction",
    "ambiguous",
)
HARD_REJECT_LABELS = frozenset({"non_event", "setup", "dead_ball", "replay_or_reaction"})
PROPOSAL_REJECTOR_AGGREGATE_FEATURES = (
    "ball_visible",
    "hoop_visible",
    "ball_detection_confidence",
    "hoop_detection_confidence",
    "tracked_ball_confidence",
    "player_track_count",
    "tracked_player_count",
    "detection_density",
    "tracking_density",
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
    "event_localization_present",
    "event_localization_complete",
    "event_duration_seconds_norm",
)
REJECT_LABEL_TO_OTHER_BUCKET = {
    "non_event": "non_event",
    "setup": "setup",
    "dead_ball": "dead_ball",
    "replay_or_reaction": "replay_or_reaction",
    "ambiguous": "ambiguous_event",
}


@dataclass(frozen=True)
class TemporalConvLayer:
    weight: tuple[tuple[tuple[float, ...], ...], ...]
    bias: tuple[float, ...]
    dilation: int


@dataclass(frozen=True)
class TemporalEventProposal:
    start_index: int
    center_index: int
    end_index: int
    start_seconds: float
    center_seconds: float
    end_seconds: float
    event_score: float
    event_margin: float
    coarse_event_family: str
    hidden: np.ndarray
    pooled_vector: np.ndarray
    segment_attention: np.ndarray
    eventness: np.ndarray
    start_scores: np.ndarray
    end_scores: np.ndarray
    event_spotter_prediction: TemporalStudentTargetPrediction


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
    eventness_temperature: float = 1.0
    proposal_rejector_feature_names: tuple[str, ...] = ()
    proposal_rejector: TemporalTargetModel | None = None

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
            branches = [np.tanh(_conv1d_same(base_hidden, layer)) for layer in self.temporal_layers]
            return np.tanh((base_hidden + sum(branches)) / float(len(branches) + 1))
        hidden = base_hidden
        for layer in self.temporal_layers:
            hidden = np.tanh(_conv1d_same(hidden, layer))
        return hidden

    def propose(self, observations: Sequence[TemporalStudentObservation]) -> TemporalEventProposal:
        if not observations:
            raise ValueError("At least one temporal detector observation is required.")
        hidden = self.encode_observations(observations)
        frame_family_probabilities = _softmax_rows(
            np.matmul(hidden, np.asarray(self.frame_family_weight, dtype=np.float64).T)
            + np.asarray(self.frame_family_bias, dtype=np.float64),
        )
        raw_eventness = (
            np.matmul(hidden, np.asarray(self.eventness_weight, dtype=np.float64))
            + float(self.eventness_bias)
        )
        eventness = _sigmoid(raw_eventness / max(self.eventness_temperature, 1e-3))
        start_scores = _softmax(
            np.matmul(hidden, np.asarray(self.start_weight, dtype=np.float64)) + float(self.start_bias)
        )
        end_scores = _softmax(
            np.matmul(hidden, np.asarray(self.end_weight, dtype=np.float64)) + float(self.end_bias)
        )
        center_index, coarse_event_family, event_spotter_prediction, best_event_score = self._spot_event(
            frame_family_probabilities=frame_family_probabilities,
            eventness=eventness,
            start_scores=start_scores,
            end_scores=end_scores,
        )
        start_index = int(np.argmax(start_scores[: center_index + 1])) if center_index >= 0 else 0
        end_index = int(center_index + np.argmax(end_scores[center_index:])) if center_index < len(observations) else len(observations) - 1
        if end_index < start_index:
            end_index = start_index
        pooled, segment_attention = self._pool_segment(hidden, start_index=start_index, end_index=end_index)
        return TemporalEventProposal(
            start_index=start_index,
            center_index=center_index,
            end_index=end_index,
            start_seconds=round(float(observations[start_index].timestamp_seconds), 4),
            center_seconds=round(float(observations[center_index].timestamp_seconds), 4),
            end_seconds=round(float(observations[end_index].timestamp_seconds), 4),
            event_score=round(best_event_score, 4),
            event_margin=round(event_spotter_prediction.margin, 4),
            coarse_event_family=coarse_event_family,
            hidden=hidden,
            pooled_vector=pooled,
            segment_attention=segment_attention,
            eventness=eventness,
            start_scores=start_scores,
            end_scores=end_scores,
            event_spotter_prediction=event_spotter_prediction,
        )

    def predict(self, observations: Sequence[TemporalStudentObservation]) -> ActionPrediction:
        proposal = self.propose(observations)
        rejector_prediction = self._predict_proposal_rejector(observations, proposal)
        proposal_accepted = self._proposal_accepted(proposal, rejector_prediction)
        classifier_gate_open = False

        if proposal_accepted:
            family_prediction = _predict_conditioned_target(
                self.targets["eventFamily"],
                proposal.pooled_vector,
                model_version=self.model_version,
                allowed_labels=tuple(label for label in EVENT_FAMILIES if label != "other"),
            )
            event_family = family_prediction.label
            if family_prediction.is_uncertain or event_family not in EVENT_FAMILIES or event_family == "other":
                event_family = "other"
            classifier_gate_open = (
                rejector_prediction.label == "real_event"
                and not rejector_prediction.is_uncertain
                and event_family != "other"
                and not family_prediction.is_uncertain
            )
            if classifier_gate_open:
                outcome_prediction = _predict_conditioned_target(
                    self.targets["outcome"],
                    proposal.pooled_vector,
                    model_version=self.model_version,
                    allowed_labels=CONDITIONED_OUTCOME_LABELS.get(event_family, OUTCOMES),
                )
                subtype_prediction = _predict_conditioned_target(
                    self.targets["shotSubtype"],
                    proposal.pooled_vector,
                    model_version=self.model_version,
                    allowed_labels=CONDITIONED_SUBTYPE_LABELS.get(event_family, SHOT_SUBTYPES),
                )
                outcome = _resolve_outcome(event_family, outcome_prediction)
            else:
                outcome_prediction = _fallback_temporal_prediction(
                    label="uncertain",
                    confidence=min(rejector_prediction.confidence, 0.49),
                    model_version=self.model_version,
                )
                subtype_prediction = _fallback_temporal_prediction(
                    label="null",
                    confidence=min(rejector_prediction.confidence, 0.49),
                    model_version=self.model_version,
                )
                outcome = "uncertain"
        else:
            family_prediction = _fallback_temporal_prediction(
                label="other",
                confidence=min(proposal.event_score, 0.49),
                model_version=self.model_version,
            )
            outcome_prediction = _fallback_temporal_prediction(
                label="uncertain",
                confidence=min(rejector_prediction.confidence, 0.49),
                model_version=self.model_version,
            )
            subtype_prediction = _fallback_temporal_prediction(
                label="null",
                confidence=min(rejector_prediction.confidence, 0.49),
                model_version=self.model_version,
            )
            event_family = "other"
            outcome = "uncertain"

        shot_subtype: str | None = None
        if (
            proposal_accepted
            and event_family == "shot_attempt"
            and not subtype_prediction.is_uncertain
            and subtype_prediction.label not in {"null", "unknown"}
        ):
            shot_subtype = subtype_prediction.label

        canonical_label, display_label = derive_runtime_display_label(
            event_family=event_family,
            outcome=outcome,
            shot_subtype=shot_subtype,
        )
        is_uncertain = (
            not proposal_accepted
            or not classifier_gate_open
            or rejector_prediction.is_uncertain
            or rejector_prediction.label != "real_event"
            or family_prediction.is_uncertain
            or (classifier_gate_open and event_family == "shot_attempt" and outcome_prediction.is_uncertain)
            or (event_family == "shot_attempt" and shot_subtype is None)
        )
        confidence_before_mapping = proposal.event_score if not proposal_accepted else max(
            proposal.event_score,
            family_prediction.confidence,
        )
        if proposal_accepted:
            confidence_after_mapping = round(
                _resolve_student_confidence(
                    display_label=display_label,
                    event_spotter_prediction=proposal.event_spotter_prediction,
                    family_prediction=family_prediction,
                    outcome_prediction=outcome_prediction,
                    subtype_prediction=subtype_prediction,
                    gate_open=classifier_gate_open,
                    is_uncertain=is_uncertain,
                ),
                4,
            )
        else:
            confidence_after_mapping = round(
                max(min(proposal.event_score, rejector_prediction.confidence) - 0.12, 0.18),
                4,
            )

        if proposal_accepted:
            other_bucket, other_bucket_reason, other_bucket_scores = _classify_other_bucket(
                observations=observations,
                event_family=event_family,
                event_spotter_prediction=proposal.event_spotter_prediction,
                family_prediction=family_prediction,
            )
        else:
            other_bucket = REJECT_LABEL_TO_OTHER_BUCKET.get(rejector_prediction.label, "other_true_unknown")
            other_bucket_reason = f"proposal_rejected:{rejector_prediction.label}"
            other_bucket_scores = rejector_prediction.distribution

        metadata = {
            "temporal_event_detector_model_version": self.model_version,
            "temporal_event_detector_schema_version": self.schema_version,
            "temporal_event_detector_feature_schema_version": self.feature_schema_version,
            "temporal_event_detector_family": self.detector_family,
            "temporal_event_detector_frame_count": len(observations),
            "temporal_event_detector_event_score_threshold": round(self.event_score_threshold, 4),
            "temporal_event_detector_event_margin_threshold": round(self.event_margin_threshold, 4),
            "temporal_event_detector_eventness_temperature": round(self.eventness_temperature, 4),
            "temporal_event_detector_segment": {
                "startIndex": proposal.start_index,
                "centerIndex": proposal.center_index,
                "endIndex": proposal.end_index,
                "startSeconds": proposal.start_seconds,
                "centerSeconds": proposal.center_seconds,
                "endSeconds": proposal.end_seconds,
            },
            "temporal_event_detector_event_score": proposal.event_score,
            "temporal_event_detector_event_margin": proposal.event_margin,
            "temporal_event_detector_eventness": [round(float(value), 4) for value in proposal.eventness.tolist()],
            "temporal_event_detector_start_scores": [round(float(value), 4) for value in proposal.start_scores.tolist()],
            "temporal_event_detector_end_scores": [round(float(value), 4) for value in proposal.end_scores.tolist()],
            "temporal_event_detector_segment_attention": [round(float(value), 4) for value in proposal.segment_attention.tolist()],
            "temporal_event_detector_event_family": proposal.coarse_event_family,
            "temporal_event_detector_gate_open": classifier_gate_open,
            "temporal_event_detector_proposal_accepted": proposal_accepted,
            "temporal_event_detector_classifier_gate_open": classifier_gate_open,
            "temporal_event_detector_proposal_rejector_label": rejector_prediction.label,
            "temporal_event_detector_proposal_rejector_confidence": round(rejector_prediction.confidence, 4),
            "temporal_event_detector_proposal_rejector_margin": round(rejector_prediction.margin, 4),
            "temporal_event_detector_proposal_rejector_distribution": rejector_prediction.distribution,
            "temporal_event_detector_proposal_rejector_top_labels": [
                item.model_dump(mode="json") for item in rejector_prediction.top_labels
            ],
            "temporal_event_detector_proposal_rejector_temperature": (
                round(self.proposal_rejector.temperature, 4) if self.proposal_rejector is not None else None
            ),
            "temporal_event_detector_proposal_rejector_uncertainty_threshold": (
                round(self.proposal_rejector.uncertainty_threshold, 4) if self.proposal_rejector is not None else None
            ),
            "temporal_event_detector_proposal_rejector_margin_threshold": (
                round(self.proposal_rejector.margin_threshold, 4) if self.proposal_rejector is not None else None
            ),
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
            "temporal_event_detector_outcome_temperature": round(self.targets["outcome"].temperature, 4),
            "temporal_event_detector_outcome_uncertainty_threshold": round(
                self.targets["outcome"].uncertainty_threshold,
                4,
            ),
            "temporal_event_detector_outcome_margin_threshold": round(self.targets["outcome"].margin_threshold, 4),
            "temporal_student_event_spotter_family": proposal.coarse_event_family,
            "temporal_student_event_spotter_likely_event": proposal_accepted,
            "temporal_student_event_spotter_margin": round(proposal.event_spotter_prediction.margin, 4),
            "temporal_student_family_margin": round(family_prediction.margin, 4),
            "temporal_student_outcome_margin": round(outcome_prediction.margin, 4),
            "temporal_student_subtype_margin": round(subtype_prediction.margin, 4),
            "temporal_student_event_spotter_distribution": proposal.event_spotter_prediction.distribution,
            "temporal_student_event_spotter_top_labels": [
                item.model_dump(mode="json") for item in proposal.event_spotter_prediction.top_labels
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

        top_labels = list(family_prediction.top_labels if proposal_accepted else proposal.event_spotter_prediction.top_labels)
        return ActionPrediction(
            label=display_label,
            canonicalLabel=canonical_label,
            confidence=confidence_after_mapping,
            modelVersion=self.model_version,
            detectionMethod="temporal_event_detector",
            topLabels=top_labels,
            eventFamily=event_family,
            shotSubtype=shot_subtype,
            outcome=outcome,
            confidenceBeforeMapping=round(confidence_before_mapping, 4),
            confidenceAfterMapping=confidence_after_mapping,
            eventFamilyConfidenceBeforeMapping=round(proposal.event_spotter_prediction.confidence, 4),
            eventFamilyConfidenceAfterMapping=round(
                max(
                    (family_prediction.confidence if proposal_accepted else rejector_prediction.confidence)
                    - (0.08 if is_uncertain else 0.0),
                    0.0,
                ),
                4,
            ),
            shotSubtypeConfidenceBeforeMapping=subtype_prediction.confidence if shot_subtype is not None else None,
            shotSubtypeConfidenceAfterMapping=(
                round(max(subtype_prediction.confidence - (0.06 if subtype_prediction.is_uncertain else 0.0), 0.0), 4)
                if shot_subtype is not None
                else None
            ),
            outcomeConfidenceBeforeMapping=outcome_prediction.confidence if proposal_accepted else None,
            outcomeConfidenceAfterMapping=(
                round(max(outcome_prediction.confidence - (0.06 if outcome_prediction.is_uncertain else 0.0), 0.0), 4)
                if proposal_accepted
                else None
            ),
            isUncertain=is_uncertain,
            metadata=metadata,
        )

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
            other_confidence = (
                min(
                    max((0.55 * top_probability) + (0.3 * (1.0 - float(eventness[index]))) + (0.15 * boundary_score), 0.0),
                    1.0,
                )
                if EVENT_FAMILIES[top_index] == "other"
                else 0.0
            )
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

    def _predict_proposal_rejector(
        self,
        observations: Sequence[TemporalStudentObservation],
        proposal: TemporalEventProposal,
    ) -> TemporalTargetPrediction:
        if self.proposal_rejector is None or not self.proposal_rejector_feature_names:
            return _fallback_rejector_prediction(
                label="real_event" if proposal.coarse_event_family != "other" and not proposal.event_spotter_prediction.is_uncertain else "ambiguous",
                confidence=proposal.event_spotter_prediction.confidence,
                margin=proposal.event_spotter_prediction.margin,
                model_version=self.model_version,
            )
        feature_map = build_proposal_rejector_feature_map(observations=observations, proposal=proposal)
        feature_vector = np.asarray(
            [float(feature_map.get(name, 0.0)) for name in self.proposal_rejector_feature_names],
            dtype=np.float64,
        )
        return self.proposal_rejector.predict(feature_vector, model_version=self.model_version)

    def _proposal_accepted(
        self,
        proposal: TemporalEventProposal,
        rejector_prediction: TemporalTargetPrediction,
    ) -> bool:
        if proposal.event_score < self.event_score_threshold:
            return False
        if proposal.event_margin < self.event_margin_threshold:
            return False
        if proposal.coarse_event_family == "other":
            return False
        if rejector_prediction.label in HARD_REJECT_LABELS and not rejector_prediction.is_uncertain:
            return False
        if rejector_prediction.label == "real_event":
            return True
        if rejector_prediction.label == "ambiguous":
            return False
        if rejector_prediction.is_uncertain:
            return (
                proposal.event_spotter_prediction.confidence >= max(self.event_score_threshold + 0.08, 0.5)
                and proposal.event_spotter_prediction.margin >= max(self.event_margin_threshold, 0.05)
            )
        return False


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


def build_proposal_rejector_feature_map(
    *,
    observations: Sequence[TemporalStudentObservation],
    proposal: TemporalEventProposal,
) -> dict[str, float]:
    if not observations:
        return {}
    clip_start = float(observations[0].timestamp_seconds)
    clip_end = float(observations[-1].timestamp_seconds)
    clip_duration = max(clip_end - clip_start, 1e-3)
    segment = observations[proposal.start_index : proposal.end_index + 1]
    segment_feature_maps = [build_temporal_event_detector_feature_map(observation) for observation in segment]
    feature_map: dict[str, float] = {
        "proposal_event_score": proposal.event_score,
        "proposal_event_margin": proposal.event_margin,
        "proposal_start_ratio": round(max(proposal.start_seconds - clip_start, 0.0) / clip_duration, 4),
        "proposal_center_ratio": round(max(proposal.center_seconds - clip_start, 0.0) / clip_duration, 4),
        "proposal_end_ratio": round(max(proposal.end_seconds - clip_start, 0.0) / clip_duration, 4),
        "proposal_duration_ratio": round(max(proposal.end_seconds - proposal.start_seconds, 0.0) / clip_duration, 4),
        "proposal_frame_count": float(len(segment)),
        "proposal_eventness_center": round(float(proposal.eventness[proposal.center_index]), 4),
        "proposal_eventness_mean": round(float(np.mean(proposal.eventness[proposal.start_index : proposal.end_index + 1])), 4),
        "proposal_eventness_max": round(float(np.max(proposal.eventness[proposal.start_index : proposal.end_index + 1])), 4),
        "proposal_segment_attention_peak": round(float(np.max(proposal.segment_attention)), 4),
        "proposal_segment_attention_entropy": round(_entropy(proposal.segment_attention), 4),
    }
    for family in EVENT_FAMILIES:
        feature_map[f"proposal_family_{family}"] = float(proposal.event_spotter_prediction.distribution.get(family, 0.0))
    for index, value in enumerate(proposal.pooled_vector.tolist()):
        feature_map[f"proposal_embedding_{index}"] = float(value)
    for name in PROPOSAL_REJECTOR_AGGREGATE_FEATURES:
        values = [float(item.get(name, 0.0)) for item in segment_feature_maps]
        feature_map[f"segment_mean_{name}"] = round(float(np.mean(values)), 4) if values else 0.0
        feature_map[f"segment_max_{name}"] = round(float(np.max(values)), 4) if values else 0.0
    return feature_map


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
    proposal_rejector_payload = payload.get("proposalRejector") or {}
    proposal_rejector_target_payload = proposal_rejector_payload.get("target") or {}
    proposal_rejector = None
    if proposal_rejector_target_payload:
        proposal_rejector = TemporalTargetModel(
            name="proposalRejector",
            classes=tuple(str(item) for item in proposal_rejector_target_payload.get("classes", [])),
            weight=tuple(tuple(float(value) for value in row) for row in proposal_rejector_target_payload.get("weight", [])),
            bias=tuple(float(value) for value in proposal_rejector_target_payload.get("bias", [])),
            temperature=float(proposal_rejector_target_payload.get("temperature", 1.0)),
            uncertainty_threshold=float(proposal_rejector_target_payload.get("uncertaintyThreshold", 0.5)),
            margin_threshold=float(proposal_rejector_target_payload.get("marginThreshold", 0.08)),
            top_k=int(proposal_rejector_target_payload.get("topK", MAX_TEMPORAL_EVENT_DETECTOR_TOPK)),
        )
    return TemporalEventDetectorBundle(
        schema_version=str(payload.get("schemaVersion", TEMPORAL_EVENT_DETECTOR_SCHEMA_VERSION)),
        feature_schema_version=str(payload.get("featureSchemaVersion", TEMPORAL_EVENT_DETECTOR_FEATURE_SCHEMA_VERSION)),
        model_version=str(payload.get("modelVersion", TEMPORAL_EVENT_DETECTOR_MODEL_VERSION)),
        detector_family=str(payload.get("detectorFamily", "tridet")),
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
        event_score_threshold=float(payload.get("eventScoreThreshold", 0.36)),
        event_margin_threshold=float(payload.get("eventMarginThreshold", 0.05)),
        targets=targets,
        eventness_temperature=float(payload.get("eventnessTemperature", 1.0)),
        proposal_rejector_feature_names=tuple(str(item) for item in proposal_rejector_payload.get("featureNames", [])),
        proposal_rejector=proposal_rejector,
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
        "eventnessTemperature": bundle.eventness_temperature,
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
        "proposalRejector": (
            {
                "featureNames": list(bundle.proposal_rejector_feature_names),
                "target": {
                    "classes": list(bundle.proposal_rejector.classes),
                    "weight": [list(row) for row in bundle.proposal_rejector.weight],
                    "bias": list(bundle.proposal_rejector.bias),
                    "temperature": bundle.proposal_rejector.temperature,
                    "uncertaintyThreshold": bundle.proposal_rejector.uncertainty_threshold,
                    "marginThreshold": bundle.proposal_rejector.margin_threshold,
                    "topK": bundle.proposal_rejector.top_k,
                },
            }
            if bundle.proposal_rejector is not None
            else None
        ),
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


def _best_non_other_label(prediction: TemporalStudentTargetPrediction) -> str | None:
    for item in prediction.top_labels:
        label = str(item.label)
        if label != "other":
            return label
    return None


def _fallback_rejector_prediction(
    *,
    label: str,
    confidence: float,
    margin: float,
    model_version: str,
) -> TemporalTargetPrediction:
    safe_label = label if label in PROPOSAL_REJECT_LABELS else "ambiguous"
    confidence = round(min(max(float(confidence), 0.0), 1.0), 4)
    margin = round(min(max(float(margin), 0.0), 1.0), 4)
    distribution = {item: 0.0 for item in PROPOSAL_REJECT_LABELS}
    distribution[safe_label] = confidence
    top_labels = (LabelScore(label=safe_label, confidence=confidence, modelVersion=model_version),)
    return TemporalTargetPrediction(
        label=safe_label,
        confidence=confidence,
        margin=margin,
        distribution=distribution,
        top_labels=top_labels,
        is_uncertain=safe_label != "real_event" and confidence < 0.6,
    )


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
                value += float(np.dot(padded[padded_index], weights[out_channel, :, kernel_index]))
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


def _entropy(values: np.ndarray) -> float:
    safe = np.clip(np.asarray(values, dtype=np.float64), 1e-8, 1.0)
    return float(-np.sum(safe * np.log2(safe)))

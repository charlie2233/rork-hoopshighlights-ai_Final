from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from services.inference.app.models import ActionPrediction, LabelScore
from services.inference.app.runtime_model import derive_runtime_display_label
from services.inference.app.temporal_encoder import TemporalTargetModel


TEMPORAL_STUDENT_SCHEMA_VERSION = "temporal-student-v2"
TEMPORAL_STUDENT_FEATURE_SCHEMA_VERSION = "temporal-student-feature-v2"
TEMPORAL_STUDENT_MODEL_VERSION = "temporal-student-staged-v1"
TEMPORAL_STUDENT_BUNDLE_PATH = Path(__file__).resolve().parents[2] / "models" / "temporal_student_v1.json"
MAX_TEMPORAL_STUDENT_TOPK = 3

EVENT_FAMILIES = ("shot_attempt", "turnover", "defensive_event", "transition", "other")
OUTCOMES = ("made", "missed", "blocked", "uncertain")
SHOT_SUBTYPES = ("dunk", "layup", "jumper", "three", "putback", "null")
DISPLAY_LABELS = ("Dunk", "Layup", "Three Pointer", "Made Shot", "Block", "Steal", "Fast Break", "Highlight")
CONDITIONED_OUTCOME_LABELS = {
    "shot_attempt": ("made", "missed", "blocked", "uncertain"),
    "defensive_event": ("blocked", "uncertain"),
    "turnover": ("uncertain",),
    "transition": ("uncertain",),
    "other": ("uncertain",),
}
CONDITIONED_SUBTYPE_LABELS = {
    "shot_attempt": ("dunk", "layup", "jumper", "three", "putback", "null"),
    "defensive_event": ("null",),
    "turnover": ("null",),
    "transition": ("null",),
    "other": ("null",),
}


@dataclass(frozen=True)
class TemporalStudentObservation:
    timestamp_seconds: float
    structured_signals: dict[str, Any]
    perception_features: dict[str, Any]
    detection_features: dict[str, Any] = field(default_factory=dict)
    tracking_features: dict[str, Any] = field(default_factory=dict)
    runtime_features: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalStudentTargetPrediction:
    label: str
    confidence: float
    margin: float
    distribution: dict[str, float]
    top_labels: tuple[LabelScore, ...]
    is_uncertain: bool


@dataclass(frozen=True)
class TemporalStudentBundle:
    schema_version: str
    feature_schema_version: str
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

    def encode_observations(self, observations: Sequence[TemporalStudentObservation]) -> tuple[np.ndarray, np.ndarray]:
        if not observations:
            raise ValueError("At least one temporal student observation is required.")
        frame_matrix = np.asarray(
            [vectorize_temporal_student_observation(observation, self.input_feature_names) for observation in observations],
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

    def predict(self, observations: Sequence[TemporalStudentObservation]) -> ActionPrediction:
        hidden, attention = self.encode_observations(observations)
        pooled = self.pool_hidden_states(hidden, attention)
        family_prediction = self.targets["eventFamily"].predict(pooled, model_version=self.model_version)
        event_family = family_prediction.label if not family_prediction.is_uncertain else "other"
        outcome_prediction = _predict_conditioned_target(
            self.targets["outcome"],
            pooled,
            model_version=self.model_version,
            allowed_labels=(
                OUTCOMES if family_prediction.is_uncertain else CONDITIONED_OUTCOME_LABELS.get(event_family, OUTCOMES)
            ),
        )
        subtype_prediction = _predict_conditioned_target(
            self.targets["shotSubtype"],
            pooled,
            model_version=self.model_version,
            allowed_labels=(
                SHOT_SUBTYPES
                if family_prediction.is_uncertain
                else CONDITIONED_SUBTYPE_LABELS.get(event_family, SHOT_SUBTYPES)
            ),
        )
        outcome = _resolve_student_outcome(event_family, outcome_prediction)
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
            _resolve_student_confidence(
                display_label=display_label,
                family_prediction=family_prediction,
                outcome_prediction=outcome_prediction,
                subtype_prediction=subtype_prediction,
                is_uncertain=is_uncertain,
            ),
            4,
        )
        metadata = {
            "temporal_student_model_version": self.model_version,
            "temporal_student_schema_version": self.schema_version,
            "temporal_student_feature_schema_version": self.feature_schema_version,
            "temporal_student_frame_count": len(observations),
            "temporal_student_attention": [round(float(value), 4) for value in attention.tolist()],
            "temporal_student_family_distribution": family_prediction.distribution,
            "temporal_student_outcome_distribution": outcome_prediction.distribution,
            "temporal_student_subtype_distribution": subtype_prediction.distribution,
            "temporal_student_family_top_labels": [item.model_dump(mode="json") for item in family_prediction.top_labels],
            "temporal_student_outcome_top_labels": [item.model_dump(mode="json") for item in outcome_prediction.top_labels],
            "temporal_student_subtype_top_labels": [item.model_dump(mode="json") for item in subtype_prediction.top_labels],
            "temporal_student_head_chain": {
                "eventFamily": event_family,
                "outcomeAllowedLabels": list(
                    OUTCOMES if family_prediction.is_uncertain else CONDITIONED_OUTCOME_LABELS.get(event_family, OUTCOMES)
                ),
                "shotSubtypeAllowedLabels": list(
                    SHOT_SUBTYPES
                    if family_prediction.is_uncertain
                    else CONDITIONED_SUBTYPE_LABELS.get(event_family, SHOT_SUBTYPES)
                ),
            },
        }
        return ActionPrediction(
            label=display_label,
            canonicalLabel=canonical_label,
            confidence=confidence_after_mapping,
            modelVersion=self.model_version,
            detectionMethod="temporal_student",
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


def vectorize_temporal_student_observation(
    observation: TemporalStudentObservation,
    input_feature_names: Sequence[str],
) -> np.ndarray:
    feature_values = build_temporal_student_feature_map(observation)
    return np.asarray([float(feature_values.get(name, 0.0)) for name in input_feature_names], dtype=np.float64)


def build_temporal_student_feature_map(observation: TemporalStudentObservation) -> dict[str, float]:
    structured = observation.structured_signals or {}
    perception = observation.perception_features or {}
    detection = observation.detection_features or {}
    tracking = observation.tracking_features or {}
    runtime = observation.runtime_features or {}

    ball_visible = _bool_float(perception.get("ballVisible", detection.get("ballVisible", runtime.get("ballVisible"))))
    hoop_visible = _bool_float(perception.get("hoopVisible", detection.get("hoopVisible", runtime.get("hoopVisible"))))
    ball_detection_confidence = _coerce_float(
        detection.get("ballDetectionConfidence", detection.get("ballConfidence", perception.get("basketballConfidence", ball_visible))),
    )
    hoop_detection_confidence = _coerce_float(
        detection.get("hoopDetectionConfidence", detection.get("hoopConfidence", perception.get("rimConfidence", hoop_visible))),
    )

    player_track_count = _coerce_float(
        tracking.get("playerTrackCount", tracking.get("playerCount", perception.get("playerCount"))),
        default=0.0,
    )
    tracked_player_count = _coerce_float(
        tracking.get("trackedPlayerCount", perception.get("trackedPlayerCount", player_track_count)),
        default=0.0,
    )
    tracked_ball_confidence = _coerce_float(
        tracking.get("trackedBallConfidence", perception.get("trackedBallConfidence", ball_detection_confidence)),
        default=0.0,
    )
    ball_track_count = _coerce_float(tracking.get("ballTrackCount", 1.0 if ball_visible > 0.0 else 0.0), default=0.0)
    rim_track_count = _coerce_float(tracking.get("rimTrackCount", 1.0 if hoop_visible > 0.0 else 0.0), default=0.0)
    tracking_continuity = _coerce_float(
        tracking.get("trackingContinuity", structured.get("samePlayContinuityScore", runtime.get("samePlayContinuityScore"))),
        default=0.0,
    )

    runtime_confidence = _coerce_float(runtime.get("confidence", runtime.get("runtimeConfidence")), default=0.0)
    runtime_label = _normalize_label(
        runtime.get("label")
        or runtime.get("canonicalLabel")
        or runtime.get("runtimeLabel")
        or runtime.get("displayLabel")
    )
    runtime_event_family = _normalize_label(runtime.get("eventFamily") or runtime.get("runtimeEventFamily"))
    runtime_outcome = _normalize_label(runtime.get("outcome") or runtime.get("runtimeOutcome"))
    runtime_shot_subtype = _normalize_label(runtime.get("shotSubtype") or runtime.get("runtimeShotSubtype") or "null")
    clip_duration_seconds = _coerce_float(runtime.get("clipDurationSeconds"), default=0.0)
    event_start_raw = _coerce_optional_float(runtime.get("eventStartSeconds"))
    event_center_raw = _coerce_optional_float(runtime.get("eventCenterSeconds"))
    event_end_raw = _coerce_optional_float(runtime.get("eventEndSeconds"))
    shot_release_raw = _coerce_optional_float(runtime.get("shotReleaseTimeSeconds"))
    ball_near_rim_raw = _coerce_optional_float(runtime.get("ballNearRimTimeSeconds"))
    ball_through_hoop_raw = _coerce_optional_float(runtime.get("ballThroughHoopTimeSeconds"))
    possession_change_raw = _coerce_optional_float(runtime.get("possessionChangeTimeSeconds"))
    transition_start_raw = _coerce_optional_float(runtime.get("transitionStartTimeSeconds"))
    event_start_seconds = float(event_start_raw or 0.0)
    event_center_seconds = float(event_center_raw or 0.0)
    event_end_seconds = float(event_end_raw or 0.0)
    shot_release_time_seconds = float(shot_release_raw or 0.0)
    ball_near_rim_time_seconds = float(ball_near_rim_raw or 0.0)
    ball_through_hoop_time_seconds = float(ball_through_hoop_raw or 0.0)
    possession_change_time_seconds = float(possession_change_raw or 0.0)
    transition_start_time_seconds = float(transition_start_raw or 0.0)
    event_duration_seconds = max(event_end_seconds - event_start_seconds, 0.0)
    localization_present = any(
        value is not None
        for value in (
            event_start_raw,
            event_center_raw,
            event_end_raw,
            shot_release_raw,
            ball_near_rim_raw,
            ball_through_hoop_raw,
            possession_change_raw,
            transition_start_raw,
        )
    )
    normalized_duration = clip_duration_seconds if clip_duration_seconds > 0.0 else max(event_end_seconds, event_center_seconds, 1.0)

    features = {
        "timestamp_seconds": _coerce_float(observation.timestamp_seconds, default=0.0),
        "ball_visible": ball_visible,
        "hoop_visible": hoop_visible,
        "ball_detection_confidence": ball_detection_confidence,
        "hoop_detection_confidence": hoop_detection_confidence,
        "ball_track_count": ball_track_count,
        "rim_track_count": rim_track_count,
        "player_track_count": player_track_count,
        "tracked_player_count": tracked_player_count,
        "tracked_ball_confidence": tracked_ball_confidence,
        "tracking_continuity": tracking_continuity,
        "detection_density": _coerce_float(detection.get("detectionDensity", perception.get("detectionDensity")), default=0.0),
        "tracking_density": _coerce_float(tracking.get("trackingDensity", perception.get("trackingDensity")), default=0.0),
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
        "basketball_confidence": _coerce_float(perception.get("basketballConfidence", perception.get("ballConfidence", ball_visible))),
        "rim_confidence": _coerce_float(perception.get("rimConfidence", perception.get("hoopConfidence", hoop_visible))),
        "runtime_confidence": runtime_confidence,
        "runtime_top_count": _coerce_float(runtime.get("topCount", runtime.get("runtimeTopCount")), default=0.0),
        "source_ref_present": _bool_float(runtime.get("sourceRefPresent", runtime.get("sourceRef"))),
        "human_verified": _bool_float(runtime.get("humanVerified")),
        "clip_duration_seconds": clip_duration_seconds,
        "event_start_seconds": event_start_seconds,
        "event_center_seconds": event_center_seconds,
        "event_end_seconds": event_end_seconds,
        "event_duration_seconds": event_duration_seconds,
        "event_localization_present": 1.0 if localization_present else 0.0,
        "event_localization_complete": 1.0 if event_start_raw is not None and event_center_raw is not None and event_end_raw is not None else 0.0,
        "event_center_seconds_norm": event_center_seconds / normalized_duration,
        "event_duration_seconds_norm": event_duration_seconds / normalized_duration,
        "shot_release_time_seconds": shot_release_time_seconds,
        "ball_near_rim_time_seconds": ball_near_rim_time_seconds,
        "ball_through_hoop_time_seconds": ball_through_hoop_time_seconds,
        "possession_change_time_seconds": possession_change_time_seconds,
        "transition_start_time_seconds": transition_start_time_seconds,
        "shot_release_offset_from_center": _time_offset(shot_release_time_seconds, event_center_seconds),
        "ball_near_rim_offset_from_center": _time_offset(ball_near_rim_time_seconds, event_center_seconds),
        "ball_through_hoop_offset_from_center": _time_offset(ball_through_hoop_time_seconds, event_center_seconds),
        "possession_change_offset_from_center": _time_offset(possession_change_time_seconds, event_center_seconds),
        "transition_start_offset_from_center": _time_offset(transition_start_time_seconds, event_center_seconds),
        "pre_roll_seconds": _coerce_float(runtime.get("preRollSeconds")),
        "post_roll_seconds": _coerce_float(runtime.get("postRollSeconds")),
        "source_event_count": _coerce_float(runtime.get("sourceEventCount"), default=1.0),
        "was_merged": _bool_float(runtime.get("wasMerged")),
    }

    _add_categorical(features, "source_domain", runtime.get("sourceDomain") or runtime.get("source_domain"))
    _add_categorical(features, "source_set", runtime.get("sourceSet") or runtime.get("source_set"))
    _add_categorical(features, "source_kind", runtime.get("sourceKind") or runtime.get("source_kind"))

    _add_categorical(features, "runtime_label", runtime_label)
    _add_categorical(features, "runtime_event_family", runtime_event_family)
    _add_categorical(features, "runtime_outcome", runtime_outcome)
    _add_categorical(features, "runtime_shot_subtype", runtime_shot_subtype)

    _add_categorical(features, "runtime_display_label", _normalize_label(runtime.get("displayLabel") or runtime.get("label")))
    _add_categorical(features, "runtime_video_mae", _normalize_label((runtime.get("videoMAE") or {}).get("topLabel")))
    _add_categorical(features, "runtime_xclip", _normalize_label((runtime.get("xclip") or {}).get("topLabel")))

    features["runtime_label_highlight"] = 1.0 if runtime_label == "highlight" else 0.0
    features["runtime_label_dunk"] = 1.0 if runtime_label == "dunk" else 0.0
    features["runtime_label_layup"] = 1.0 if runtime_label == "layup" else 0.0
    features["runtime_label_three_pointer"] = 1.0 if runtime_label in {"three", "three_pointer"} else 0.0
    features["runtime_label_make_shot"] = 1.0 if runtime_label in {"made_shot", "made"} else 0.0
    features["runtime_label_block"] = 1.0 if runtime_label == "block" else 0.0
    features["runtime_label_steal"] = 1.0 if runtime_label == "steal" else 0.0
    features["runtime_label_fast_break"] = 1.0 if runtime_label == "fast_break" else 0.0
    features["runtime_label_miss"] = 1.0 if runtime_label == "miss" else 0.0

    features["runtime_event_family_shot_attempt"] = 1.0 if runtime_event_family == "shot_attempt" else 0.0
    features["runtime_event_family_turnover"] = 1.0 if runtime_event_family == "turnover" else 0.0
    features["runtime_event_family_defensive_event"] = 1.0 if runtime_event_family == "defensive_event" else 0.0
    features["runtime_event_family_transition"] = 1.0 if runtime_event_family == "transition" else 0.0
    features["runtime_event_family_other"] = 1.0 if runtime_event_family == "other" else 0.0

    features["runtime_outcome_made"] = 1.0 if runtime_outcome == "made" else 0.0
    features["runtime_outcome_missed"] = 1.0 if runtime_outcome == "missed" else 0.0
    features["runtime_outcome_blocked"] = 1.0 if runtime_outcome == "blocked" else 0.0
    features["runtime_outcome_uncertain"] = 1.0 if runtime_outcome == "uncertain" else 0.0

    features["runtime_shot_subtype_dunk"] = 1.0 if runtime_shot_subtype == "dunk" else 0.0
    features["runtime_shot_subtype_layup"] = 1.0 if runtime_shot_subtype == "layup" else 0.0
    features["runtime_shot_subtype_jumper"] = 1.0 if runtime_shot_subtype == "jumper" else 0.0
    features["runtime_shot_subtype_three"] = 1.0 if runtime_shot_subtype == "three" else 0.0
    features["runtime_shot_subtype_putback"] = 1.0 if runtime_shot_subtype == "putback" else 0.0
    features["runtime_shot_subtype_null"] = 1.0 if runtime_shot_subtype in {"null", ""} else 0.0

    return features


def default_temporal_student_feature_names() -> tuple[str, ...]:
    return (
        "timestamp_seconds",
        "ball_visible",
        "hoop_visible",
        "ball_detection_confidence",
        "hoop_detection_confidence",
        "ball_track_count",
        "rim_track_count",
        "player_track_count",
        "tracked_player_count",
        "tracked_ball_confidence",
        "tracking_continuity",
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
        "runtime_confidence",
        "runtime_top_count",
        "source_ref_present",
        "human_verified",
        "clip_duration_seconds",
        "event_start_seconds",
        "event_center_seconds",
        "event_end_seconds",
        "event_duration_seconds",
        "event_localization_present",
        "event_localization_complete",
        "event_center_seconds_norm",
        "event_duration_seconds_norm",
        "shot_release_time_seconds",
        "ball_near_rim_time_seconds",
        "ball_through_hoop_time_seconds",
        "possession_change_time_seconds",
        "transition_start_time_seconds",
        "shot_release_offset_from_center",
        "ball_near_rim_offset_from_center",
        "ball_through_hoop_offset_from_center",
        "possession_change_offset_from_center",
        "transition_start_offset_from_center",
        "pre_roll_seconds",
        "post_roll_seconds",
        "source_event_count",
        "was_merged",
        "source_domain=hard_negative",
        "source_domain=live_runtime",
        "source_domain=live_staging",
        "source_domain=live_shadow",
        "source_domain=staging_smoke",
        "source_domain=teacher_pseudo",
        "source_domain=benchmark_eval",
        "source_domain=broadcast",
        "source_domain=fixed_camera_indoor",
        "source_domain=fixed_camera_outdoor",
        "source_domain=phone_casual",
        "source_kind=gold",
        "source_kind=runtime",
        "source_kind=silver",
        "source_kind=disagreement",
        "source_set=gold_set",
        "source_set=silver_set",
        "source_set=disagreement_queue",
        "source_set=phase4_in_domain",
        "source_set=phase4_pseudo_labels",
        "source_set=runtime_inference",
        "runtime_label=highlight",
        "runtime_label=dunk",
        "runtime_label=layup",
        "runtime_label=three_pointer",
        "runtime_label=made_shot",
        "runtime_label=block",
        "runtime_label=steal",
        "runtime_label=fast_break",
        "runtime_label=miss",
        "runtime_event_family=shot_attempt",
        "runtime_event_family=turnover",
        "runtime_event_family=defensive_event",
        "runtime_event_family=transition",
        "runtime_event_family=other",
        "runtime_outcome=made",
        "runtime_outcome=missed",
        "runtime_outcome=blocked",
        "runtime_outcome=uncertain",
        "runtime_shot_subtype=dunk",
        "runtime_shot_subtype=layup",
        "runtime_shot_subtype=jumper",
        "runtime_shot_subtype=three",
        "runtime_shot_subtype=putback",
        "runtime_shot_subtype=null",
        "runtime_display_label=highlight",
        "runtime_display_label=dunk",
        "runtime_display_label=layup",
        "runtime_display_label=three_pointer",
        "runtime_display_label=made_shot",
        "runtime_display_label=block",
        "runtime_display_label=steal",
        "runtime_display_label=fast_break",
        "runtime_display_label=miss",
        "runtime_video_mae=highlight",
        "runtime_video_mae=dunk",
        "runtime_video_mae=layup",
        "runtime_video_mae=three_pointer",
        "runtime_video_mae=made_shot",
        "runtime_video_mae=block",
        "runtime_video_mae=steal",
        "runtime_video_mae=fast_break",
        "runtime_video_mae=miss",
        "runtime_xclip=highlight",
        "runtime_xclip=dunk",
        "runtime_xclip=layup",
        "runtime_xclip=three_pointer",
        "runtime_xclip=made_shot",
        "runtime_xclip=block",
        "runtime_xclip=steal",
        "runtime_xclip=fast_break",
        "runtime_xclip=miss",
        "runtime_label_highlight",
        "runtime_label_dunk",
        "runtime_label_layup",
        "runtime_label_three_pointer",
        "runtime_label_make_shot",
        "runtime_label_block",
        "runtime_label_steal",
        "runtime_label_fast_break",
        "runtime_label_miss",
        "runtime_event_family_shot_attempt",
        "runtime_event_family_turnover",
        "runtime_event_family_defensive_event",
        "runtime_event_family_transition",
        "runtime_event_family_other",
        "runtime_outcome_made",
        "runtime_outcome_missed",
        "runtime_outcome_blocked",
        "runtime_outcome_uncertain",
        "runtime_shot_subtype_dunk",
        "runtime_shot_subtype_layup",
        "runtime_shot_subtype_jumper",
        "runtime_shot_subtype_three",
        "runtime_shot_subtype_putback",
        "runtime_shot_subtype_null",
    )


def load_temporal_student_bundle(path: Path | None = None) -> TemporalStudentBundle:
    bundle_path = path or TEMPORAL_STUDENT_BUNDLE_PATH
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
            top_k=int(target_payload.get("topK", MAX_TEMPORAL_STUDENT_TOPK)),
        )
        for target_name, target_payload in (payload.get("targets") or {}).items()
    }
    return TemporalStudentBundle(
        schema_version=str(payload.get("schemaVersion", TEMPORAL_STUDENT_SCHEMA_VERSION)),
        feature_schema_version=str(payload.get("featureSchemaVersion", TEMPORAL_STUDENT_FEATURE_SCHEMA_VERSION)),
        model_version=str(payload.get("modelVersion", TEMPORAL_STUDENT_MODEL_VERSION)),
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
def get_temporal_student_bundle(path: str | None = None) -> TemporalStudentBundle | None:
    bundle_path = Path(path) if path else TEMPORAL_STUDENT_BUNDLE_PATH
    if not bundle_path.exists():
        return None
    return load_temporal_student_bundle(bundle_path)


def write_temporal_student_bundle(path: Path, bundle: TemporalStudentBundle) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": bundle.schema_version,
        "featureSchemaVersion": bundle.feature_schema_version,
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


def _resolve_student_outcome(event_family: str, prediction: TemporalTargetPrediction) -> str:
    if event_family == "defensive_event":
        return "blocked" if prediction.label == "blocked" and not prediction.is_uncertain else "uncertain"
    if event_family != "shot_attempt":
        return "uncertain"
    if prediction.is_uncertain:
        return "uncertain"
    return prediction.label


def _predict_conditioned_target(
    target: TemporalTargetModel,
    pooled: np.ndarray,
    *,
    model_version: str,
    allowed_labels: Sequence[str],
) -> TemporalStudentTargetPrediction:
    allowed = {str(label) for label in allowed_labels}
    if not allowed or allowed == set(target.classes):
        base_prediction = target.predict(pooled, model_version=model_version)
        return TemporalStudentTargetPrediction(
            label=base_prediction.label,
            confidence=base_prediction.confidence,
            margin=base_prediction.margin,
            distribution=base_prediction.distribution,
            top_labels=base_prediction.top_labels,
            is_uncertain=base_prediction.is_uncertain,
        )

    logits = np.matmul(np.asarray(target.weight, dtype=np.float64), pooled) + np.asarray(
        target.bias,
        dtype=np.float64,
    )
    masked_logits = np.full_like(logits, -1e9, dtype=np.float64)
    allowed_indices = [index for index, label in enumerate(target.classes) if label in allowed]
    if not allowed_indices:
        return _predict_conditioned_target(
            target,
            pooled,
            model_version=model_version,
            allowed_labels=target.classes,
        )
    for index in allowed_indices:
        masked_logits[index] = logits[index]
    probabilities = _softmax(masked_logits / max(target.temperature, 1e-3))
    ranked = list(np.argsort(probabilities)[::-1])
    top_index = ranked[0]
    second_probability = float(probabilities[ranked[1]]) if len(ranked) > 1 else 0.0
    top_probability = float(probabilities[top_index])
    margin = max(top_probability - second_probability, 0.0)
    distribution = {
        str(label): round(float(probabilities[index]), 4)
        for index, label in enumerate(target.classes)
        if label in allowed
    }
    top_labels = tuple(
        LabelScore(
            label=str(target.classes[index]),
            confidence=round(float(probabilities[index]), 4),
            modelVersion=model_version,
        )
        for index in ranked[: target.top_k]
        if target.classes[index] in allowed
    )
    return TemporalStudentTargetPrediction(
        label=str(target.classes[top_index]),
        confidence=round(top_probability, 4),
        margin=round(margin, 4),
        distribution=distribution,
        top_labels=top_labels,
        is_uncertain=top_probability < target.uncertainty_threshold or margin < target.margin_threshold,
    )


def _resolve_student_confidence(
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
    if is_uncertain and display_label == "Highlight":
        confidence = min(confidence, 0.46)
    return min(max(confidence, 0.0), 1.0)


def _add_categorical(features: dict[str, float], prefix: str, value: Any) -> None:
    label = _normalize_label(value)
    if label is None:
        return
    features[f"{prefix}={label}"] = 1.0


def _normalize_label(value: Any) -> str | None:
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


def _bool_float(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value is None:
        return 0.0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return 1.0
        if lowered in {"false", "0", "no", "n"}:
            return 0.0
    return 1.0 if bool(value) else 0.0


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


def _time_offset(value: float, center: float) -> float:
    if value <= 0.0 or center <= 0.0:
        return 0.0
    return round(value - center, 4)


def _coerce_optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

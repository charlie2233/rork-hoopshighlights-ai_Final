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


TEMPORAL_EVENT_DETECTOR_SCHEMA_VERSION = "temporal-event-detector-v3"
TEMPORAL_EVENT_DETECTOR_FEATURE_SCHEMA_VERSION = "temporal-event-detector-feature-v4"
TEMPORAL_EVENT_DETECTOR_MODEL_VERSION = "temporal-event-detector-tridet-shot-specialist-v1"
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
PROPOSAL_RANK_LABELS = ("secondary", "primary")
PROPOSAL_ACCEPT_LABELS = ("reject", "accept")
SHOT_SPECIALIST_SUBTYPE_LABELS = ("dunk", "layup", "jumper", "three", "putback", "uncertain")
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
SHOT_SPECIALIST_SIGNAL_FEATURES = (
    "ball_near_rim",
    "ball_to_rim_distance",
    "ball_to_rim_likelihood",
    "ball_above_rim",
    "ball_arc_apex",
    "ball_vertical_velocity_y",
    "ball_vertical_speed_near_rim",
    "ball_through_hoop_likelihood",
    "player_to_rim_distance",
    "defender_proximity_at_shot",
    "shot_release_candidate",
    "ball_detection_confidence",
    "hoop_detection_confidence",
    "tracked_ball_confidence",
    "basketball_confidence",
    "rim_confidence",
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
    proposal_index: int
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
    spotter_ranking_score: float
    boundary_score: float


@dataclass(frozen=True)
class RankedTemporalEventProposal:
    proposal: TemporalEventProposal
    rejector_prediction: TemporalTargetPrediction
    ranker_prediction: TemporalTargetPrediction
    acceptor_prediction: TemporalTargetPrediction
    acceptance_score: float
    competition_margin: float
    accepted: bool


@dataclass(frozen=True)
class TemporalShotSpecialistBundle:
    feature_names: tuple[str, ...]
    outcome_target: TemporalTargetModel
    subtype_target: TemporalTargetModel


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
    proposal_ranker_feature_names: tuple[str, ...] = ()
    proposal_ranker: TemporalTargetModel | None = None
    proposal_acceptor_feature_names: tuple[str, ...] = ()
    proposal_acceptor: TemporalTargetModel | None = None
    shot_specialist_feature_names: tuple[str, ...] = ()
    shot_specialist_outcome: TemporalTargetModel | None = None
    shot_specialist_subtype: TemporalTargetModel | None = None
    proposal_acceptance_threshold: float = 0.62
    proposal_competition_margin_threshold: float = 0.06
    proposal_candidate_limit: int = 4

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
        return self.propose_candidates(observations, max_candidates=1)[0]

    def propose_candidates(
        self,
        observations: Sequence[TemporalStudentObservation],
        *,
        max_candidates: int | None = None,
    ) -> list[TemporalEventProposal]:
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
        candidate_specs = self._score_candidate_specs(
            frame_family_probabilities=frame_family_probabilities,
            eventness=eventness,
            start_scores=start_scores,
            end_scores=end_scores,
        )
        proposals: list[TemporalEventProposal] = []
        seen_segments: set[tuple[int, int]] = set()
        limit = max(1, int(max_candidates or self.proposal_candidate_limit))
        for spec in candidate_specs:
            center_index = int(spec["center_index"])
            start_index = int(np.argmax(start_scores[: center_index + 1])) if center_index >= 0 else 0
            end_index = (
                int(center_index + np.argmax(end_scores[center_index:]))
                if center_index < len(observations)
                else len(observations) - 1
            )
            if end_index < start_index:
                end_index = start_index
            segment_key = (start_index, end_index)
            if segment_key in seen_segments:
                continue
            seen_segments.add(segment_key)
            pooled, segment_attention = self._pool_segment(hidden, start_index=start_index, end_index=end_index)
            proposals.append(
                TemporalEventProposal(
                    proposal_index=len(proposals),
                    start_index=start_index,
                    center_index=center_index,
                    end_index=end_index,
                    start_seconds=round(float(observations[start_index].timestamp_seconds), 4),
                    center_seconds=round(float(observations[center_index].timestamp_seconds), 4),
                    end_seconds=round(float(observations[end_index].timestamp_seconds), 4),
                    event_score=round(float(spec["event_score"]), 4),
                    event_margin=round(float(spec["event_margin"]), 4),
                    coarse_event_family=str(spec["coarse_event_family"]),
                    hidden=hidden,
                    pooled_vector=pooled,
                    segment_attention=segment_attention,
                    eventness=eventness,
                    start_scores=start_scores,
                    end_scores=end_scores,
                    event_spotter_prediction=spec["prediction"],
                    spotter_ranking_score=round(float(spec["ranking_score"]), 4),
                    boundary_score=round(float(spec["boundary_score"]), 4),
                )
            )
            if len(proposals) >= limit:
                break
        if not proposals:
            raise ValueError("Unable to generate at least one temporal proposal.")
        return proposals

    def predict(self, observations: Sequence[TemporalStudentObservation]) -> ActionPrediction:
        proposals = self.propose_candidates(observations)
        scored_proposals = self._score_ranked_proposals(observations, proposals)
        selected = scored_proposals[0]
        proposal = selected.proposal
        rejector_prediction = selected.rejector_prediction
        ranker_prediction = selected.ranker_prediction
        acceptor_prediction = selected.acceptor_prediction
        proposal_accepted = selected.accepted
        acceptance_probability = _calibrated_acceptance_probability(
            acceptor_prediction=acceptor_prediction,
            fallback_score=selected.acceptance_score,
        )
        acceptance_energy = _prediction_energy(acceptor_prediction)
        gate_rejection_reason = _family_gate_rejection_reason(
            proposal_accepted=proposal_accepted,
            rejector_prediction=rejector_prediction,
            ranker_prediction=ranker_prediction,
            acceptance_probability=acceptance_probability,
            competition_margin=selected.competition_margin,
            acceptance_threshold=self.proposal_acceptance_threshold,
            competition_margin_threshold=self.proposal_competition_margin_threshold,
        )
        classifier_gate_open = gate_rejection_reason is None
        likely_shot_attempt = False
        shot_specialist_features: dict[str, float] = {}
        shot_specialist_abstained = False

        subtype_gate_open = False
        promoted_generic_shot_attempt = False

        if proposal_accepted:
            family_prediction = _predict_conditioned_target(
                self.targets["eventFamily"],
                proposal.pooled_vector,
                model_version=self.model_version,
                allowed_labels=EVENT_FAMILIES,
            )
            event_family = family_prediction.label
            if family_prediction.is_uncertain or event_family not in EVENT_FAMILIES or event_family == "other":
                event_family = "other"
            if classifier_gate_open:
                if event_family == "shot_attempt":
                    shot_specialist_features = build_shot_specialist_feature_map(
                        observations=observations,
                        proposal=proposal,
                        ranked_proposal=selected,
                    )
                    likely_shot_attempt = True
                    outcome_prediction = self._predict_shot_specialist_target(
                        target_name="shotOutcomeSpecialist",
                        feature_map=shot_specialist_features,
                        fallback_target=self.targets["outcome"],
                        fallback_vector=proposal.pooled_vector,
                        allowed_labels=CONDITIONED_OUTCOME_LABELS.get(event_family, OUTCOMES),
                    )
                    outcome = _resolve_outcome(event_family, outcome_prediction)
                    subtype_gate_open = _should_attempt_shot_subtype(
                        outcome=outcome,
                        outcome_prediction=outcome_prediction,
                        acceptance_score=selected.acceptance_score,
                    )
                    if subtype_gate_open:
                        subtype_prediction = self._predict_shot_specialist_target(
                            target_name="shotSubtypeSpecialist",
                            feature_map=shot_specialist_features,
                            fallback_target=self.targets["shotSubtype"],
                            fallback_vector=proposal.pooled_vector,
                            allowed_labels=SHOT_SPECIALIST_SUBTYPE_LABELS,
                        )
                    else:
                        subtype_prediction = _fallback_temporal_prediction(
                            label="uncertain",
                            confidence=min(max(outcome_prediction.confidence, 0.22), 0.62),
                            model_version=self.model_version,
                        )
                else:
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
        if proposal_accepted and event_family == "shot_attempt":
            shot_subtype = _resolve_shot_specialist_subtype(outcome, subtype_prediction)
            shot_specialist_abstained = outcome != "uncertain" and shot_subtype is None
        elif (
            proposal_accepted
            and not subtype_prediction.is_uncertain
            and subtype_prediction.label not in {"null", "unknown"}
        ):
            shot_subtype = subtype_prediction.label
        using_shot_specialist = (
            proposal_accepted
            and classifier_gate_open
            and likely_shot_attempt
            and event_family == "shot_attempt"
            and bool(shot_specialist_features)
        )
        promoted_generic_shot_attempt = _should_promote_generic_shot_attempt(
            proposal_accepted=proposal_accepted,
            classifier_gate_open=classifier_gate_open,
            event_family=event_family,
            outcome=outcome,
            family_prediction=family_prediction,
            outcome_prediction=outcome_prediction,
            shot_specialist_used=using_shot_specialist,
            acceptance_score=selected.acceptance_score,
        )
        outcome_target = (
            self.shot_specialist_outcome
            if using_shot_specialist and self.shot_specialist_outcome is not None
            else self.targets["outcome"]
        )
        subtype_target = (
            self.shot_specialist_subtype
            if using_shot_specialist and self.shot_specialist_subtype is not None
            else self.targets["shotSubtype"]
        )

        if promoted_generic_shot_attempt:
            canonical_label, display_label = "shot_attempt", "Shot Attempt"
        else:
            canonical_label, display_label = derive_runtime_display_label(
                event_family=event_family,
                outcome=outcome,
                shot_subtype=shot_subtype,
            )
        is_uncertain = (
            not proposal_accepted
            or not classifier_gate_open
            or rejector_prediction.is_uncertain
            or ranker_prediction.is_uncertain
            or acceptor_prediction.is_uncertain
            or rejector_prediction.label != "real_event"
            or ranker_prediction.label != "primary"
            or family_prediction.is_uncertain
            or selected.competition_margin < self.proposal_competition_margin_threshold
            or selected.acceptance_score < (self.proposal_acceptance_threshold + 0.08)
            or (classifier_gate_open and event_family == "shot_attempt" and outcome == "uncertain")
            or (
                using_shot_specialist
                and outcome == "made"
                and (shot_specialist_abstained or subtype_prediction.is_uncertain)
            )
        )
        confidence_before_mapping = selected.acceptance_score if proposal_accepted else max(
            min(selected.acceptance_score, proposal.event_score),
            0.18,
        )
        if proposal_accepted:
            resolved_confidence = _resolve_student_confidence(
                    display_label=display_label,
                    event_spotter_prediction=proposal.event_spotter_prediction,
                    family_prediction=family_prediction,
                    outcome_prediction=outcome_prediction,
                    subtype_prediction=subtype_prediction,
                    gate_open=classifier_gate_open,
                    is_uncertain=is_uncertain,
                    outcome=outcome,
                    shot_specialist_used=using_shot_specialist,
                    shot_specialist_abstained=shot_specialist_abstained,
                )
            confidence_after_mapping = round(
                min(
                    resolved_confidence,
                    max(selected.acceptance_score - (0.08 if is_uncertain else 0.0), 0.18),
                ),
                4,
            )
        else:
            confidence_after_mapping = round(
                max(min(selected.acceptance_score, rejector_prediction.confidence, 0.49) - 0.04, 0.18),
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
            "temporal_event_detector_proposal_acceptance_threshold": round(self.proposal_acceptance_threshold, 4),
            "temporal_event_detector_proposal_competition_margin_threshold": round(
                self.proposal_competition_margin_threshold,
                4,
            ),
            "temporal_event_detector_proposal_candidate_count": len(scored_proposals),
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
            "temporal_event_detector_proposal_rank_score": proposal.spotter_ranking_score,
            "temporal_event_detector_proposal_acceptance_score": round(selected.acceptance_score, 4),
            "temporal_event_detector_proposal_competition_margin": round(selected.competition_margin, 4),
            "temporal_event_detector_boundary_score": proposal.boundary_score,
            "temporal_event_detector_eventness": [round(float(value), 4) for value in proposal.eventness.tolist()],
            "temporal_event_detector_start_scores": [round(float(value), 4) for value in proposal.start_scores.tolist()],
            "temporal_event_detector_end_scores": [round(float(value), 4) for value in proposal.end_scores.tolist()],
            "temporal_event_detector_segment_attention": [round(float(value), 4) for value in proposal.segment_attention.tolist()],
            "temporal_event_detector_event_family": proposal.coarse_event_family,
            "temporal_event_detector_gate_open": classifier_gate_open,
            "temporal_event_detector_proposal_accepted": proposal_accepted,
            "temporal_event_detector_classifier_gate_open": classifier_gate_open,
            "temporal_event_detector_family_gate_open": classifier_gate_open,
            "temporal_event_detector_family_gate_rejection_reason": gate_rejection_reason,
            "temporal_event_detector_proposal_rejector_label": rejector_prediction.label,
            "temporal_event_detector_proposal_rejector_confidence": round(rejector_prediction.confidence, 4),
            "temporal_event_detector_proposal_rejector_margin": round(rejector_prediction.margin, 4),
            "temporal_event_detector_proposal_rejector_distribution": rejector_prediction.distribution,
            "temporal_event_detector_proposal_rejector_top_labels": [
                item.model_dump(mode="json") for item in rejector_prediction.top_labels
            ],
            "temporal_event_detector_proposal_ranker_label": ranker_prediction.label,
            "temporal_event_detector_proposal_ranker_confidence": round(ranker_prediction.confidence, 4),
            "temporal_event_detector_proposal_ranker_margin": round(ranker_prediction.margin, 4),
            "temporal_event_detector_proposal_ranker_distribution": ranker_prediction.distribution,
            "temporal_event_detector_proposal_ranker_top_labels": [
                item.model_dump(mode="json") for item in ranker_prediction.top_labels
            ],
            "temporal_event_detector_proposal_acceptor_label": acceptor_prediction.label,
            "temporal_event_detector_proposal_acceptor_confidence": round(acceptor_prediction.confidence, 4),
            "temporal_event_detector_proposal_acceptor_margin": round(acceptor_prediction.margin, 4),
            "temporal_event_detector_proposal_acceptor_distribution": acceptor_prediction.distribution,
            "temporal_event_detector_proposal_acceptor_top_labels": [
                item.model_dump(mode="json") for item in acceptor_prediction.top_labels
            ],
            "temporal_event_detector_proposal_acceptance_raw_score": round(float(selected.acceptance_score), 4),
            "temporal_event_detector_proposal_acceptance_probability": round(float(acceptance_probability), 4),
            "temporal_event_detector_proposal_acceptance_energy": acceptance_energy,
            "temporal_event_detector_proposal_rejector_temperature": (
                round(self.proposal_rejector.temperature, 4) if self.proposal_rejector is not None else None
            ),
            "temporal_event_detector_proposal_rejector_uncertainty_threshold": (
                round(self.proposal_rejector.uncertainty_threshold, 4) if self.proposal_rejector is not None else None
            ),
            "temporal_event_detector_proposal_rejector_margin_threshold": (
                round(self.proposal_rejector.margin_threshold, 4) if self.proposal_rejector is not None else None
            ),
            "temporal_event_detector_proposal_ranker_temperature": (
                round(self.proposal_ranker.temperature, 4) if self.proposal_ranker is not None else None
            ),
            "temporal_event_detector_proposal_ranker_uncertainty_threshold": (
                round(self.proposal_ranker.uncertainty_threshold, 4) if self.proposal_ranker is not None else None
            ),
            "temporal_event_detector_proposal_ranker_margin_threshold": (
                round(self.proposal_ranker.margin_threshold, 4) if self.proposal_ranker is not None else None
            ),
            "temporal_event_detector_proposal_acceptor_temperature": (
                round(self.proposal_acceptor.temperature, 4) if self.proposal_acceptor is not None else None
            ),
            "temporal_event_detector_proposal_acceptor_uncertainty_threshold": (
                round(self.proposal_acceptor.uncertainty_threshold, 4) if self.proposal_acceptor is not None else None
            ),
            "temporal_event_detector_proposal_acceptor_margin_threshold": (
                round(self.proposal_acceptor.margin_threshold, 4) if self.proposal_acceptor is not None else None
            ),
            "temporal_event_detector_shot_specialist_used": using_shot_specialist,
            "temporal_event_detector_shot_head_invoked": using_shot_specialist,
            "temporal_event_detector_likely_shot_attempt": likely_shot_attempt,
            "temporal_event_detector_shot_specialist_abstained": shot_specialist_abstained,
            "temporal_event_detector_shot_specialist_feature_count": len(shot_specialist_features),
            "temporal_event_detector_shot_specialist_subtype_gate_open": subtype_gate_open,
            "temporal_event_detector_generic_shot_attempt_promoted": promoted_generic_shot_attempt,
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
            "temporal_event_detector_outcome_temperature": round(outcome_target.temperature, 4),
            "temporal_event_detector_outcome_uncertainty_threshold": round(
                outcome_target.uncertainty_threshold,
                4,
            ),
            "temporal_event_detector_outcome_margin_threshold": round(outcome_target.margin_threshold, 4),
            "temporal_event_detector_subtype_temperature": round(subtype_target.temperature, 4),
            "temporal_event_detector_subtype_uncertainty_threshold": round(
                subtype_target.uncertainty_threshold,
                4,
            ),
            "temporal_event_detector_subtype_margin_threshold": round(subtype_target.margin_threshold, 4),
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
            "temporal_event_detector_shot_specialist_features": (
                {name: round(float(value), 4) for name, value in shot_specialist_features.items()}
                if using_shot_specialist
                else None
            ),
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

    def _score_candidate_specs(
        self,
        *,
        frame_family_probabilities: np.ndarray,
        eventness: np.ndarray,
        start_scores: np.ndarray,
        end_scores: np.ndarray,
    ) -> list[dict[str, Any]]:
        candidate_specs: list[dict[str, Any]] = []
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
            coarse_family = (
                str(EVENT_FAMILIES[best_non_other_index])
                if confidence_score >= self.event_score_threshold
                else "other"
            )
            prediction = TemporalStudentTargetPrediction(
                label=coarse_family,
                confidence=round(confidence_score, 4),
                margin=round(max(best_non_other_probability - second_probability, 0.0), 4),
                distribution=distribution,
                top_labels=top_labels,
                is_uncertain=(
                    confidence_score < self.event_score_threshold
                    or max(best_non_other_probability - second_probability, 0.0) < self.event_margin_threshold
                ),
            )
            candidate_specs.append(
                {
                    "center_index": index,
                    "coarse_event_family": coarse_family,
                    "prediction": prediction,
                    "event_score": round(confidence_score, 4),
                    "event_margin": round(max(best_non_other_probability - second_probability, 0.0), 4),
                    "boundary_score": round(boundary_score, 4),
                    "ranking_score": round(
                        max(ranking_score, other_confidence * 0.92 if EVENT_FAMILIES[top_index] == "other" else 0.0),
                        4,
                    ),
                }
            )
        candidate_specs.sort(key=lambda spec: float(spec["ranking_score"]), reverse=True)
        return candidate_specs

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

    def _predict_proposal_ranker(
        self,
        observations: Sequence[TemporalStudentObservation],
        proposal: TemporalEventProposal,
    ) -> TemporalTargetPrediction:
        if self.proposal_ranker is None or not self.proposal_ranker_feature_names:
            return _fallback_target_prediction(
                label="primary" if proposal.coarse_event_family != "other" and not proposal.event_spotter_prediction.is_uncertain else "secondary",
                confidence=proposal.event_spotter_prediction.confidence,
                margin=proposal.event_spotter_prediction.margin,
                model_version=self.model_version,
                classes=PROPOSAL_RANK_LABELS,
                default_label="secondary",
            )
        feature_map = build_proposal_rejector_feature_map(observations=observations, proposal=proposal)
        feature_vector = np.asarray(
            [float(feature_map.get(name, 0.0)) for name in self.proposal_ranker_feature_names],
            dtype=np.float64,
        )
        return self.proposal_ranker.predict(feature_vector, model_version=self.model_version)

    def _predict_proposal_acceptor(
        self,
        *,
        proposal: TemporalEventProposal,
        rejector_prediction: TemporalTargetPrediction,
        ranker_prediction: TemporalTargetPrediction,
    ) -> TemporalTargetPrediction:
        if self.proposal_acceptor is None or not self.proposal_acceptor_feature_names:
            conservative_accept = (
                proposal.coarse_event_family != "other"
                and not proposal.event_spotter_prediction.is_uncertain
                and proposal.event_score >= max(self.event_score_threshold + 0.08, 0.4)
                and proposal.event_margin >= max(self.event_margin_threshold + 0.02, 0.05)
                and rejector_prediction.label == "real_event"
                and not rejector_prediction.is_uncertain
                and ranker_prediction.label == "primary"
                and not ranker_prediction.is_uncertain
            )
            return _fallback_target_prediction(
                label="accept" if conservative_accept else "reject",
                confidence=min(
                    0.94 if conservative_accept else 0.82,
                    max(
                        proposal.event_spotter_prediction.confidence,
                        rejector_prediction.confidence,
                        ranker_prediction.confidence,
                    ),
                ),
                margin=max(
                    0.08 if conservative_accept else 0.12,
                    min(
                        proposal.event_spotter_prediction.margin,
                        rejector_prediction.margin,
                        ranker_prediction.margin,
                    ),
                ),
                model_version=self.model_version,
                classes=PROPOSAL_ACCEPT_LABELS,
                default_label="reject",
            )
        feature_map = build_proposal_acceptor_feature_map(
            proposal=proposal,
            rejector_prediction=rejector_prediction,
            ranker_prediction=ranker_prediction,
        )
        feature_vector = np.asarray(
            [float(feature_map.get(name, 0.0)) for name in self.proposal_acceptor_feature_names],
            dtype=np.float64,
        )
        return self.proposal_acceptor.predict(feature_vector, model_version=self.model_version)

    def _predict_shot_specialist_target(
        self,
        *,
        target_name: str,
        feature_map: dict[str, float],
        fallback_target: TemporalTargetModel,
        fallback_vector: np.ndarray,
        allowed_labels: Sequence[str],
    ) -> TemporalTargetPrediction:
        if target_name == "shotOutcomeSpecialist":
            target = self.shot_specialist_outcome
        elif target_name == "shotSubtypeSpecialist":
            target = self.shot_specialist_subtype
        else:
            target = None
        if target is None or not self.shot_specialist_feature_names:
            return _predict_conditioned_target(
                fallback_target,
                fallback_vector,
                model_version=self.model_version,
                allowed_labels=allowed_labels,
            )
        feature_vector = np.asarray(
            [float(feature_map.get(name, 0.0)) for name in self.shot_specialist_feature_names],
            dtype=np.float64,
        )
        return target.predict(feature_vector, model_version=self.model_version)

    def _score_ranked_proposals(
        self,
        observations: Sequence[TemporalStudentObservation],
        proposals: Sequence[TemporalEventProposal],
    ) -> list[RankedTemporalEventProposal]:
        staged: list[
            tuple[
                TemporalEventProposal,
                TemporalTargetPrediction,
                TemporalTargetPrediction,
                TemporalTargetPrediction,
                float,
            ]
        ] = []
        for proposal in proposals:
            rejector_prediction = self._predict_proposal_rejector(observations, proposal)
            ranker_prediction = self._predict_proposal_ranker(observations, proposal)
            acceptor_prediction = self._predict_proposal_acceptor(
                proposal=proposal,
                rejector_prediction=rejector_prediction,
                ranker_prediction=ranker_prediction,
            )
            acceptance_score = self._proposal_acceptance_score(
                proposal,
                rejector_prediction,
                ranker_prediction,
                acceptor_prediction,
            )
            staged.append((proposal, rejector_prediction, ranker_prediction, acceptor_prediction, acceptance_score))
        staged.sort(key=lambda item: item[4], reverse=True)
        scored: list[RankedTemporalEventProposal] = []
        for index, (proposal, rejector_prediction, ranker_prediction, acceptor_prediction, acceptance_score) in enumerate(staged):
            next_score = staged[index + 1][4] if index + 1 < len(staged) else 0.0
            competition_margin = round(max(acceptance_score - next_score, 0.0), 4)
            accepted = self._proposal_accepted(
                proposal=proposal,
                rejector_prediction=rejector_prediction,
                ranker_prediction=ranker_prediction,
                acceptor_prediction=acceptor_prediction,
                acceptance_score=acceptance_score,
                competition_margin=competition_margin,
            )
            scored.append(
                RankedTemporalEventProposal(
                    proposal=proposal,
                    rejector_prediction=rejector_prediction,
                    ranker_prediction=ranker_prediction,
                    acceptor_prediction=acceptor_prediction,
                    acceptance_score=acceptance_score,
                    competition_margin=competition_margin,
                    accepted=accepted,
                )
            )
        return scored

    def _proposal_acceptance_score(
        self,
        proposal: TemporalEventProposal,
        rejector_prediction: TemporalTargetPrediction,
        ranker_prediction: TemporalTargetPrediction,
        acceptor_prediction: TemporalTargetPrediction,
    ) -> float:
        if self.proposal_acceptor is not None:
            return round(
                float(
                    acceptor_prediction.distribution.get(
                        "accept",
                        acceptor_prediction.confidence if acceptor_prediction.label == "accept" else 1.0 - acceptor_prediction.confidence,
                    )
                ),
                4,
            )
        verifier_real_event_score = float(
            rejector_prediction.distribution.get(
                "real_event",
                rejector_prediction.confidence if rejector_prediction.label == "real_event" else 1.0 - rejector_prediction.confidence,
            )
        )
        rank_primary_score = float(
            ranker_prediction.distribution.get(
                "primary",
                ranker_prediction.confidence if ranker_prediction.label == "primary" else 1.0 - ranker_prediction.confidence,
            )
        )
        return round(
            (0.42 * float(proposal.event_score))
            + (0.38 * verifier_real_event_score)
            + (0.2 * rank_primary_score),
            4,
        )

    def _proposal_accepted(
        self,
        *,
        proposal: TemporalEventProposal,
        rejector_prediction: TemporalTargetPrediction,
        ranker_prediction: TemporalTargetPrediction,
        acceptor_prediction: TemporalTargetPrediction,
        acceptance_score: float,
        competition_margin: float,
    ) -> bool:
        if proposal.event_score < max(self.event_score_threshold - 0.02, 0.18):
            return False
        if proposal.event_margin < max(self.event_margin_threshold - 0.01, 0.02):
            return False
        if rejector_prediction.label in HARD_REJECT_LABELS and not rejector_prediction.is_uncertain:
            return False
        if rejector_prediction.label != "real_event":
            return False
        if ranker_prediction.label != "primary":
            return False
        if self.proposal_acceptor is not None and acceptor_prediction.label != "accept":
            return False
        if rejector_prediction.is_uncertain or ranker_prediction.is_uncertain or acceptor_prediction.is_uncertain:
            return False
        if acceptance_score < self.proposal_acceptance_threshold:
            return False
        if competition_margin < self.proposal_competition_margin_threshold:
            return False
        return True


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
        "proposal_rank_score": proposal.spotter_ranking_score,
        "proposal_start_ratio": round(max(proposal.start_seconds - clip_start, 0.0) / clip_duration, 4),
        "proposal_center_ratio": round(max(proposal.center_seconds - clip_start, 0.0) / clip_duration, 4),
        "proposal_end_ratio": round(max(proposal.end_seconds - clip_start, 0.0) / clip_duration, 4),
        "proposal_duration_ratio": round(max(proposal.end_seconds - proposal.start_seconds, 0.0) / clip_duration, 4),
        "proposal_frame_count": float(len(segment)),
        "proposal_eventness_center": round(float(proposal.eventness[proposal.center_index]), 4),
        "proposal_eventness_mean": round(float(np.mean(proposal.eventness[proposal.start_index : proposal.end_index + 1])), 4),
        "proposal_eventness_max": round(float(np.max(proposal.eventness[proposal.start_index : proposal.end_index + 1])), 4),
        "proposal_eventness_min": round(float(np.min(proposal.eventness[proposal.start_index : proposal.end_index + 1])), 4),
        "proposal_segment_attention_peak": round(float(np.max(proposal.segment_attention)), 4),
        "proposal_segment_attention_entropy": round(_entropy(proposal.segment_attention), 4),
        "proposal_eventness_prev": round(
            float(proposal.eventness[max(proposal.center_index - 1, 0)]),
            4,
        ),
        "proposal_eventness_next": round(
            float(proposal.eventness[min(proposal.center_index + 1, len(proposal.eventness) - 1)]),
            4,
        ),
        "proposal_start_peak_local": round(
            float(np.max(proposal.start_scores[max(proposal.start_index - 1, 0) : min(proposal.start_index + 2, len(proposal.start_scores))])),
            4,
        ),
        "proposal_end_peak_local": round(
            float(np.max(proposal.end_scores[max(proposal.end_index - 1, 0) : min(proposal.end_index + 2, len(proposal.end_scores))])),
            4,
        ),
        "proposal_clip_mid_distance": round(
            abs(((proposal.start_seconds + proposal.end_seconds) / 2.0) - ((clip_start + clip_end) / 2.0)) / clip_duration,
            4,
        ),
    }
    left_context = proposal.eventness[max(proposal.start_index - 2, 0) : proposal.start_index + 1]
    right_context = proposal.eventness[proposal.end_index : min(proposal.end_index + 3, len(proposal.eventness))]
    feature_map["proposal_left_context_eventness_mean"] = round(float(np.mean(left_context)), 4) if left_context.size else 0.0
    feature_map["proposal_right_context_eventness_mean"] = round(float(np.mean(right_context)), 4) if right_context.size else 0.0
    feature_map["proposal_eventness_context_gap"] = round(
        feature_map["proposal_eventness_mean"] - max(
            feature_map["proposal_left_context_eventness_mean"],
            feature_map["proposal_right_context_eventness_mean"],
        ),
        4,
    )
    for family in EVENT_FAMILIES:
        feature_map[f"proposal_family_{family}"] = float(proposal.event_spotter_prediction.distribution.get(family, 0.0))
    for index, value in enumerate(proposal.pooled_vector.tolist()):
        feature_map[f"proposal_embedding_{index}"] = float(value)
    for name in PROPOSAL_REJECTOR_AGGREGATE_FEATURES:
        values = [float(item.get(name, 0.0)) for item in segment_feature_maps]
        feature_map[f"segment_mean_{name}"] = round(float(np.mean(values)), 4) if values else 0.0
        feature_map[f"segment_max_{name}"] = round(float(np.max(values)), 4) if values else 0.0
    return feature_map


def build_proposal_acceptor_feature_map(
    *,
    proposal: TemporalEventProposal,
    rejector_prediction: TemporalTargetPrediction,
    ranker_prediction: TemporalTargetPrediction,
) -> dict[str, float]:
    rejector_real_event_score = float(
        rejector_prediction.distribution.get(
            "real_event",
            rejector_prediction.confidence if rejector_prediction.label == "real_event" else 1.0 - rejector_prediction.confidence,
        )
    )
    ranker_primary_score = float(
        ranker_prediction.distribution.get(
            "primary",
            ranker_prediction.confidence if ranker_prediction.label == "primary" else 1.0 - ranker_prediction.confidence,
        )
    )
    return {
        "proposal_event_score": round(float(proposal.event_score), 4),
        "proposal_event_margin": round(float(proposal.event_margin), 4),
        "proposal_rank_score": round(float(proposal.spotter_ranking_score), 4),
        "proposal_boundary_score": round(float(proposal.boundary_score), 4),
        "proposal_coarse_family_non_other": 0.0 if proposal.coarse_event_family == "other" else 1.0,
        "proposal_rejector_real_event_score": round(rejector_real_event_score, 4),
        "proposal_rejector_margin": round(float(rejector_prediction.margin), 4),
        "proposal_rejector_uncertain": 1.0 if rejector_prediction.is_uncertain else 0.0,
        "proposal_ranker_primary_score": round(ranker_primary_score, 4),
        "proposal_ranker_margin": round(float(ranker_prediction.margin), 4),
        "proposal_ranker_uncertain": 1.0 if ranker_prediction.is_uncertain else 0.0,
    }


def build_shot_specialist_feature_map(
    *,
    observations: Sequence[TemporalStudentObservation],
    proposal: TemporalEventProposal,
    ranked_proposal: RankedTemporalEventProposal | None = None,
) -> dict[str, float]:
    if not observations:
        return {}
    feature_maps = [build_temporal_student_feature_map(observation) for observation in observations]
    timestamps = [float(observation.timestamp_seconds) for observation in observations]
    release_index = _resolve_shot_anchor_index(
        observations,
        timestamps=timestamps,
        runtime_key="shotReleaseTimeSeconds",
        fallback_index=proposal.center_index,
    )
    rim_index = _resolve_shot_anchor_index(
        observations,
        timestamps=timestamps,
        runtime_key="ballNearRimTimeSeconds",
        fallback_index=proposal.center_index,
    )
    finish_index = _resolve_shot_anchor_index(
        observations,
        timestamps=timestamps,
        runtime_key="ballThroughHoopTimeSeconds",
        fallback_index=max(rim_index, proposal.end_index),
    )
    release_window = _window_indices(release_index, radius=1, length=len(observations))
    rim_window = _window_indices(rim_index, radius=1, length=len(observations))
    finish_window = _window_indices(finish_index, radius=1, length=len(observations))
    segment_window = range(proposal.start_index, proposal.end_index + 1)

    feature_map: dict[str, float] = {
        "shot_release_index_ratio": round(release_index / max(len(observations) - 1, 1), 4),
        "shot_rim_index_ratio": round(rim_index / max(len(observations) - 1, 1), 4),
        "shot_finish_index_ratio": round(finish_index / max(len(observations) - 1, 1), 4),
        "shot_release_to_rim_travel_time": round(max(timestamps[rim_index] - timestamps[release_index], 0.0), 4),
        "shot_release_to_finish_travel_time": round(max(timestamps[finish_index] - timestamps[release_index], 0.0), 4),
        "shot_rim_to_finish_time": round(max(timestamps[finish_index] - timestamps[rim_index], 0.0), 4),
        "shot_proposal_duration_seconds": round(max(proposal.end_seconds - proposal.start_seconds, 0.0), 4),
        "shot_proposal_event_score": round(float(proposal.event_score), 4),
        "shot_proposal_event_margin": round(float(proposal.event_margin), 4),
        "shot_proposal_rank_score": round(float(proposal.spotter_ranking_score), 4),
        "shot_proposal_boundary_score": round(float(proposal.boundary_score), 4),
    }
    if ranked_proposal is not None:
        rejector_real_event_score = float(
            ranked_proposal.rejector_prediction.distribution.get(
                "real_event",
                ranked_proposal.rejector_prediction.confidence
                if ranked_proposal.rejector_prediction.label == "real_event"
                else 1.0 - ranked_proposal.rejector_prediction.confidence,
            )
        )
        ranker_primary_score = float(
            ranked_proposal.ranker_prediction.distribution.get(
                "primary",
                ranked_proposal.ranker_prediction.confidence
                if ranked_proposal.ranker_prediction.label == "primary"
                else 1.0 - ranked_proposal.ranker_prediction.confidence,
            )
        )
        acceptor_accept_score = float(
            ranked_proposal.acceptor_prediction.distribution.get(
                "accept",
                ranked_proposal.acceptor_prediction.confidence
                if ranked_proposal.acceptor_prediction.label == "accept"
                else 1.0 - ranked_proposal.acceptor_prediction.confidence,
            )
        )
        feature_map.update(
            {
                "shot_proposal_acceptance_score": round(float(ranked_proposal.acceptance_score), 4),
                "shot_proposal_competition_margin": round(float(ranked_proposal.competition_margin), 4),
                "shot_proposal_accepted": 1.0 if ranked_proposal.accepted else 0.0,
                "shot_proposal_rejector_real_event_score": round(rejector_real_event_score, 4),
                "shot_proposal_ranker_primary_score": round(ranker_primary_score, 4),
                "shot_proposal_acceptor_accept_score": round(acceptor_accept_score, 4),
                "shot_proposal_shot_attempt_score": round(
                    float(proposal.event_spotter_prediction.distribution.get("shot_attempt", 0.0)),
                    4,
                ),
            }
        )
    for index, value in enumerate(proposal.pooled_vector.tolist()):
        feature_map[f"shot_proposal_embedding_{index}"] = round(float(value), 6)

    _append_window_signal_stats(feature_map, feature_maps, release_window, prefix="release")
    _append_window_signal_stats(feature_map, feature_maps, rim_window, prefix="rim")
    _append_window_signal_stats(feature_map, feature_maps, finish_window, prefix="finish")
    _append_window_signal_stats(feature_map, feature_maps, segment_window, prefix="segment")

    release_player_to_rim = feature_map.get("release_player_to_rim_distance_mean", 0.0)
    rim_player_to_rim = feature_map.get("rim_player_to_rim_distance_mean", 0.0)
    finish_player_to_rim = feature_map.get("finish_player_to_rim_distance_mean", 0.0)
    rim_near = feature_map.get("rim_ball_near_rim_max", 0.0)
    finish_through = feature_map.get("finish_ball_through_hoop_likelihood_max", 0.0)
    release_above = feature_map.get("release_ball_above_rim_mean", 0.0)
    rim_above = feature_map.get("rim_ball_above_rim_max", 0.0)
    finish_above = feature_map.get("finish_ball_above_rim_max", 0.0)
    release_arc = feature_map.get("release_ball_arc_apex_max", 0.0)
    rim_arc = feature_map.get("rim_ball_arc_apex_max", 0.0)
    finish_arc = feature_map.get("finish_ball_arc_apex_max", 0.0)
    release_ball_to_rim = feature_map.get("release_ball_to_rim_distance_mean", 0.0)
    rim_ball_to_rim = feature_map.get("rim_ball_to_rim_distance_min", 0.0)
    finish_ball_to_rim = feature_map.get("finish_ball_to_rim_distance_min", 0.0)
    rim_vertical_velocity = feature_map.get("rim_ball_vertical_velocity_y_mean", 0.0)
    finish_vertical_velocity = feature_map.get("finish_ball_vertical_velocity_y_mean", 0.0)
    near_rim_vertical_speed = max(
        feature_map.get("rim_ball_vertical_speed_near_rim_max", 0.0),
        feature_map.get("finish_ball_vertical_speed_near_rim_max", 0.0),
    )
    release_shot = feature_map.get("release_shot_release_candidate_max", 0.0)
    rim_defender = feature_map.get("rim_defender_proximity_at_shot_max", 0.0)
    finish_defender = feature_map.get("finish_defender_proximity_at_shot_max", 0.0)
    segment_ball_to_rim_min = feature_map.get("segment_ball_to_rim_distance_min", 0.0)
    segment_ball_to_rim_range = (
        feature_map.get("segment_ball_to_rim_distance_max", 0.0) - feature_map.get("segment_ball_to_rim_distance_min", 0.0)
    )
    feature_map["shot_ball_to_rim_curve_range"] = round(segment_ball_to_rim_range, 4)
    feature_map["shot_release_to_rim_distance_drop"] = round(max(release_ball_to_rim - rim_ball_to_rim, 0.0), 4)
    feature_map["shot_finish_distance_rebound"] = round(max(finish_ball_to_rim - rim_ball_to_rim, 0.0), 4)
    feature_map["shot_ball_vertical_proxy"] = round(max(rim_above - release_above, finish_above - release_above), 4)
    feature_map["shot_rim_vertical_velocity"] = round(rim_vertical_velocity, 4)
    feature_map["shot_finish_vertical_velocity"] = round(finish_vertical_velocity, 4)
    feature_map["shot_near_rim_vertical_speed"] = round(near_rim_vertical_speed, 4)
    feature_map["shot_arc_proxy"] = round(max(release_arc, rim_arc, finish_arc), 4)
    feature_map["shot_finish_evidence"] = round(
        max(
            finish_through,
            (0.34 * rim_near)
            + (0.22 * rim_above)
            + (0.16 * release_shot)
            + (0.14 * feature_map.get("rim_ball_to_rim_likelihood_max", 0.0))
            + (0.14 * feature_map["shot_release_to_rim_distance_drop"]),
        ),
        4,
    )
    feature_map["shot_made_evidence"] = round(
        max(
            finish_through,
            (0.28 * rim_near)
            + (0.22 * rim_above)
            + (0.18 * release_shot)
            + (0.12 * max(1.0 - segment_ball_to_rim_min, 0.0))
            + (0.12 * feature_map["shot_release_to_rim_distance_drop"])
            + (0.08 * feature_map["shot_near_rim_vertical_speed"]),
        ),
        4,
    )
    feature_map["shot_miss_evidence"] = round(
        max(
            (0.3 * release_shot) + (0.22 * rim_arc) + (0.18 * max(1.0 - finish_through, 0.0)),
            (0.22 * max(1.0 - finish_through, 0.0))
            + (0.18 * feature_map.get("rim_ball_to_rim_likelihood_max", 0.0))
            + (0.18 * feature_map["shot_finish_distance_rebound"]),
        ),
        4,
    )
    feature_map["shot_block_evidence"] = round(
        max(
            finish_defender * 0.72 * max(release_shot, 0.35),
            rim_defender * 0.58 * max(rim_near, 0.3),
        ),
        4,
    )
    feature_map["shot_dunk_evidence"] = round(
        max(feature_map["shot_made_evidence"], 0.0)
        * max(rim_above, feature_map["shot_arc_proxy"], 0.0)
        * max(1.0 - rim_player_to_rim / 0.22, 0.0)
        * max(min(feature_map["shot_near_rim_vertical_speed"] / 0.55, 1.0), 0.25),
        4,
    )
    feature_map["shot_layup_evidence"] = round(
        max(1.0 - release_player_to_rim / 0.28, 0.0)
        * max(release_shot, 0.35)
        * max(1.0 - rim_above * 0.6, 0.0)
        * max(1.0 - feature_map["shot_near_rim_vertical_speed"] * 0.7, 0.0),
        4,
    )
    feature_map["shot_three_evidence"] = round(
        min(max((release_player_to_rim - 0.28) / 0.22, 0.0), 1.0) * max(release_shot, 0.35),
        4,
    )
    feature_map["shot_jumper_evidence"] = round(
        max(0.0, 1.0 - abs(release_player_to_rim - 0.35) / 0.28) * max(release_shot, 0.32),
        4,
    )
    feature_map["shot_putback_evidence"] = round(
        max(feature_map.get("segment_same_play_continuity_score_max", 0.0), 0.0) * max(1.0 - finish_player_to_rim / 0.24, 0.0),
        4,
    )
    feature_map["shot_attempt_likelihood"] = round(
        max(
            feature_map["shot_finish_evidence"],
            feature_map["shot_miss_evidence"],
            feature_map["shot_block_evidence"],
            0.18 * feature_map.get("segment_ball_to_rim_likelihood_max", 0.0),
        ),
        4,
    )
    return feature_map


def _append_window_signal_stats(
    destination: dict[str, float],
    feature_maps: Sequence[dict[str, float]],
    indices: Sequence[int] | range,
    *,
    prefix: str,
) -> None:
    window = [feature_maps[index] for index in indices]
    for feature_name in SHOT_SPECIALIST_SIGNAL_FEATURES:
        values = [float(item.get(feature_name, 0.0)) for item in window]
        destination[f"{prefix}_{feature_name}_mean"] = round(float(np.mean(values)), 4) if values else 0.0
        destination[f"{prefix}_{feature_name}_max"] = round(float(np.max(values)), 4) if values else 0.0
        destination[f"{prefix}_{feature_name}_min"] = round(float(np.min(values)), 4) if values else 0.0


def _resolve_shot_anchor_index(
    observations: Sequence[TemporalStudentObservation],
    *,
    timestamps: Sequence[float],
    runtime_key: str,
    fallback_index: int,
) -> int:
    raw_value = _coerce_optional_time((observations[0].runtime_features or {}).get(runtime_key)) if observations else None
    if raw_value is None:
        return int(min(max(fallback_index, 0), max(len(timestamps) - 1, 0)))
    return _closest_timestamp_index(timestamps, raw_value)


def _window_indices(center_index: int, *, radius: int, length: int) -> range:
    start_index = max(center_index - radius, 0)
    end_index = min(center_index + radius, max(length - 1, 0))
    return range(start_index, end_index + 1)


def _closest_timestamp_index(timestamps: Sequence[float], target_seconds: float) -> int:
    return min(range(len(timestamps)), key=lambda index: abs(float(timestamps[index]) - float(target_seconds)))


def _coerce_optional_time(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    proposal_ranker_payload = payload.get("proposalRanker") or {}
    proposal_ranker_target_payload = proposal_ranker_payload.get("target") or {}
    proposal_ranker = None
    if proposal_ranker_target_payload:
        proposal_ranker = TemporalTargetModel(
            name="proposalRanker",
            classes=tuple(str(item) for item in proposal_ranker_target_payload.get("classes", [])),
            weight=tuple(tuple(float(value) for value in row) for row in proposal_ranker_target_payload.get("weight", [])),
            bias=tuple(float(value) for value in proposal_ranker_target_payload.get("bias", [])),
            temperature=float(proposal_ranker_target_payload.get("temperature", 1.0)),
            uncertainty_threshold=float(proposal_ranker_target_payload.get("uncertaintyThreshold", 0.5)),
            margin_threshold=float(proposal_ranker_target_payload.get("marginThreshold", 0.08)),
            top_k=int(proposal_ranker_target_payload.get("topK", MAX_TEMPORAL_EVENT_DETECTOR_TOPK)),
        )
    proposal_acceptor_payload = payload.get("proposalAcceptor") or {}
    proposal_acceptor_target_payload = proposal_acceptor_payload.get("target") or {}
    proposal_acceptor = None
    if proposal_acceptor_target_payload:
        proposal_acceptor = TemporalTargetModel(
            name="proposalAcceptor",
            classes=tuple(str(item) for item in proposal_acceptor_target_payload.get("classes", [])),
            weight=tuple(tuple(float(value) for value in row) for row in proposal_acceptor_target_payload.get("weight", [])),
            bias=tuple(float(value) for value in proposal_acceptor_target_payload.get("bias", [])),
            temperature=float(proposal_acceptor_target_payload.get("temperature", 1.0)),
            uncertainty_threshold=float(proposal_acceptor_target_payload.get("uncertaintyThreshold", 0.5)),
            margin_threshold=float(proposal_acceptor_target_payload.get("marginThreshold", 0.08)),
            top_k=int(proposal_acceptor_target_payload.get("topK", MAX_TEMPORAL_EVENT_DETECTOR_TOPK)),
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
        proposal_ranker_feature_names=tuple(str(item) for item in proposal_ranker_payload.get("featureNames", [])),
        proposal_ranker=proposal_ranker,
        proposal_acceptor_feature_names=tuple(str(item) for item in proposal_acceptor_payload.get("featureNames", [])),
        proposal_acceptor=proposal_acceptor,
        shot_specialist_feature_names=tuple(str(item) for item in payload.get("shotSpecialistFeatureNames", [])),
        shot_specialist_outcome=targets.get("shotOutcomeSpecialist"),
        shot_specialist_subtype=targets.get("shotSubtypeSpecialist"),
        proposal_acceptance_threshold=float(payload.get("proposalAcceptanceThreshold", 0.62)),
        proposal_competition_margin_threshold=float(payload.get("proposalCompetitionMarginThreshold", 0.06)),
        proposal_candidate_limit=int(payload.get("proposalCandidateLimit", 4)),
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
        "proposalAcceptanceThreshold": bundle.proposal_acceptance_threshold,
        "proposalCompetitionMarginThreshold": bundle.proposal_competition_margin_threshold,
        "proposalCandidateLimit": bundle.proposal_candidate_limit,
        "shotSpecialistFeatureNames": list(bundle.shot_specialist_feature_names),
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
        "proposalRanker": (
            {
                "featureNames": list(bundle.proposal_ranker_feature_names),
                "target": {
                    "classes": list(bundle.proposal_ranker.classes),
                    "weight": [list(row) for row in bundle.proposal_ranker.weight],
                    "bias": list(bundle.proposal_ranker.bias),
                    "temperature": bundle.proposal_ranker.temperature,
                    "uncertaintyThreshold": bundle.proposal_ranker.uncertainty_threshold,
                    "marginThreshold": bundle.proposal_ranker.margin_threshold,
                    "topK": bundle.proposal_ranker.top_k,
                },
            }
            if bundle.proposal_ranker is not None
            else None
        ),
        "proposalAcceptor": (
            {
                "featureNames": list(bundle.proposal_acceptor_feature_names),
                "target": {
                    "classes": list(bundle.proposal_acceptor.classes),
                    "weight": [list(row) for row in bundle.proposal_acceptor.weight],
                    "bias": list(bundle.proposal_acceptor.bias),
                    "temperature": bundle.proposal_acceptor.temperature,
                    "uncertaintyThreshold": bundle.proposal_acceptor.uncertainty_threshold,
                    "marginThreshold": bundle.proposal_acceptor.margin_threshold,
                    "topK": bundle.proposal_acceptor.top_k,
                },
            }
            if bundle.proposal_acceptor is not None
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


def _resolve_shot_specialist_subtype(
    outcome: str,
    prediction: TemporalTargetPrediction,
) -> str | None:
    if outcome == "uncertain" or prediction.is_uncertain:
        return None
    if prediction.label in {"null", "uncertain", "unknown"}:
        return None
    return prediction.label


def _should_attempt_shot_subtype(
    *,
    outcome: str,
    outcome_prediction: TemporalTargetPrediction,
    acceptance_score: float,
) -> bool:
    if outcome == "uncertain" or outcome_prediction.is_uncertain:
        return False
    if outcome_prediction.confidence < 0.66:
        return False
    if outcome_prediction.margin < 0.1:
        return False
    if float(acceptance_score) < 0.72:
        return False
    return True


def _should_promote_generic_shot_attempt(
    *,
    proposal_accepted: bool,
    classifier_gate_open: bool,
    event_family: str,
    outcome: str,
    family_prediction: TemporalTargetPrediction,
    outcome_prediction: TemporalTargetPrediction,
    shot_specialist_used: bool,
    acceptance_score: float,
) -> bool:
    if not proposal_accepted or not classifier_gate_open or not shot_specialist_used:
        return False
    if event_family != "shot_attempt" or outcome != "uncertain":
        return False
    if family_prediction.is_uncertain or family_prediction.confidence < 0.62:
        return False
    if outcome_prediction.confidence < 0.48:
        return False
    if float(acceptance_score) < 0.7:
        return False
    return True


def _calibrated_acceptance_probability(
    *,
    acceptor_prediction: TemporalTargetPrediction,
    fallback_score: float,
) -> float:
    if acceptor_prediction.confidence > 0.0:
        return round(min(max(float(acceptor_prediction.confidence), 0.0), 1.0), 4)
    return round(min(max(float(fallback_score), 0.0), 1.0), 4)


def _prediction_energy(prediction: TemporalTargetPrediction) -> float | None:
    raw_logits = prediction.raw_logits
    if not raw_logits:
        return None
    logits = np.asarray(raw_logits, dtype=np.float64)
    max_logit = float(np.max(logits))
    logsumexp = max_logit + float(np.log(np.sum(np.exp(logits - max_logit))))
    return round(-logsumexp, 4)


def _family_gate_rejection_reason(
    *,
    proposal_accepted: bool,
    rejector_prediction: TemporalTargetPrediction,
    ranker_prediction: TemporalTargetPrediction,
    acceptance_probability: float,
    competition_margin: float,
    acceptance_threshold: float,
    competition_margin_threshold: float,
) -> str | None:
    if not proposal_accepted:
        return "proposal_rejected"
    if rejector_prediction.label in HARD_REJECT_LABELS and not rejector_prediction.is_uncertain:
        return f"hard_rejector:{rejector_prediction.label}"
    if rejector_prediction.label != "real_event":
        return f"rejector:{rejector_prediction.label}"
    if ranker_prediction.label != "primary":
        return f"ranker:{ranker_prediction.label}"
    if acceptance_probability < acceptance_threshold:
        return "acceptance_probability_below_threshold"
    if competition_margin < competition_margin_threshold:
        return "competition_margin_below_threshold"
    return None


def _best_non_other_label(prediction: TemporalStudentTargetPrediction) -> str | None:
    for item in prediction.top_labels:
        label = str(item.label)
        if label != "other":
            return label
    return None


def _fallback_target_prediction(
    *,
    label: str,
    confidence: float,
    margin: float,
    model_version: str,
    classes: Sequence[str],
    default_label: str,
) -> TemporalTargetPrediction:
    safe_label = label if label in classes else default_label
    confidence = round(min(max(float(confidence), 0.0), 1.0), 4)
    margin = round(min(max(float(margin), 0.0), 1.0), 4)
    distribution = {item: 0.0 for item in classes}
    distribution[safe_label] = confidence
    top_labels = (LabelScore(label=safe_label, confidence=confidence, modelVersion=model_version),)
    return TemporalTargetPrediction(
        label=safe_label,
        confidence=confidence,
        margin=margin,
        distribution=distribution,
        top_labels=top_labels,
        is_uncertain=safe_label != default_label and confidence < 0.6,
    )


def _fallback_rejector_prediction(
    *,
    label: str,
    confidence: float,
    margin: float,
    model_version: str,
) -> TemporalTargetPrediction:
    return _fallback_target_prediction(
        label=label,
        confidence=confidence,
        margin=margin,
        model_version=model_version,
        classes=PROPOSAL_REJECT_LABELS,
        default_label="ambiguous",
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

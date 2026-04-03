from __future__ import annotations

from dataclasses import replace
import tempfile
import unittest
from importlib import util
from pathlib import Path
from types import ModuleType
import sys

from services.inference.app.runtime_models.temporal_event_detector import (
    _resolve_shot_specialist_subtype,
    load_temporal_event_detector_bundle,
)
from services.inference.app.temporal_encoder import TemporalTargetPrediction
from services.inference.app.runtime_models.temporal_student import TemporalStudentObservation

try:
    import torch  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    torch = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_training_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "training" / "temporal_event_detector.py"
    spec = util.spec_from_file_location("temporal_event_detector_training_test_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load training module from {module_path}")
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


training = _load_training_module()
TemporalTrainingExample = training.TemporalTrainingExample
evaluate_temporal_event_detector_bundle = training.evaluate_temporal_event_detector_bundle
train_temporal_event_detector = training.train_temporal_event_detector
refresh_shot_specialist_bundle = training.refresh_shot_specialist_bundle
infer_proposal_reject_label = training.infer_proposal_reject_label
write_temporal_event_detector_bundle = training.write_temporal_event_detector_bundle


def _make_observation(
    *,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
    position: float,
    ball_visible: bool = True,
    hoop_visible: bool = True,
) -> TemporalStudentObservation:
    structured_signals = {
        "ballNearRim": 0.82 if event_family == "shot_attempt" else 0.08,
        "ballToRimDistance": 0.08 if shot_subtype == "dunk" else 0.14 if shot_subtype == "layup" else 0.36,
        "ballToRimLikelihood": 0.9 if event_family == "shot_attempt" else 0.1,
        "ballAboveRim": 0.84 if shot_subtype == "dunk" else 0.22,
        "ballArcApex": 0.77 if shot_subtype in {"jumper", "three"} else 0.18,
        "ballVerticalVelocityY": -0.42 if event_family == "shot_attempt" else 0.05,
        "ballVerticalSpeedNearRim": 0.8 if shot_subtype == "dunk" else 0.42 if event_family == "shot_attempt" else 0.08,
        "ballThroughHoopLikelihood": 0.9 if outcome == "made" else 0.08,
        "possessionChangeLikelihood": 0.86 if event_family == "turnover" else 0.06,
        "transitionLikelihood": 0.88 if event_family == "transition" else 0.1,
        "playerToRimDistance": 0.18 if shot_subtype == "dunk" else 0.28 if shot_subtype == "layup" else 0.58,
        "ballCarrierSpeed": 0.74 if event_family == "transition" else 0.12,
        "transitionSpeedScore": 0.9 if event_family == "transition" else 0.14,
        "defenderProximityAtShot": 0.84 if event_family == "defensive_event" else 0.18,
        "shotReleaseCandidate": 0.91 if event_family == "shot_attempt" else 0.07,
        "samePlayContinuityScore": 0.8 if event_family != "other" else 0.18,
    }
    perception_features = {
        "ballVisible": ball_visible,
        "hoopVisible": hoop_visible,
        "basketballConfidence": 0.95 if ball_visible else 0.05,
        "rimConfidence": 0.93 if hoop_visible else 0.06,
        "playerCount": 5.0 if event_family == "shot_attempt" else 6.0 if event_family == "transition" else 4.0,
        "trackedPlayerCount": 4.0 if event_family == "shot_attempt" else 5.0 if event_family == "transition" else 3.0,
        "trackedBallConfidence": 0.88 if ball_visible else 0.05,
        "detectionDensity": 0.72 if ball_visible or hoop_visible else 0.1,
        "trackingDensity": 0.74 if event_family != "other" else 0.12,
    }
    detection_features = {
        "ballVisible": ball_visible,
        "hoopVisible": hoop_visible,
        "ballDetectionConfidence": 0.9 if ball_visible else 0.04,
        "hoopDetectionConfidence": 0.92 if hoop_visible else 0.04,
        "ballTrackCount": 1.0 if ball_visible else 0.0,
        "rimTrackCount": 1.0 if hoop_visible else 0.0,
        "detectionDensity": 0.68 if ball_visible or hoop_visible else 0.08,
    }
    tracking_features = {
        "playerTrackCount": 5.0 if event_family == "shot_attempt" else 6.0 if event_family == "transition" else 3.0,
        "trackedPlayerCount": 4.0 if event_family == "shot_attempt" else 5.0 if event_family == "transition" else 3.0,
        "trackedBallConfidence": 0.89 if ball_visible else 0.05,
        "trackingContinuity": 0.82 if event_family != "other" else 0.12,
        "trackingDensity": 0.76 if event_family != "other" else 0.14,
        "ballTrackCount": 1.0 if ball_visible else 0.0,
        "rimTrackCount": 1.0 if hoop_visible else 0.0,
    }
    runtime_features = {
        "label": "Layup" if shot_subtype == "layup" else "Fast Break" if event_family == "transition" else "Highlight",
        "displayLabel": "Layup" if shot_subtype == "layup" else "Fast Break" if event_family == "transition" else "Highlight",
        "canonicalLabel": "layup" if shot_subtype == "layup" else "fast_break" if event_family == "transition" else "highlight",
        "eventFamily": event_family,
        "outcome": outcome,
        "shotSubtype": shot_subtype or "null",
        "confidence": 0.86 if event_family != "other" else 0.31,
        "sourceKind": "gold",
        "sourceDomain": "live_shadow",
        "sourceSet": "phase4_event_localization_queue",
        "ballVisible": ball_visible,
        "hoopVisible": hoop_visible,
        "sourceRefPresent": True,
        "humanVerified": True,
        "clipDurationSeconds": 4.8,
        "eventStartSeconds": 0.8 if event_family != "other" else 0.0,
        "eventCenterSeconds": 2.4,
        "eventEndSeconds": 3.6 if event_family != "other" else 0.0,
        "shotReleaseTimeSeconds": 1.8 if event_family == "shot_attempt" else None,
        "ballNearRimTimeSeconds": 2.6 if event_family == "shot_attempt" else None,
        "ballThroughHoopTimeSeconds": 2.9 if outcome == "made" else None,
        "possessionChangeTimeSeconds": 2.2 if event_family == "turnover" else None,
        "transitionStartTimeSeconds": 0.6 if event_family == "transition" else None,
        "preRollSeconds": 0.0,
        "postRollSeconds": 0.0,
        "sourceEventCount": 1.0,
        "wasMerged": False,
        "videoMAE": {"topLabel": "layup" if shot_subtype == "layup" else "fast_break" if event_family == "transition" else "highlight"},
        "xclip": {"topLabel": "layup" if shot_subtype == "layup" else "fast_break" if event_family == "transition" else "highlight"},
    }
    return TemporalStudentObservation(
        timestamp_seconds=round(position * 4.8, 4),
        structured_signals=structured_signals,
        perception_features=perception_features,
        detection_features=detection_features,
        tracking_features=tracking_features,
        runtime_features=runtime_features,
    )


class TemporalEventDetectorTests(unittest.TestCase):
    def test_infers_rejector_label_from_reviewer_notes(self) -> None:
        example = TemporalTrainingExample(
            clip_id="clip-ambiguous-negative",
            source_kind="disagreement",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="train",
            event_family="other",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(
                    event_family="other",
                    outcome="uncertain",
                    shot_subtype=None,
                    position=position,
                    ball_visible=False,
                    hoop_visible=False,
                )
                for position in (0.15, 0.4, 0.66, 0.92)
            ),
            weight=2.0,
            has_event_localization=False,
            reviewer_notes="Manual review: dead-ball reset before inbound.",
        )

        self.assertEqual(infer_proposal_reject_label(example), "dead_ball")

    @unittest.skipIf(torch is None, "torch is required for temporal event detector training")
    def test_actionformer_smoke_predicts_shot_attempt(self) -> None:
        shot = TemporalTrainingExample(
            clip_id="clip-shot-layup",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="val",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="layup",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="made", shot_subtype="layup", position=position)
                for position in (0.12, 0.4, 0.7, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        shot_secondary = TemporalTrainingExample(
            clip_id="clip-shot-dunk-secondary",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="train",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="dunk",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="made", shot_subtype="dunk", position=position)
                for position in (0.16, 0.44, 0.71, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        transition = TemporalTrainingExample(
            clip_id="clip-transition",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="transition",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(event_family="transition", outcome="uncertain", shot_subtype=None, position=position)
                for position in (0.1, 0.38, 0.66, 0.92)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        negative = TemporalTrainingExample(
            clip_id="clip-negative-camera-pan",
            source_kind="gold",
            source_domain="manual_negative",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="other",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(
                    event_family="other",
                    outcome="uncertain",
                    shot_subtype=None,
                    position=position,
                    ball_visible=False,
                    hoop_visible=False,
                )
                for position in (0.11, 0.36, 0.63, 0.89)
            ),
            weight=4.0,
            has_event_localization=False,
            reviewer_notes="Camera pan across the crowd; no live event.",
        )

        result = train_temporal_event_detector(
            [shot, shot_secondary, transition, negative],
            architecture="actionformer",
            hidden_size=8,
            epochs=18,
            learning_rate=0.05,
        )
        prediction = result.bundle.predict(shot.observations)
        self.assertEqual(prediction.metadata["temporal_event_detector_family"], "actionformer")
        self.assertEqual(prediction.metadata["temporal_event_detector_family"], "actionformer")

    @unittest.skipIf(torch is None, "torch is required for temporal event detector training")
    def test_tridet_can_gate_non_event(self) -> None:
        shot = TemporalTrainingExample(
            clip_id="clip-shot-jumper",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="val",
            event_family="shot_attempt",
            outcome="missed",
            shot_subtype="jumper",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="missed", shot_subtype="jumper", position=position)
                for position in (0.14, 0.42, 0.68, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        negative = TemporalTrainingExample(
            clip_id="clip-non-event",
            source_kind="gold",
            source_domain="manual_negative",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="other",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(
                    event_family="other",
                    outcome="uncertain",
                    shot_subtype=None,
                    position=position,
                    ball_visible=False,
                    hoop_visible=False,
                )
                for position in (0.15, 0.4, 0.66, 0.92)
            ),
            weight=4.5,
            has_event_localization=False,
        )

        result = train_temporal_event_detector(
            [shot, negative],
            architecture="tridet",
            hidden_size=8,
            epochs=10,
            learning_rate=0.05,
        )
        prediction = result.bundle.predict(negative.observations)
        self.assertEqual(prediction.eventFamily, "other")
        self.assertEqual(prediction.label, "Highlight")
        self.assertFalse(prediction.metadata["temporal_event_detector_gate_open"])
        self.assertFalse(prediction.metadata["temporal_event_detector_proposal_accepted"])
        self.assertIsNotNone(prediction.metadata["temporal_event_detector_proposal_rejector_label"])
        self.assertTrue(result.bundle.proposal_rejector is not None)
        self.assertTrue(result.bundle.proposal_ranker is not None)
        self.assertTrue(result.bundle.proposal_acceptor is not None)

    @unittest.skipIf(torch is None, "torch is required for temporal event detector training")
    def test_accepted_proposal_does_not_force_shot_attempt_when_family_is_weak(self) -> None:
        shot = TemporalTrainingExample(
            clip_id="clip-shot-weak-family",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="val",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="layup",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="made", shot_subtype="layup", position=position)
                for position in (0.14, 0.43, 0.69, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        transition = TemporalTrainingExample(
            clip_id="clip-transition-weak-family",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="transition",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(event_family="transition", outcome="uncertain", shot_subtype=None, position=position)
                for position in (0.1, 0.36, 0.64, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        negative = TemporalTrainingExample(
            clip_id="clip-negative-weak-family",
            source_kind="gold",
            source_domain="manual_negative",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="other",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(
                    event_family="other",
                    outcome="uncertain",
                    shot_subtype=None,
                    position=position,
                    ball_visible=False,
                    hoop_visible=False,
                )
                for position in (0.12, 0.39, 0.65, 0.9)
            ),
            weight=4.0,
            has_event_localization=False,
            reviewer_notes="Half-court setup with no real event.",
        )

        result = train_temporal_event_detector(
            [shot, transition, negative],
            architecture="tridet",
            hidden_size=8,
            epochs=10,
            learning_rate=0.05,
        )
        weakened_family_target = replace(
            result.bundle.targets["eventFamily"],
            uncertainty_threshold=0.999,
            margin_threshold=0.999,
        )
        weakened_bundle = replace(
            result.bundle,
            targets={**result.bundle.targets, "eventFamily": weakened_family_target},
            proposal_rejector=replace(
                result.bundle.proposal_rejector,
                uncertainty_threshold=0.0,
                margin_threshold=0.0,
            ) if result.bundle.proposal_rejector is not None else None,
            proposal_ranker=replace(
                result.bundle.proposal_ranker,
                uncertainty_threshold=0.0,
                margin_threshold=0.0,
            ) if result.bundle.proposal_ranker is not None else None,
            proposal_acceptor_feature_names=(),
            proposal_acceptor=None,
            proposal_acceptance_threshold=0.2,
            proposal_competition_margin_threshold=0.0,
        )

        prediction = weakened_bundle.predict(shot.observations)

        self.assertTrue(prediction.metadata["temporal_event_detector_proposal_accepted"])
        self.assertFalse(prediction.metadata["temporal_event_detector_classifier_gate_open"])
        self.assertEqual(prediction.eventFamily, "other")
        self.assertEqual(prediction.outcome, "uncertain")
        self.assertIsNone(prediction.shotSubtype)

    @unittest.skipIf(torch is None, "torch is required for temporal event detector training")
    def test_evaluation_reports_detector_metrics_and_bundle_roundtrip(self) -> None:
        shot = TemporalTrainingExample(
            clip_id="clip-shot-dunk",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="val",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="dunk",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="made", shot_subtype="dunk", position=position)
                for position in (0.15, 0.45, 0.72, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        miss = TemporalTrainingExample(
            clip_id="clip-shot-miss-jumper",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="train",
            event_family="shot_attempt",
            outcome="missed",
            shot_subtype="jumper",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="missed", shot_subtype="jumper", position=position)
                for position in (0.12, 0.41, 0.67, 0.88)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        turnover = TemporalTrainingExample(
            clip_id="clip-turnover",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="turnover",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(event_family="turnover", outcome="uncertain", shot_subtype=None, position=position)
                for position in (0.12, 0.38, 0.66, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        negative = TemporalTrainingExample(
            clip_id="clip-negative-dead-ball",
            source_kind="gold",
            source_domain="manual_negative",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="other",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(
                    event_family="other",
                    outcome="uncertain",
                    shot_subtype=None,
                    position=position,
                    ball_visible=False,
                    hoop_visible=False,
                )
                for position in (0.14, 0.39, 0.65, 0.88)
            ),
            weight=4.0,
            has_event_localization=False,
            reviewer_notes="Dead-ball reset with no live event.",
        )

        result = train_temporal_event_detector(
            [shot, miss, turnover, negative],
            architecture="actionformer",
            hidden_size=8,
            epochs=8,
            learning_rate=0.05,
        )
        metrics = evaluate_temporal_event_detector_bundle(result.bundle, [shot, turnover, negative])
        self.assertIn("eventDetectionPrecision", metrics)
        self.assertIn("eventDetectionRecall", metrics)
        self.assertIn("predictedOtherTrueMissRate", metrics)
        self.assertIn("proposalAcceptanceRate", metrics)
        self.assertIn("acceptedShotProposalOutcomeAccuracy", metrics)
        self.assertIn("acceptedShotAbstentionRate", metrics)
        self.assertIn("dunkDominance", metrics)
        self.assertIn("eventnessBrier", metrics)

        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = Path(temp_dir) / "temporal-event-detector.json"
            write_temporal_event_detector_bundle(bundle_path, result.bundle)
            loaded = load_temporal_event_detector_bundle(bundle_path)
        prediction = loaded.predict(shot.observations)
        self.assertEqual(prediction.metadata["temporal_event_detector_family"], "actionformer")
        self.assertEqual(loaded.schema_version, "temporal-event-detector-v3")
        self.assertEqual(loaded.model_version, "temporal-event-detector-actionformer-open-set-v1")
        self.assertEqual(loaded.proposal_rejector is not None, result.bundle.proposal_rejector is not None)
        self.assertEqual(loaded.proposal_ranker is not None, result.bundle.proposal_ranker is not None)
        self.assertEqual(loaded.proposal_acceptor is not None, result.bundle.proposal_acceptor is not None)
        self.assertTrue(bool(loaded.shot_specialist_feature_names))
        self.assertEqual(loaded.shot_specialist_outcome is not None, "shotOutcomeSpecialist" in result.bundle.targets)
        self.assertEqual(loaded.shot_specialist_subtype is not None, "shotSubtypeSpecialist" in result.bundle.targets)
        self.assertEqual("shotOutcomeSpecialist" in loaded.targets, "shotOutcomeSpecialist" in result.bundle.targets)
        self.assertEqual("shotSubtypeSpecialist" in loaded.targets, "shotSubtypeSpecialist" in result.bundle.targets)

    @unittest.skipIf(torch is None, "torch is required for temporal event detector training")
    def test_shot_specialist_refresh_preserves_frozen_proposal_stack(self) -> None:
        shot = TemporalTrainingExample(
            clip_id="clip-shot-refresh-dunk",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="val",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="dunk",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="made", shot_subtype="dunk", position=position)
                for position in (0.15, 0.44, 0.71, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        miss = TemporalTrainingExample(
            clip_id="clip-shot-refresh-miss",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="train",
            event_family="shot_attempt",
            outcome="missed",
            shot_subtype="jumper",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="missed", shot_subtype="jumper", position=position)
                for position in (0.14, 0.41, 0.66, 0.88)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        transition = TemporalTrainingExample(
            clip_id="clip-transition-refresh",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="transition",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(event_family="transition", outcome="uncertain", shot_subtype=None, position=position)
                for position in (0.12, 0.39, 0.67, 0.9)
            ),
            weight=4.0,
            has_event_localization=True,
        )
        negative = TemporalTrainingExample(
            clip_id="clip-other-refresh",
            source_kind="gold",
            source_domain="manual_negative",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="other",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(
                    event_family="other",
                    outcome="uncertain",
                    shot_subtype=None,
                    position=position,
                    ball_visible=False,
                    hoop_visible=False,
                )
                for position in (0.13, 0.38, 0.64, 0.89)
            ),
            weight=4.0,
            has_event_localization=False,
            reviewer_notes="Half-court setup with no finish.",
        )

        result = train_temporal_event_detector(
            [shot, miss, transition, negative],
            architecture="tridet",
            hidden_size=8,
            epochs=8,
            learning_rate=0.05,
        )
        refreshed = refresh_shot_specialist_bundle(
            result.bundle,
            [shot, miss, transition, negative],
            epochs=12,
            learning_rate=0.04,
        )

        self.assertEqual(refreshed.detector_family, result.bundle.detector_family)
        self.assertEqual(refreshed.projection_weight, result.bundle.projection_weight)
        self.assertEqual(refreshed.proposal_rejector, result.bundle.proposal_rejector)
        self.assertEqual(refreshed.proposal_ranker, result.bundle.proposal_ranker)
        self.assertEqual(refreshed.proposal_acceptor, result.bundle.proposal_acceptor)
        self.assertTrue(bool(refreshed.shot_specialist_feature_names))
        self.assertIn("phase4f_shot_specialist_refresh", refreshed.source_dataset)
        self.assertIn(
            "Shot-specialist heads refreshed from the frozen phase4e TriDet proposal stack.",
            refreshed.notes,
        )

    @unittest.skipIf(torch is None, "torch is required for temporal event detector training")
    def test_event_detection_metrics_count_coarse_gold_rows(self) -> None:
        shot = TemporalTrainingExample(
            clip_id="clip-shot-coarse",
            source_kind="gold",
            source_domain="live_shadow",
            source_set="phase4_event_localization_queue",
            split="val",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="dunk",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="made", shot_subtype="dunk", position=position)
                for position in (0.18, 0.42, 0.7, 0.9)
            ),
            weight=4.0,
            has_event_localization=False,
        )
        negative = TemporalTrainingExample(
            clip_id="clip-other-coarse",
            source_kind="gold",
            source_domain="manual_negative",
            source_set="phase4_event_localization_queue",
            split="test",
            event_family="other",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(
                    event_family="other",
                    outcome="uncertain",
                    shot_subtype=None,
                    position=position,
                    ball_visible=False,
                    hoop_visible=False,
                )
                for position in (0.16, 0.41, 0.68, 0.91)
            ),
            weight=4.0,
            has_event_localization=False,
        )

        result = train_temporal_event_detector(
            [shot, negative],
            architecture="actionformer",
            hidden_size=8,
            epochs=10,
            learning_rate=0.05,
        )
        metrics = evaluate_temporal_event_detector_bundle(result.bundle, [shot, negative])
        self.assertEqual(metrics["eventDetectionLabeledRows"], 2)

    @unittest.skipIf(torch is None, "torch is required for temporal event detector training")
    def test_shot_specialist_subtype_abstains_for_weak_or_non_made_outcomes(self) -> None:
        uncertain_prediction = TemporalTargetPrediction(
            label="dunk",
            confidence=0.51,
            margin=0.01,
            distribution={"dunk": 0.51, "layup": 0.49},
            top_labels=(),
            is_uncertain=True,
        )
        confident_prediction = TemporalTargetPrediction(
            label="dunk",
            confidence=0.88,
            margin=0.44,
            distribution={"dunk": 0.88, "layup": 0.12},
            top_labels=(),
            is_uncertain=False,
        )

        self.assertIsNone(_resolve_shot_specialist_subtype("made", uncertain_prediction))
        self.assertIsNone(_resolve_shot_specialist_subtype("missed", confident_prediction))
        self.assertEqual(_resolve_shot_specialist_subtype("made", confident_prediction), "dunk")

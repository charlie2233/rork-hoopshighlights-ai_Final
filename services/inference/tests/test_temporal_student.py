from __future__ import annotations

import unittest
from importlib import util
from pathlib import Path
from types import ModuleType
import sys

from services.inference.app.runtime_models.temporal_student import (
    TemporalStudentObservation,
    build_temporal_student_feature_map,
)

try:
    import torch  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    torch = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_training_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "training" / "temporal_student.py"
    spec = util.spec_from_file_location("temporal_student_training_test_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load training module from {module_path}")
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


training = _load_training_module()
TemporalStudentTrainingExample = training.TemporalStudentTrainingExample
evaluate_temporal_student_bundle = training.evaluate_temporal_student_bundle
load_temporal_student_examples = training.load_temporal_student_examples
train_temporal_student = training.train_temporal_student


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
        "ballNearRim": 0.85 if event_family == "shot_attempt" else 0.12,
        "ballAboveRim": 0.82 if shot_subtype == "dunk" else 0.48 if event_family == "shot_attempt" else 0.08,
        "ballArcApex": 0.8 if shot_subtype in {"jumper", "three"} else 0.34,
        "ballThroughHoopLikelihood": 0.92 if outcome == "made" else 0.08 if outcome == "missed" else 0.1,
        "possessionChangeLikelihood": 0.88 if event_family == "turnover" else 0.08,
        "transitionLikelihood": 0.86 if event_family == "transition" else 0.1,
        "playerToRimDistance": 0.18 if shot_subtype == "dunk" else 0.28 if shot_subtype == "layup" else 0.52,
        "ballCarrierSpeed": 0.74 if event_family == "transition" else 0.22,
        "transitionSpeedScore": 0.86 if event_family == "transition" else 0.2,
        "defenderProximityAtShot": 0.82 if event_family == "defensive_event" else 0.28,
        "shotReleaseCandidate": 0.9 if event_family == "shot_attempt" else 0.12,
        "samePlayContinuityScore": 0.78 if event_family == "shot_attempt" else 0.24,
    }
    perception_features = {
        "basketballConfidence": 0.96 if ball_visible else 0.1,
        "rimConfidence": 0.94 if hoop_visible else 0.08,
        "playerCount": 5.0 if event_family == "shot_attempt" else 6.0 if event_family == "transition" else 4.0,
        "trackedPlayerCount": 4.0 if event_family == "shot_attempt" else 5.0,
        "trackedBallConfidence": 0.9 if ball_visible else 0.08,
        "ballVisible": ball_visible,
        "hoopVisible": hoop_visible,
    }
    detection_features = {
        "ballVisible": ball_visible,
        "hoopVisible": hoop_visible,
        "ballDetectionConfidence": 0.94 if ball_visible else 0.05,
        "hoopDetectionConfidence": 0.92 if hoop_visible else 0.05,
        "ballTrackCount": 1.0 if ball_visible else 0.0,
        "rimTrackCount": 1.0 if hoop_visible else 0.0,
        "detectionDensity": 0.7 if ball_visible and hoop_visible else 0.2,
    }
    tracking_features = {
        "playerTrackCount": 5.0 if event_family == "shot_attempt" else 6.0 if event_family == "transition" else 4.0,
        "trackedPlayerCount": 4.0 if event_family == "shot_attempt" else 5.0,
        "trackedBallConfidence": 0.9 if ball_visible else 0.08,
        "trackingContinuity": 0.82 if event_family == "shot_attempt" else 0.25,
        "trackingDensity": 0.74 if event_family == "shot_attempt" else 0.24,
        "ballTrackCount": 1.0 if ball_visible else 0.0,
        "rimTrackCount": 1.0 if hoop_visible else 0.0,
        "ballTrackConfidence": 0.9 if ball_visible else 0.08,
    }
    runtime_features = {
        "label": "dunk" if shot_subtype == "dunk" else "steal" if event_family == "turnover" else "fast break" if event_family == "transition" else "highlight",
        "eventFamily": event_family,
        "outcome": outcome,
        "shotSubtype": shot_subtype or "null",
        "confidence": 0.87 if event_family == "shot_attempt" else 0.73,
        "sourceKind": "gold",
        "sourceDomain": "live_shadow",
        "sourceSet": "gold_set",
        "ballVisible": ball_visible,
        "hoopVisible": hoop_visible,
        "sourceRefPresent": True,
        "humanVerified": event_family == "shot_attempt",
        "clipDurationSeconds": 4.8,
        "sourceEventCount": 1.0,
        "wasMerged": False,
        "position": position,
    }
    return TemporalStudentObservation(
        timestamp_seconds=round(position * 4.8, 4),
        structured_signals=structured_signals,
        perception_features=perception_features,
        detection_features=detection_features,
        tracking_features=tracking_features,
        runtime_features=runtime_features,
    )


class TemporalStudentTests(unittest.TestCase):
    def test_load_temporal_student_examples_include_perception_features(self) -> None:
        examples = load_temporal_student_examples(REPO_ROOT)

        self.assertGreater(len(examples), 0)
        self.assertTrue(any(example.source_kind == "gold" for example in examples))
        feature_map = build_temporal_student_feature_map(examples[0].observations[0])
        self.assertIn("ball_detection_confidence", feature_map)
        self.assertIn("tracking_continuity", feature_map)
        self.assertIn("runtime_label_highlight", feature_map)

    @unittest.skipIf(torch is None, "torch is required for temporal student training")
    def test_train_temporal_student_smoke_honors_hierarchy(self) -> None:
        made = TemporalStudentTrainingExample(
            clip_id="gold-made-dunk",
            source_kind="gold",
            source_domain="live_shadow",
            split="val",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="dunk",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="made", shot_subtype="dunk", position=position)
                for position in (0.15, 0.45, 0.7, 0.9)
            ),
            weight=4.0,
        )
        turnover = TemporalStudentTrainingExample(
            clip_id="gold-turnover",
            source_kind="gold",
            source_domain="live_shadow",
            split="test",
            event_family="turnover",
            outcome="uncertain",
            shot_subtype=None,
            observations=tuple(
                _make_observation(event_family="turnover", outcome="uncertain", shot_subtype=None, position=position, ball_visible=False)
                for position in (0.12, 0.42, 0.7, 0.9)
            ),
            weight=4.0,
        )

        result = train_temporal_student([made, turnover], hidden_size=8, epochs=6, learning_rate=0.05)
        made_prediction = result.bundle.predict(made.observations)
        turnover_prediction = result.bundle.predict(turnover.observations)

        self.assertEqual(made_prediction.eventFamily, "shot_attempt")
        self.assertEqual(made_prediction.outcome, "made")
        self.assertEqual(made_prediction.shotSubtype, "dunk")
        self.assertEqual(turnover_prediction.eventFamily, "turnover")
        self.assertIsNone(turnover_prediction.shotSubtype)
        self.assertIn(turnover_prediction.label, {"Steal", "Highlight", "Fast Break"})

    @unittest.skipIf(torch is None, "torch is required for temporal student training")
    def test_temporal_student_evaluation_reports_dominance_and_confusion(self) -> None:
        made = TemporalStudentTrainingExample(
            clip_id="gold-made-layup",
            source_kind="gold",
            source_domain="live_shadow",
            split="val",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="layup",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="made", shot_subtype="layup", position=position)
                for position in (0.15, 0.45, 0.72, 0.9)
            ),
            weight=4.0,
        )
        miss = TemporalStudentTrainingExample(
            clip_id="gold-miss-jumper",
            source_kind="gold",
            source_domain="live_shadow",
            split="test",
            event_family="shot_attempt",
            outcome="missed",
            shot_subtype="jumper",
            observations=tuple(
                _make_observation(event_family="shot_attempt", outcome="missed", shot_subtype="jumper", position=position)
                for position in (0.12, 0.4, 0.72, 0.9)
            ),
            weight=4.0,
        )

        result = train_temporal_student([made, miss], hidden_size=8, epochs=6, learning_rate=0.05)
        metrics = evaluate_temporal_student_bundle(result.bundle, [made, miss])

        self.assertIn("flatLabelSpread", metrics)
        self.assertIn("highlightDominance", metrics)
        self.assertIn("otherDominance", metrics)
        self.assertIn("missVsMadeConfusion", metrics)
        self.assertGreaterEqual(metrics["flatLabelSpread"], 1)


if __name__ == "__main__":
    unittest.main()


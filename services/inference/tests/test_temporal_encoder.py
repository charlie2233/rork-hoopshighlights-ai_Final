from __future__ import annotations

import unittest
from importlib import util
from pathlib import Path
from types import ModuleType
import sys

from services.inference.app.temporal_encoder import TemporalObservation

try:
    import torch  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    torch = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_training_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "training" / "temporal_encoder.py"
    spec = util.spec_from_file_location("temporal_encoder_training_test_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load training module from {module_path}")
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


training = _load_training_module()
evaluate_temporal_encoder_bundle = training.evaluate_temporal_encoder_bundle
load_temporal_training_examples = training.load_temporal_training_examples
train_temporal_encoder = training.train_temporal_encoder
TemporalTrainingExample = training.TemporalTrainingExample


class TemporalEncoderTrainingTests(unittest.TestCase):
    def test_load_temporal_training_examples_builds_fixed_length_sequences(self) -> None:
        examples = load_temporal_training_examples(REPO_ROOT)

        self.assertGreater(len(examples), 0)
        self.assertTrue(any(example.source_kind == "gold" for example in examples))
        self.assertTrue(all(len(example.observations) == 4 for example in examples))
        first = examples[0]
        self.assertIn("ballNearRim", first.observations[0].structured_signals)
        self.assertIn("basketballConfidence", first.observations[0].perception_features)

    @unittest.skipIf(torch is None, "torch is required for temporal encoder training")
    def test_train_temporal_encoder_smoke(self) -> None:
        made = TemporalTrainingExample(
            clip_id="gold-made-jumper",
            source_kind="gold",
            split="val",
            event_family="shot_attempt",
            outcome="made",
            shot_subtype="jumper",
            observations=(
                TemporalObservation(0.5, {"ballNearRim": 0.25, "shotReleaseCandidate": 0.82}, {"basketballConfidence": 0.9, "rimConfidence": 0.8, "playerCount": 4.0, "trackedPlayerCount": 3.0, "trackedBallConfidence": 0.82}),
                TemporalObservation(1.2, {"ballNearRim": 0.62, "ballArcApex": 0.84, "shotReleaseCandidate": 0.93}, {"basketballConfidence": 0.9, "rimConfidence": 0.8, "playerCount": 4.0, "trackedPlayerCount": 3.0, "trackedBallConfidence": 0.82}),
                TemporalObservation(1.9, {"ballNearRim": 0.71, "ballThroughHoopLikelihood": 0.88, "shotReleaseCandidate": 0.44}, {"basketballConfidence": 0.9, "rimConfidence": 0.8, "playerCount": 4.0, "trackedPlayerCount": 3.0, "trackedBallConfidence": 0.82}),
                TemporalObservation(2.5, {"ballNearRim": 0.28, "samePlayContinuityScore": 0.72}, {"basketballConfidence": 0.9, "rimConfidence": 0.8, "playerCount": 4.0, "trackedPlayerCount": 3.0, "trackedBallConfidence": 0.82}),
            ),
            weight=4.0,
        )
        turnover = TemporalTrainingExample(
            clip_id="gold-steal",
            source_kind="gold",
            split="test",
            event_family="turnover",
            outcome="uncertain",
            shot_subtype=None,
            observations=(
                TemporalObservation(0.4, {"possessionChangeLikelihood": 0.24, "transitionLikelihood": 0.32}, {"basketballConfidence": 0.86, "rimConfidence": 0.2, "playerCount": 6.0, "trackedPlayerCount": 5.0, "trackedBallConfidence": 0.75}),
                TemporalObservation(1.0, {"possessionChangeLikelihood": 0.78, "transitionLikelihood": 0.66}, {"basketballConfidence": 0.86, "rimConfidence": 0.2, "playerCount": 6.0, "trackedPlayerCount": 5.0, "trackedBallConfidence": 0.75}),
                TemporalObservation(1.7, {"possessionChangeLikelihood": 0.92, "transitionLikelihood": 0.74, "transitionSpeedScore": 0.81}, {"basketballConfidence": 0.86, "rimConfidence": 0.2, "playerCount": 6.0, "trackedPlayerCount": 5.0, "trackedBallConfidence": 0.75}),
                TemporalObservation(2.3, {"possessionChangeLikelihood": 0.84, "samePlayContinuityScore": 0.28}, {"basketballConfidence": 0.86, "rimConfidence": 0.2, "playerCount": 6.0, "trackedPlayerCount": 5.0, "trackedBallConfidence": 0.75}),
            ),
            weight=4.0,
        )

        result = train_temporal_encoder(
            [made, turnover],
            hidden_size=6,
            epochs=4,
            learning_rate=0.05,
        )
        metrics = evaluate_temporal_encoder_bundle(result.bundle, [made, turnover])

        self.assertEqual(result.bundle.model_version, "temporal-encoder-lite-v1")
        self.assertIn("eventFamilyAccuracy", metrics)
        self.assertIn("outcomeAccuracy", metrics)


if __name__ == "__main__":
    unittest.main()

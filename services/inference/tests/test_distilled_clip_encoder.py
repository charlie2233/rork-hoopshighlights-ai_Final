from __future__ import annotations

import tempfile
import unittest
from importlib import util
from pathlib import Path
from types import ModuleType
import sys

from services.inference.app.distilled_clip_encoder import DistilledClipEncoderBundle


def _load_training_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "training" / "distilled_clip_encoder.py"
    spec = util.spec_from_file_location("distilled_clip_encoder_training_test_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load training module from {module_path}")
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


training = _load_training_module()
DistilledClipTrainingExample = training.DistilledClipTrainingExample
build_distilled_clip_encoder_bundle = training.build_distilled_clip_encoder_bundle
evaluate_distilled_clip_encoder = training.evaluate_distilled_clip_encoder
fit_distilled_clip_encoder = training.fit_distilled_clip_encoder


class DistilledClipEncoderTests(unittest.TestCase):
    def test_bundle_learns_from_weighted_gold_silver_labels(self) -> None:
        examples = [
            DistilledClipTrainingExample(
                clip_id="gold-dunk",
                source_kind="gold",
                source_domain="gold:human",
                source_set="gold_set",
                split="train",
                weight=4.0,
                ignored=False,
                event_family="shot_attempt",
                outcome="made",
                shot_subtype="dunk",
                label_source="human",
                teacher_confidence=None,
                human_verified=True,
                raw_runtime_outputs={
                    "label": "Highlight",
                    "eventFamily": "shot_attempt",
                    "outcome": "made",
                    "shotSubtype": "dunk",
                    "topKLabels": ["shooting basketball", "playing basketball"],
                },
                raw_teacher_outputs=None,
                features={
                    "sourceKind=gold": 1.0,
                    "ballNearRim": 0.92,
                    "ballThroughHoopLikelihood": 0.81,
                    "hoopVisible": 1.0,
                    "ballVisible": 1.0,
                    "runtimeLabel=highlight": 1.0,
                    "runtimeEventFamily=shot_attempt": 1.0,
                    "runtimeOutcome=made": 1.0,
                    "runtimeShotSubtype=dunk": 1.0,
                },
            ),
            DistilledClipTrainingExample(
                clip_id="silver-layup",
                source_kind="silver",
                source_domain="silver:teacher",
                source_set="silver_set",
                split="train",
                weight=1.5,
                ignored=False,
                event_family="shot_attempt",
                outcome="missed",
                shot_subtype="layup",
                label_source="teacher",
                teacher_confidence=0.92,
                human_verified=False,
                raw_runtime_outputs={
                    "label": "Highlight",
                    "eventFamily": "shot_attempt",
                    "outcome": "uncertain",
                    "shotSubtype": "layup",
                    "topKLabels": ["shooting basketball", "dribbling basketball", "playing basketball"],
                },
                raw_teacher_outputs={
                    "eventFamily": "shot_attempt",
                    "outcome": "missed",
                    "shotSubtype": "layup",
                    "confidence": 0.92,
                },
                features={
                    "sourceKind=silver": 1.0,
                    "ballNearRim": 0.77,
                    "ballThroughHoopLikelihood": 0.11,
                    "hoopVisible": 1.0,
                    "ballVisible": 1.0,
                    "runtimeLabel=highlight": 1.0,
                    "runtimeEventFamily=shot_attempt": 1.0,
                    "runtimeOutcome=uncertain": 1.0,
                    "runtimeShotSubtype=layup": 1.0,
                },
            ),
            DistilledClipTrainingExample(
                clip_id="gold-steal-train",
                source_kind="gold",
                source_domain="gold:human",
                source_set="gold_set",
                split="train",
                weight=4.0,
                ignored=False,
                event_family="turnover",
                outcome="uncertain",
                shot_subtype=None,
                label_source="human",
                teacher_confidence=None,
                human_verified=True,
                raw_runtime_outputs={
                    "label": "steal",
                    "eventFamily": "turnover",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "topKLabels": ["steal", "fast break"],
                },
                raw_teacher_outputs=None,
                features={
                    "sourceKind=gold": 1.0,
                    "ballNearRim": 0.03,
                    "ballThroughHoopLikelihood": 0.01,
                    "transitionLikelihood": 0.18,
                    "runtimeLabel=steal": 1.0,
                    "runtimeEventFamily=turnover": 1.0,
                    "runtimeOutcome=uncertain": 1.0,
                    "runtimeTopK[0]=steal": 1.0,
                },
            ),
            DistilledClipTrainingExample(
                clip_id="gold-steal",
                source_kind="gold",
                source_domain="gold:human",
                source_set="gold_set",
                split="test",
                weight=4.0,
                ignored=False,
                event_family="turnover",
                outcome="uncertain",
                shot_subtype=None,
                label_source="human",
                teacher_confidence=None,
                human_verified=True,
                raw_runtime_outputs={
                    "label": "steal",
                    "eventFamily": "turnover",
                    "outcome": "uncertain",
                    "shotSubtype": None,
                    "topKLabels": ["steal", "block", "fast break"],
                },
                raw_teacher_outputs=None,
                features={
                    "sourceKind=gold": 1.0,
                    "ballNearRim": 0.04,
                    "ballThroughHoopLikelihood": 0.01,
                    "transitionLikelihood": 0.14,
                    "runtimeLabel=steal": 1.0,
                    "runtimeEventFamily=turnover": 1.0,
                    "runtimeOutcome=uncertain": 1.0,
                    "runtimeTopK[0]=steal": 1.0,
                },
            ),
        ]

        bundle, manifest = fit_distilled_clip_encoder(examples)
        evaluation_rows, baseline_metrics, distilled_metrics, comparison = evaluate_distilled_clip_encoder(bundle, examples)

        self.assertEqual(bundle.model_version, "distilled-clip-encoder-v1")
        self.assertGreaterEqual(len(bundle.feature_names), 1)
        self.assertIn("eventFamily", bundle.heads)
        self.assertIn("outcome", bundle.heads)
        self.assertIn("shotSubtype", bundle.heads)
        self.assertGreaterEqual(manifest["summary"]["activeExamples"], 1)
        self.assertGreaterEqual(distilled_metrics["sampleCount"], 1)
        self.assertGreaterEqual(len(evaluation_rows), 1)
        self.assertIn("outcomeDelta", comparison)

        snapshot = {
            "sourceKind": "live",
            "sourceDomain": "staging:smoke",
            "sourceSet": "mixed",
            "humanVerified": False,
            "ballVisible": True,
            "hoopVisible": True,
            "ballNearRim": 0.94,
            "ballThroughHoopLikelihood": 0.83,
            "possessionChangeLikelihood": 0.03,
            "transitionLikelihood": 0.02,
            "clipDurationSeconds": 4.8,
            "eventCenterSeconds": 2.4,
            "preRollSeconds": 2.1,
            "postRollSeconds": 2.7,
            "sourceEventCount": 1,
            "wasMerged": False,
            "rawRuntimeOutputs": {
                "label": "Highlight",
                "eventFamily": "shot_attempt",
                "outcome": "made",
                "shotSubtype": "dunk",
                "topKLabels": ["shooting basketball", "playing basketball", "dribbling basketball"],
            },
        }
        prediction = bundle.predict_from_snapshot(snapshot)
        self.assertEqual(prediction.display_label, "Dunk")
        self.assertEqual(prediction.event_family, "shot_attempt")
        self.assertEqual(prediction.outcome, "made")
        self.assertFalse(prediction.is_uncertain)
        self.assertEqual(prediction.shot_subtype, "dunk")
        self.assertIn("distilledClipEncoderSchemaVersion", prediction.metadata)
        self.assertNotIn("teacher", prediction.metadata["distilledClipEncoderSnapshot"])

    def test_bundle_round_trips_through_json(self) -> None:
        bundle, _ = fit_distilled_clip_encoder(
            [
                DistilledClipTrainingExample(
                    clip_id="gold-made",
                    source_kind="gold",
                    source_domain="gold:human",
                    source_set="gold_set",
                    split="train",
                    weight=4.0,
                    ignored=False,
                    event_family="shot_attempt",
                    outcome="made",
                    shot_subtype="jumper",
                    label_source="human",
                    teacher_confidence=None,
                    human_verified=True,
                    raw_runtime_outputs={"label": "jumper", "eventFamily": "shot_attempt", "outcome": "made", "shotSubtype": "jumper", "topKLabels": ["jumper", "three"]},
                    raw_teacher_outputs=None,
                    features={
                        "sourceKind=gold": 1.0,
                        "ballNearRim": 0.61,
                        "ballThroughHoopLikelihood": 0.66,
                        "runtimeLabel=jumper": 1.0,
                        "runtimeEventFamily=shot_attempt": 1.0,
                        "runtimeOutcome=made": 1.0,
                        "runtimeShotSubtype=jumper": 1.0,
                    },
                )
            ]
        )

        payload = bundle.to_dict()
        restored = DistilledClipEncoderBundle.from_dict(payload)
        self.assertEqual(restored.model_version, bundle.model_version)
        self.assertEqual(restored.feature_names, bundle.feature_names)
        self.assertEqual(restored.heads["eventFamily"].labels, bundle.heads["eventFamily"].labels)

    def test_training_builder_can_write_report(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = build_distilled_clip_encoder_bundle(repo_root, Path(tmp_dir))
            self.assertIn("eventFamilyDelta", result.comparison)
            self.assertTrue((Path(tmp_dir) / "bundle.json").exists())
            self.assertTrue((Path(tmp_dir) / "report.md").exists())


if __name__ == "__main__":
    unittest.main()

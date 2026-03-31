from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets.annotations import ClipAnnotation
from services.inference.training.perception_supervision import (
    PERCEPTION_SUPERVISION_FEATURE_VERSION,
    PERCEPTION_SUPERVISION_SCHEMA_VERSION,
    build_perception_feature_dict,
    build_perception_supervision_bundle,
    build_perception_supervision_record,
    extract_perception_context,
    load_perception_supervision_examples,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


class PerceptionSupervisionTests(unittest.TestCase):
    def test_extracts_nested_perception_summary_and_detection_tracks(self) -> None:
        annotation = ClipAnnotation(
            clipId="clip-123",
            sourceDomain="live_shadow",
            schemaVersion=PERCEPTION_SUPERVISION_SCHEMA_VERSION,
            sourceRef="r2://clips/clip-123.mp4",
            eventFamily="shot_attempt",
            outcome="made",
            shotSubtype="layup",
            ballVisible=True,
            hoopVisible=True,
            ballNearRim=0.92,
            ballThroughHoopLikelihood=0.87,
            possessionChangeLikelihood=0.14,
            transitionLikelihood=0.11,
            teacherConfidence=0.98,
            humanVerified=True,
            reviewerNotes="Nested context should survive export.",
            rawRuntimeOutputs={
                "structuredSignals": {
                    "ballNearRim": 0.88,
                    "ballThroughHoopLikelihood": 0.91,
                    "ballAboveRim": 0.42,
                    "shotReleaseCandidate": 0.76,
                },
                "perceptionSummary": {
                    "frameWidth": 1920,
                    "frameHeight": 1080,
                    "sampledFrameCount": 8,
                    "detectionCounts": {"basketball": 24, "rim": 16, "player": 31},
                    "trackCounts": {"basketball": 1, "rim": 1, "player": 4},
                    "tracks": [
                        {"trackId": "basketball-1", "label": "basketball", "averageConfidence": 0.91, "observationCount": 8},
                        {"trackId": "rim-1", "label": "rim", "averageConfidence": 0.87, "observationCount": 8},
                        {"trackId": "player-1", "label": "player", "averageConfidence": 0.78, "observationCount": 4},
                    ],
                    "overlayPaths": ["/tmp/overlay-1.jpg", "/tmp/overlay-2.jpg"],
                },
            },
            rawTeacherOutputs={
                "evidence": {
                    "structuredSignals": {"transitionSpeedScore": 0.23, "samePlayContinuityScore": 0.81},
                    "perceptionSummary": {"frameWidth": 1920, "frameHeight": 1080, "sampledFrameCount": 8},
                }
            },
        )

        context = extract_perception_context(annotation)
        features = build_perception_feature_dict(annotation)

        self.assertEqual(context["sourceDomainTag"], "live_shadow")
        self.assertEqual(features["perception.frameWidth"], 1920.0)
        self.assertEqual(features["perception.trackCount.player"], 4.0)
        self.assertEqual(features["perception.primaryBallTrack.averageConfidence"], 0.91)
        self.assertEqual(features["perception.overlayPathCount"], 2.0)
        self.assertGreater(features["signal.ballNearRim"], 0.85)
        self.assertGreater(features["signal.samePlayContinuityScore"], 0.8)

    def test_bundle_exports_features_and_preserves_gold_anchor_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            manifest = build_perception_supervision_bundle(REPO_ROOT, output_dir=output_dir)

            self.assertEqual(manifest["schemaVersion"], PERCEPTION_SUPERVISION_SCHEMA_VERSION)
            self.assertEqual(manifest["featureVersion"], PERCEPTION_SUPERVISION_FEATURE_VERSION)
            self.assertGreater(manifest["summary"]["totalRecords"], 0)
            self.assertGreater(manifest["summary"]["activeRecords"], 0)
            self.assertGreater(manifest["summary"]["calibrationAnchorRecords"], 0)

            feature_names = json.loads((output_dir / "feature_names.json").read_text(encoding="utf-8"))
            self.assertIn("perception.trackCount.player", feature_names)
            self.assertIn("perception.primaryBallTrack.averageConfidence", feature_names)
            self.assertIn("signal.ballNearRim", feature_names)

            train_records = [
                json.loads(line)
                for line in (output_dir / "train" / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            val_records = [
                json.loads(line)
                for line in (output_dir / "val" / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            test_records = [
                json.loads(line)
                for line in (output_dir / "test" / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertTrue(any(record["sourceKind"] == "gold" for record in train_records + val_records + test_records))
            self.assertTrue(any(record["calibrationAnchor"] for record in val_records + test_records if record["sourceKind"] == "gold"))
            self.assertTrue(any(record["sourceKind"] == "silver" and not record["ignored"] for record in train_records))
            self.assertTrue(any(record["sourceSet"] == "disagreement_queue" for record in train_records + val_records + test_records))

    def test_load_examples_preserves_detection_first_inputs_in_context(self) -> None:
        examples = load_perception_supervision_examples(REPO_ROOT)
        self.assertGreater(len(examples), 0)
        example = next(
            item
            for item in examples
            if item.ball_visible and item.hoop_visible and item.features.get("perception.trackCount.player", 0.0) >= 0.0
        )
        self.assertIn("perceptionSummary", example.perception_context)
        self.assertIn("structuredSignals", example.perception_context)
        self.assertIn("signal.ballThroughHoopLikelihood", example.features)
        self.assertGreaterEqual(example.weight, 0.0)

    def test_low_confidence_silver_rows_are_ignored(self) -> None:
        silver_examples = [
            example
            for example in load_perception_supervision_examples(REPO_ROOT)
            if example.source_kind == "silver"
        ]
        self.assertTrue(any(example.ignored for example in silver_examples))
        self.assertTrue(any(example.weight >= 1.0 for example in silver_examples if not example.ignored))


if __name__ == "__main__":
    unittest.main()

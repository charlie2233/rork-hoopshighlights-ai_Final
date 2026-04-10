from __future__ import annotations

import unittest

from services.inference.app.calibration import CalibrationBin, LabelCalibration, RuntimeCalibration, get_runtime_calibration
from services.inference.app.labels import CanonicalLabelScore, derive_basketball_taxonomy


class RuntimeCalibrationTests(unittest.TestCase):
    def test_runtime_calibration_artifact_loads(self) -> None:
        calibration = get_runtime_calibration()

        self.assertIsNotNone(calibration)
        assert calibration is not None
        self.assertEqual(calibration.schema_version, "runtime-calibration-v1")
        self.assertIn("eventFamily", calibration.dimensions)
        self.assertIn("outcome", calibration.dimensions)
        self.assertIn("shotSubtype", calibration.dimensions)

    def test_calibrated_confidence_can_push_a_clip_to_uncertain(self) -> None:
        calibration = RuntimeCalibration(
            schema_version="runtime-calibration-test",
            source_dataset="fixture",
            split_strategy="unit-test",
            dimensions={
                "eventFamily": {
                    "shot_attempt": LabelCalibration(
                        label="shot_attempt",
                        bins=(CalibrationBin(min_score=0.0, max_score=1.0, count=1, positives=0, calibrated_score=0.24),),
                        fallback_score=0.24,
                        support=1,
                    )
                },
                "outcome": {
                    "made": LabelCalibration(
                        label="made",
                        bins=(CalibrationBin(min_score=0.0, max_score=1.0, count=4, positives=0, calibrated_score=0.18),),
                        fallback_score=0.18,
                        support=4,
                    ),
                    "missed": LabelCalibration(
                        label="missed",
                        bins=(CalibrationBin(min_score=0.0, max_score=1.0, count=2, positives=1, calibrated_score=0.34),),
                        fallback_score=0.34,
                        support=2,
                    ),
                    "uncertain": LabelCalibration(
                        label="uncertain",
                        bins=(CalibrationBin(min_score=0.0, max_score=1.0, count=3, positives=3, calibrated_score=0.82),),
                        fallback_score=0.82,
                        support=3,
                    ),
                },
                "shotSubtype": {
                    "jumper": LabelCalibration(
                        label="jumper",
                        bins=(CalibrationBin(min_score=0.0, max_score=1.0, count=3, positives=0, calibrated_score=0.14),),
                        fallback_score=0.14,
                        support=3,
                    )
                },
            },
            holdout_metrics={},
        )

        taxonomy = derive_basketball_taxonomy(
            "jumper",
            0.88,
            [
                CanonicalLabelScore(label="jumper", confidence=0.88),
                CanonicalLabelScore(label="miss", confidence=0.46),
            ],
            calibration=calibration,
        )

        self.assertEqual(taxonomy.calibration_version, "runtime-calibration-test")
        self.assertEqual(taxonomy.event_family, "other")
        self.assertEqual(taxonomy.outcome, "uncertain")
        self.assertEqual(taxonomy.display_label, "Highlight")
        self.assertTrue(taxonomy.is_uncertain)
        self.assertLessEqual(taxonomy.event_family_confidence_after_mapping, taxonomy.event_family_confidence_before_mapping)


if __name__ == "__main__":
    unittest.main()

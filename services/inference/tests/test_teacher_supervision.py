from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets import TEACHER_SUPERVISION_DATASET_VERSION, build_teacher_supervision_bundle, teacher_supervision_weight, teacher_supervision_weight_components


class TeacherSupervisionDataTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_build_teacher_supervision_bundle_separates_gold_and_teacher_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            manifest = build_teacher_supervision_bundle(self.repo_root(), output_dir)

            self.assertEqual(manifest["datasetVersion"], TEACHER_SUPERVISION_DATASET_VERSION)
            self.assertGreater(manifest["summary"]["totalRecords"], 0)
            self.assertGreater(manifest["summary"]["trainingEligibleRecords"], 0)
            self.assertGreater(manifest["summary"]["calibrationAnchorRecords"], 0)
            self.assertIn("gold_anchor", manifest["summary"]["byRole"])
            self.assertIn("teacher_distill", manifest["summary"]["byRole"])

            rows = [
                json.loads(line)
                for line in (output_dir / "all_records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            gold_row = next(row for row in rows if row["sourceKind"] == "gold")
            silver_row = next(row for row in rows if row["sourceKind"] == "silver")
            low_conf_row = next(row for row in rows if row["clipId"] == "silver-low-confidence-camera-pan-001")
            high_conf_row = next(row for row in rows if row["clipId"] == "silver-dunk-pseudo-001")

            self.assertEqual(gold_row["selectedLabelSource"], "gold")
            self.assertEqual(gold_row["goldEventFamily"], gold_row["selectedEventFamily"])
            self.assertIsNotNone(gold_row["teacherEventFamily"])
            self.assertEqual(silver_row["selectedLabelSource"], "teacher")
            self.assertIsNone(silver_row["goldEventFamily"])
            self.assertIsNotNone(silver_row["teacherEventFamily"])
            self.assertGreater(silver_row["weight"], 0.0)
            self.assertTrue(low_conf_row["trainingEligible"])
            self.assertEqual(low_conf_row["selectedLabelSource"], "teacher")
            self.assertLess(low_conf_row["weight"], high_conf_row["weight"])

            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertTrue((output_dir / "weights.json").exists())
            self.assertTrue((output_dir / "train" / "records.jsonl").exists())
            self.assertTrue((output_dir / "val" / "records.jsonl").exists())
            self.assertTrue((output_dir / "test" / "records.jsonl").exists())

    def test_teacher_supervision_weighting_prefers_gold_then_high_confidence_silver(self) -> None:
        gold_weight = teacher_supervision_weight({"sourceKind": "gold", "sourceDomain": "live_shadow", "teacherConfidence": 0.98})
        silver_weight = teacher_supervision_weight({"sourceKind": "silver", "sourceDomain": "teacher_pseudo", "teacherConfidence": 0.93})
        low_conf_weight = teacher_supervision_weight({"sourceKind": "silver", "sourceDomain": "teacher_pseudo", "teacherConfidence": 0.42})
        hard_negative_weight = teacher_supervision_weight({"sourceKind": "silver", "sourceDomain": "hard_negative", "teacherConfidence": 0.63})

        self.assertGreater(gold_weight, silver_weight)
        self.assertGreater(silver_weight, 0.0)
        self.assertEqual(low_conf_weight, 0.0)
        self.assertGreater(hard_negative_weight, 0.0)
        self.assertLess(hard_negative_weight, gold_weight)

    def test_teacher_supervision_weight_components_report_selected_source(self) -> None:
        components = teacher_supervision_weight_components(
            {
                "clipId": "silver-hard-negative-replay-001",
                "sourceKind": "silver",
                "sourceDomain": "hard_negative",
                "teacherConfidence": 0.6,
                "rawRuntimeOutputs": {"label": "Highlight"},
                "rawTeacherOutputs": {"label": "other"},
                "humanVerified": False,
            }
        )

        self.assertEqual(components["selectedLabelSource"], "teacher")
        self.assertGreater(components["weight"], 0.0)
        self.assertGreaterEqual(components["hardExampleMultiplier"], 1.0)


if __name__ == "__main__":
    unittest.main()

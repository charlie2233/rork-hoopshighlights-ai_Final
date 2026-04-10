from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets.runtime_training import (
    LORA_DATASET_VERSION,
    RUNTIME_TRAINING_FEATURE_VERSION,
    build_runtime_training_bundle,
    example_weight,
    is_ignored,
    lora_example_weight,
)


class RuntimeTrainingDataTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_build_runtime_training_bundle_exports_split_matrices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            manifest = build_runtime_training_bundle(self.repo_root(), output_dir)

            self.assertEqual(manifest["featureVersion"], RUNTIME_TRAINING_FEATURE_VERSION)
            self.assertEqual(manifest["schemaVersion"], "2026-03-30")
            self.assertIn("train", manifest["summary"]["splits"])
            self.assertIn("val", manifest["summary"]["splits"])
            self.assertIn("test", manifest["summary"]["splits"])
            self.assertGreater(manifest["summary"]["totalRecords"], 0)
            self.assertGreater(manifest["summary"]["activeRecords"], 0)

            records_path = output_dir / "all_records.jsonl"
            self.assertTrue(records_path.exists())
            records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(any(record["sourceKind"] == "gold" for record in records))
            self.assertTrue(any(record["sourceKind"] == "silver" for record in records))
            self.assertTrue(any(record["sourceKind"] == "disagreement" for record in records))
            self.assertTrue(all(record["split"] in {"train", "val", "test"} for record in records))
            self.assertTrue(all(record["schemaVersion"] == "2026-03-30" for record in records))
            self.assertTrue(all(record["split"] != "train" for record in records if record["sourceKind"] == "gold"))

            for split in ("train", "val", "test"):
                split_dir = output_dir / split
                payload = json.loads((split_dir / "features.json").read_text(encoding="utf-8"))
                self.assertGreaterEqual(len(payload["featureNames"]), 1)
                self.assertEqual(len(payload["rows"]), len(payload["matrix"]))
                self.assertTrue(any(name.startswith("runtime") or name.startswith("ball") for name in payload["featureNames"]))

            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertTrue((output_dir / "feature_names.json").exists())

            lora_manifest = json.loads((output_dir / "videomae_lora_v1" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(lora_manifest["datasetVersion"], LORA_DATASET_VERSION)
            self.assertGreater(lora_manifest["summary"]["trainingEligibleRecords"], 0)
            self.assertGreater(lora_manifest["summary"]["calibrationAnchorRecords"], 0)

            lora_train_records = [
                json.loads(line)
                for line in (output_dir / "videomae_lora_v1" / "train" / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            lora_val_records = [
                json.loads(line)
                for line in (output_dir / "videomae_lora_v1" / "val" / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            lora_test_records = [
                json.loads(line)
                for line in (output_dir / "videomae_lora_v1" / "test" / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(record["sourceKind"] == "gold" for record in lora_train_records))
            self.assertTrue(any(record["calibrationAnchor"] for record in lora_val_records if record["sourceKind"] == "gold"))
            self.assertTrue(any(record["calibrationAnchor"] for record in lora_test_records if record["sourceKind"] == "gold"))
            self.assertTrue(
                any(
                    (not record["trainingEligible"]) and record["exclusionReason"] == "missing_source_ref"
                    for record in lora_train_records + lora_val_records + lora_test_records
                    if record["sourceKind"] == "disagreement"
                )
            )
            self.assertTrue(
                any(record["trainingEligible"] and record["sourceRef"] for record in lora_train_records if record["sourceKind"] in {"gold", "silver"})
            )

    def test_low_confidence_silver_rows_are_ignored(self) -> None:
        self.assertEqual(example_weight("silver", 0.6, None), 0.0)
        self.assertTrue(is_ignored("silver", 0.6, None))
        self.assertGreater(example_weight("silver", 0.95, None), example_weight("silver", 0.82, None))
        self.assertEqual(lora_example_weight("silver", 0.6, None), 0.0)
        self.assertGreater(lora_example_weight("gold", 1.0, None), lora_example_weight("silver", 0.95, None))
        self.assertGreater(lora_example_weight("silver", 0.95, None), lora_example_weight("silver", 0.8, None))


if __name__ == "__main__":
    unittest.main()

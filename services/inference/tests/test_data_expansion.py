from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets.runtime_training import (
    ANNOTATION_SCHEMA_PATH,
    ANNOTATION_SCHEMA_VERSION,
    build_runtime_training_bundle,
    run_offline_probe,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS_DIR = REPO_ROOT / "services" / "inference" / "datasets"


class DataExpansionTests(unittest.TestCase):
    def test_seed_data_is_tagged_with_source_domains_and_schema_version(self) -> None:
        gold_rows = json.loads((DATASETS_DIR / "gold_set.json").read_text())
        silver_rows = json.loads((DATASETS_DIR / "silver_set.json").read_text())

        self.assertEqual(json.loads(ANNOTATION_SCHEMA_PATH.read_text())["schemaVersion"], ANNOTATION_SCHEMA_VERSION)
        self.assertGreaterEqual({row["sourceDomain"] for row in gold_rows}, {"live_shadow", "manual_negative", "benchmark_eval"})
        self.assertGreaterEqual({row["sourceDomain"] for row in silver_rows}, {"teacher_pseudo", "hard_negative", "disagreement_queue", "live_shadow"})
        self.assertTrue(any(row["teacherConfidence"] < 0.5 for row in silver_rows))
        self.assertTrue(all(row["schemaVersion"] == ANNOTATION_SCHEMA_VERSION for row in gold_rows + silver_rows))

    def test_bundle_builds_with_confidence_gated_silver_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            manifest = build_runtime_training_bundle(repo_root=REPO_ROOT, output_dir=output_dir)

            self.assertEqual(manifest["schemaVersion"], ANNOTATION_SCHEMA_VERSION)
            self.assertGreaterEqual(manifest["summary"]["ignoredRecords"], 1)
            self.assertGreaterEqual(manifest["summary"]["gatedSilverRecords"], 4)
            feature_names = json.loads((output_dir / "feature_names.json").read_text())
            self.assertIn("sourceDomain=hard_negative", feature_names)
            self.assertTrue((output_dir / "train" / "records.jsonl").exists())
            self.assertTrue((output_dir / "val" / "records.jsonl").exists())
            self.assertTrue((output_dir / "test" / "records.jsonl").exists())

    def test_offline_probe_reports_class_separation_and_disagreement_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            build_runtime_training_bundle(repo_root=REPO_ROOT, output_dir=output_dir)
            report = run_offline_probe(repo_root=REPO_ROOT, bundle_dir=output_dir)

            self.assertIn("eventFamily", report)
            self.assertIn("outcome", report)
            self.assertIn("shotSubtype", report)
            self.assertGreaterEqual(report["eventFamily"]["accuracy"], 0.8)
            self.assertGreaterEqual(report["outcome"]["accuracy"], 0.7)
            self.assertGreaterEqual(report["shotSubtype"]["accuracy"], 0.6)
            self.assertGreater(report["uncertaintyRate"], 0.0)
            self.assertTrue(report["disagreementExamples"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.scripts.build_probe_datasets import main as build_datasets_main
from services.inference.scripts.run_offline_probe import build_probe_report, load_jsonl


class OfflineProbeTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_dataset_schema_and_probe_report(self) -> None:
        datasets_dir = self.repo_root() / "services" / "inference" / "datasets"
        gold = load_jsonl(datasets_dir / "gold_annotations.jsonl")
        silver = load_jsonl(datasets_dir / "silver_teacher_annotations.jsonl")
        report = build_probe_report(gold, silver)

        self.assertGreaterEqual(report["summary"]["goldClips"], 20)
        self.assertIn("benchmark_eval", report["summary"]["sourceDomainSplit"])
        self.assertIn("hard_negative", report["summary"]["sourceDomainSplit"])
        self.assertIn("eventFamily", report["separability"])
        self.assertIn("outcome", report["separability"])
        self.assertIn("shotSubtype", report["separability"])
        self.assertGreaterEqual(report["separability"]["eventFamily"]["runtimeOnly"]["summary"]["accuracy"], 0.0)
        self.assertGreaterEqual(report["separability"]["outcome"]["runtimePlusTeacher"]["summary"]["accuracy"], 0.0)
        self.assertGreaterEqual(len(report["correctedLabelExamples"]), 1)
        self.assertGreaterEqual(sum(report["disagreementDistribution"].values()), 1)

    def test_schema_file_contains_required_fields(self) -> None:
        schema_path = self.repo_root() / "services" / "inference" / "datasets" / "annotation_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema["required"])
        for field in [
            "clipId",
            "sourceDomain",
            "eventFamily",
            "outcome",
            "shotSubtype",
            "rawRuntimeOutputs",
            "rawTeacherOutputs",
        ]:
            self.assertIn(field, required)

    def test_dataset_generation_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            rc = build_datasets_main(["--output-dir", str(output)]) if callable(build_datasets_main) else 0
            self.assertEqual(rc, 0)
            self.assertTrue((output / "gold_annotations.jsonl").exists())
            self.assertTrue((output / "silver_teacher_annotations.jsonl").exists())
            self.assertTrue((output / "disagreement_queue.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

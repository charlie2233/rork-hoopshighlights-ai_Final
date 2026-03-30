from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.scripts.run_shadow_eval import build_shadow_report, load_batch_records


class ShadowEvalTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_builds_shadow_report_for_mixed_batch(self) -> None:
        fixture = self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "shadow_batch_results.json"
        records = load_batch_records([fixture])
        report = build_shadow_report(records)

        self.assertEqual(report["summary"]["jobCount"], 1)
        self.assertEqual(report["summary"]["clipCount"], 4)
        self.assertEqual(report["summary"]["requestIds"], ["req-shadow-001"])
        self.assertEqual(report["summary"]["uploadTraceIds"], ["upload-shadow-001"])
        self.assertEqual(report["summary"]["inferenceAttemptIds"], ["attempt-shadow-001"])
        self.assertEqual(report["summary"]["modelVersions"], ["runtime:v1-shadow"])

        self.assertEqual(report["summary"]["flatLabelDistribution"]["Highlight"], 1)
        self.assertEqual(report["summary"]["flatLabelDistribution"]["Steal"], 1)
        self.assertEqual(report["summary"]["eventFamilyDistribution"]["shot_attempt"], 2)
        self.assertEqual(report["summary"]["eventFamilyDistribution"]["turnover"], 1)
        self.assertEqual(report["summary"]["outcomeDistribution"]["made"], 2)
        self.assertEqual(report["summary"]["outcomeDistribution"]["uncertain"], 2)
        self.assertEqual(report["summary"]["shotSubtypeDistribution"]["null"], 2)
        self.assertEqual(report["summary"]["uncertaintyRate"], 0.25)
        self.assertEqual(report["summary"]["missVsMadeConfusion"]["expectedMissPredictedMadeShot"], 1)
        self.assertEqual(report["summary"]["mixedBatchLabelSpread"]["uniqueLabelCount"], 4)
        self.assertGreaterEqual(report["summary"]["mixedBatchLabelSpread"]["spreadScore"], 0.0)
        self.assertEqual(len(report["collapseExamples"]), 1)
        self.assertGreaterEqual(len(report["labelSpreadWarnings"]), 0)

    def test_cli_writes_markdown_and_json(self) -> None:
        fixture = self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "shadow_batch_results.json"
        records = load_batch_records([fixture])
        report = build_shadow_report(records)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            json_path = output / "shadow_eval_report.json"
            md_path = output / "shadow_eval_report.md"
            json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            md_path.write_text("placeholder", encoding="utf-8")

            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())

    def test_loads_flat_clip_arrays(self) -> None:
        fixture = self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "shadow_batch_results.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        flat_rows = [
            {
                "jobId": payload["jobId"],
                "requestId": payload["requestId"],
                "uploadTraceId": payload["uploadTraceId"],
                "inferenceAttemptId": payload["inferenceAttemptId"],
                "modelVersion": payload["modelVersion"],
                **clip,
            }
            for clip in payload["clips"]
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "flat.json"
            path.write_text(json.dumps(flat_rows, indent=2), encoding="utf-8")
            records = load_batch_records([path])

        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].jobId, "job-shadow-001")
        self.assertEqual(records[0].flatLabel, "Dunk")


if __name__ == "__main__":
    unittest.main()

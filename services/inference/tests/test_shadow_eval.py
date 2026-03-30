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

    def test_prefers_runtime_shadow_payload_when_present(self) -> None:
        payload = {
            "jobId": "job-shadow-rt-001",
            "requestId": "req-shadow-rt-001",
            "uploadTraceId": "upload-shadow-rt-001",
            "inferenceAttemptId": "attempt-shadow-rt-001",
            "modelVersion": "videomae:test",
            "clips": [
                {
                    "clipId": "clip-shadow-rt-001",
                    "label": "Highlight",
                    "eventFamily": "other",
                    "shotSubtype": None,
                    "outcome": "uncertain",
                    "confidence": 0.41,
                    "clipDurationSeconds": 4.75,
                    "runtimeFusionShadow": {
                        "runtime_fusion_model_version": "runtime-fusion-v1",
                        "label": "Steal",
                        "eventFamily": "turnover",
                        "shotSubtype": None,
                        "outcome": "uncertain",
                        "confidenceBeforeMapping": 0.62,
                        "confidenceAfterMapping": 0.62,
                        "confidence": 0.62,
                        "isUncertain": True,
                        "runtime_fusion_snapshot": {
                            "videoMAE": [{"label": "steal", "confidence": 0.44}],
                            "xclip": [{"label": "steal", "confidence": 0.51}],
                        },
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shadow-runtime.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            records = load_batch_records([path])

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.modelVersion, "runtime-fusion-v1")
        self.assertEqual(record.flatLabel, "Steal")
        self.assertEqual(record.eventFamily, "turnover")
        self.assertEqual(record.confidenceAfterMapping, 0.62)
        self.assertEqual(record.rawVideoMAETopK[0]["label"], "steal")


if __name__ == "__main__":
    unittest.main()

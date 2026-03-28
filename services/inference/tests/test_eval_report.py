from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.scripts.run_eval_report import build_report, load_eval_rows, load_predictions


class EvalReportTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_builds_report_with_taxonomy_metrics(self) -> None:
        base = self.repo_root() / "services" / "inference" / "evals"
        eval_rows = load_eval_rows(base / "basketball_eval_set.json")
        predictions = load_predictions(base / "baseline_predictions.json")
        report = build_report(eval_rows, predictions)

        self.assertEqual(report["summary"]["totalClips"], 18)
        self.assertIn("three", report["perClass"])
        self.assertGreater(report["summary"]["accuracy"], 0.0)
        self.assertGreaterEqual(len(report["recommendedLabelingPriorities"]), 1)

        clip_stats = report["summary"]["clipDurationStats"]
        self.assertEqual(clip_stats["belowMinimumCount"], 0)
        self.assertEqual(clip_stats["belowMinimumPercentage"], 0.0)
        self.assertEqual(clip_stats["sourceShorterThanMinimumCount"], 0)
        self.assertGreater(clip_stats["medianSeconds"], 0.0)
        self.assertGreaterEqual(clip_stats["p90Seconds"], clip_stats["medianSeconds"])
        self.assertEqual(clip_stats["mergedClipCount"], 2)

        self.assertIn("fast break", report["perLabelDurationDistribution"])
        self.assertEqual(report["perLabelDurationDistribution"]["fast break"]["mergedCount"], 2)

        taxonomy_metrics = report["taxonomyMetrics"]
        self.assertIn("eventFamily", taxonomy_metrics)
        self.assertIn("shotSubtype", taxonomy_metrics)
        self.assertIn("outcome", taxonomy_metrics)
        self.assertGreater(taxonomy_metrics["eventFamily"]["summary"]["top1Accuracy"], 0.0)
        self.assertGreaterEqual(taxonomy_metrics["shotSubtype"]["summary"]["topKHitRate"], taxonomy_metrics["shotSubtype"]["summary"]["top1Accuracy"])
        self.assertIn("three", taxonomy_metrics["shotSubtype"]["perClass"])
        self.assertIn("blocked", taxonomy_metrics["outcome"]["perClass"])

        confusion_matrices = report["confusionMatrices"]
        self.assertIn("displayLabel", confusion_matrices)
        self.assertIn("eventFamily", confusion_matrices)
        self.assertIn("shotSubtype", confusion_matrices)
        self.assertIn("outcome", confusion_matrices)

    def test_markdown_and_json_round_trip(self) -> None:
        base = self.repo_root() / "services" / "inference" / "evals"
        eval_rows = load_eval_rows(base / "basketball_eval_set.json")
        predictions = load_predictions(base / "baseline_predictions.json")
        report = build_report(eval_rows, predictions)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            output.write_text(json.dumps(report), encoding="utf-8")
            loaded = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(loaded["summary"]["totalClips"], 18)
        self.assertIn("taxonomyMetrics", loaded)


if __name__ == "__main__":
    unittest.main()

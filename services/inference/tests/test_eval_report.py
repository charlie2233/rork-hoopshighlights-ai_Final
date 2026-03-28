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

    def test_builds_report_with_label_priorities(self) -> None:
        base = self.repo_root() / "services" / "inference" / "evals"
        eval_rows = load_eval_rows(base / "basketball_eval_set.json")
        predictions = load_predictions(base / "baseline_predictions.json")
        report = build_report(eval_rows, predictions)

        self.assertEqual(report["summary"]["totalClips"], 14)
        self.assertIn("jumper", report["perClass"])
        self.assertGreater(report["summary"]["accuracy"], 0.0)
        self.assertGreaterEqual(len(report["recommendedLabelingPriorities"]), 1)

    def test_markdown_and_json_round_trip(self) -> None:
        base = self.repo_root() / "services" / "inference" / "evals"
        eval_rows = load_eval_rows(base / "basketball_eval_set.json")
        predictions = load_predictions(base / "baseline_predictions.json")
        report = build_report(eval_rows, predictions)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            output.write_text(json.dumps(report), encoding="utf-8")
            loaded = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(loaded["summary"]["totalClips"], 14)


if __name__ == "__main__":
    unittest.main()

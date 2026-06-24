from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend"))

from app.evaluation import evaluate_clip_rerank  # noqa: E402


class ClipRerankEvaluationTests(unittest.TestCase):
    def test_eval_harness_reports_ranking_metrics_and_error_buckets(self) -> None:
        fixture = json.loads((Path(__file__).parent / "fixtures" / "detection_eval_fixture.json").read_text(encoding="utf-8"))

        metrics = evaluate_clip_rerank(fixture["predictions"], fixture["groundTruth"], k_values=[1, 3, 5])

        self.assertEqual(metrics["metricVersion"], "clip-rerank-eval-v1")
        self.assertEqual(metrics["truePositive"], 3)
        self.assertEqual(metrics["falsePositive"], 2)
        self.assertEqual(metrics["falseNegative"], 0)
        self.assertEqual(metrics["precision"], 0.6)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertGreater(metrics["f1"], 0.7)
        self.assertGreater(metrics["ndcg"], 0.9)
        self.assertGreater(metrics["mrr"], 0.6)
        self.assertAlmostEqual(metrics["recallAtK"]["1"], 1 / 3, places=6)
        self.assertEqual(metrics["recallAtK"]["3"], 1.0)
        self.assertEqual(metrics["precisionAtK"]["5"], 0.6)
        self.assertEqual(metrics["errorBuckets"]["duplicate"], 1)
        self.assertEqual(metrics["errorBuckets"]["bad_window"], 1)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import numpy as np

from services.inference.training.hard_negative_mining import (
    focal_reweighting,
    hard_example_multiplier,
    hard_example_signal,
    summarize_hard_examples,
)


class HardNegativeMiningTests(unittest.TestCase):
    def test_hard_example_signal_favors_disagreement_and_hard_negative_domains(self) -> None:
        easy_row = {"sourceKind": "gold", "sourceDomain": "staging_smoke", "features": {}}
        hard_row = {
            "sourceKind": "disagreement",
            "sourceDomain": "hard_negative",
            "priorityScore": 0.8,
            "teacherConfidence": 0.92,
            "features": {"reason=miss_vs_made_conflict": 1},
        }

        easy_signal = hard_example_signal(easy_row)
        hard_signal = hard_example_signal(hard_row)

        self.assertLess(easy_signal, hard_signal)
        self.assertAlmostEqual(hard_example_multiplier(hard_row, base_multiplier=1.8), 1.0 + 1.8 * hard_signal, places=4)

    def test_focal_reweighting_upweights_misclassified_examples(self) -> None:
        probabilities = np.asarray([[0.92, 0.08], [0.41, 0.59]], dtype=np.float64)
        labels = ["made", "missed"]
        classes = ["made", "missed"]
        weights = focal_reweighting(probabilities, labels, classes, gamma=1.5)

        self.assertLess(weights[0], weights[1])
        self.assertGreater(weights[1], 0.0)

    def test_summarize_hard_examples_reports_domain_counts(self) -> None:
        summary = summarize_hard_examples(
            [
                {"sourceKind": "gold", "sourceDomain": "staging_smoke"},
                {"sourceKind": "disagreement", "sourceDomain": "hard_negative", "priorityScore": 0.9, "features": {"reason=hard_negative": 1}},
                {"sourceKind": "disagreement", "sourceDomain": "benchmark_eval", "priorityScore": 0.7, "features": {"reason=miss_vs_made_conflict": 1}},
            ]
        )

        self.assertEqual(summary["rowCount"], 3)
        self.assertEqual(summary["hardExampleCount"], 2)
        self.assertEqual(summary["hardExampleRate"], 0.6667)
        self.assertEqual(summary["bySourceKind"]["disagreement"], 2)


if __name__ == "__main__":
    unittest.main()

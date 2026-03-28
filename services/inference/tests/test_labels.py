from __future__ import annotations

import unittest

from app.labels import (
    CanonicalLabelScore,
    CANONICAL_ACTION_LABELS,
    aggregate_label_scores,
    build_xclip_prompts,
    canonical_to_display_label,
    normalize_action_label,
)


class LabelNormalizationTests(unittest.TestCase):
    def test_normalizes_common_video_model_labels(self) -> None:
        self.assertEqual(normalize_action_label("BasketballDunk"), "dunk")
        self.assertEqual(normalize_action_label("three pointer"), "jumper")
        self.assertEqual(normalize_action_label("fast-break transition"), "fast break")
        self.assertEqual(canonical_to_display_label("jumper"), "Made Shot")

    def test_aggregate_label_scores_keeps_best_score_per_canonical_label(self) -> None:
        aggregated = aggregate_label_scores(
            [
                CanonicalLabelScore(label="dunk", confidence=0.61, raw_label="BasketballDunk"),
                CanonicalLabelScore(label="dunk", confidence=0.83, raw_label="slam dunk"),
                CanonicalLabelScore(label="steal", confidence=0.52, raw_label="Steal"),
            ]
        )

        self.assertEqual([item.label for item in aggregated], ["dunk", "steal"])
        self.assertAlmostEqual(aggregated[0].confidence, 0.83)

    def test_xclip_prompt_order_matches_canonical_labels(self) -> None:
        prompts = build_xclip_prompts()
        self.assertEqual(len(prompts), len(CANONICAL_ACTION_LABELS))
        self.assertIn("a basketball dunk", prompts[0])


if __name__ == "__main__":
    unittest.main()

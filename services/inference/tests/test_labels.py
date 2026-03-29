from __future__ import annotations

import unittest

from services.inference.app.labels import (
    CanonicalLabelScore,
    CANONICAL_ACTION_LABELS,
    aggregate_label_scores,
    aggregate_raw_label_scores,
    build_xclip_prompts,
    canonical_to_display_label,
    derive_basketball_taxonomy,
    normalize_action_label,
    xclip_prompt_set_version,
)
from services.inference.app.models import RawLabelScore


class LabelNormalizationTests(unittest.TestCase):
    def test_normalizes_common_video_model_labels(self) -> None:
        self.assertEqual(normalize_action_label("BasketballDunk"), "dunk")
        self.assertEqual(normalize_action_label("three pointer"), "three")
        self.assertEqual(normalize_action_label("fast-break transition"), "fast break")
        self.assertEqual(normalize_action_label("crowd reaction"), "uncertain")
        self.assertEqual(canonical_to_display_label("three"), "Three Pointer")

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
        self.assertGreater(len(prompts), len(CANONICAL_ACTION_LABELS))
        self.assertIn("a powerful basketball dunk at the rim", prompts)
        self.assertIn("a generic basketball hype clip without a clear shot or defensive play", prompts)
        self.assertEqual(xclip_prompt_set_version(), "xclip-bball-v2")

    def test_aggregate_raw_label_scores_keeps_best_score_per_raw_label(self) -> None:
        aggregated = aggregate_raw_label_scores(
            [
                RawLabelScore(rawLabel="jump shot", canonicalLabel="jumper", confidence=0.61, modelVersion="videomae:test"),
                RawLabelScore(rawLabel="jump shot", canonicalLabel="jumper", confidence=0.83, modelVersion="videomae:test"),
                RawLabelScore(rawLabel="a basketball layup", canonicalLabel="layup", confidence=0.52, modelVersion="xclip:test"),
            ]
        )

        self.assertEqual(len(aggregated), 2)
        self.assertEqual(aggregated[0].rawLabel, "jump shot")
        self.assertAlmostEqual(aggregated[0].confidence, 0.83)

    def test_derive_taxonomy_abstains_on_low_confidence_jumpers(self) -> None:
        taxonomy = derive_basketball_taxonomy(
            "jumper",
            0.51,
            [
                CanonicalLabelScore(label="jumper", confidence=0.51),
                CanonicalLabelScore(label="miss", confidence=0.46),
            ],
        )

        self.assertEqual(taxonomy.event_family, "shot")
        self.assertEqual(taxonomy.shot_subtype, "jumper")
        self.assertEqual(taxonomy.outcome, "uncertain")
        self.assertEqual(taxonomy.display_label, "Highlight")
        self.assertTrue(taxonomy.is_uncertain)

    def test_derive_taxonomy_keeps_defensive_event_diversity(self) -> None:
        taxonomy = derive_basketball_taxonomy("block", 0.84)

        self.assertEqual(taxonomy.event_family, "defensive_event")
        self.assertEqual(taxonomy.event_subtype, "block")
        self.assertEqual(taxonomy.outcome, "blocked")
        self.assertEqual(taxonomy.display_label, "Block")

    def test_derive_taxonomy_distinguishes_three_and_putback(self) -> None:
        three_taxonomy = derive_basketball_taxonomy("three", 0.81)
        putback_taxonomy = derive_basketball_taxonomy("putback", 0.78)

        self.assertEqual(three_taxonomy.shot_subtype, "three")
        self.assertEqual(three_taxonomy.display_label, "Three Pointer")
        self.assertEqual(putback_taxonomy.shot_subtype, "putback")
        self.assertEqual(putback_taxonomy.display_label, "Made Shot")

    def test_derive_taxonomy_prefers_shot_family_with_uncertain_outcome(self) -> None:
        taxonomy = derive_basketball_taxonomy(
            "three",
            0.42,
            [
                CanonicalLabelScore(label="three", confidence=0.42),
                CanonicalLabelScore(label="miss", confidence=0.33),
                CanonicalLabelScore(label="fast break", confidence=0.12),
            ],
            prompt_set_version="xclip-bball-v2",
        )

        self.assertEqual(taxonomy.event_family, "shot")
        self.assertEqual(taxonomy.shot_subtype, "three")
        self.assertIn(taxonomy.display_label, {"Three Pointer", "Highlight"})
        self.assertEqual(taxonomy.prompt_set_version, "xclip-bball-v2")


if __name__ == "__main__":
    unittest.main()

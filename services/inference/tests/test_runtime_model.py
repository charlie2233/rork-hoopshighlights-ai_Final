from __future__ import annotations

import unittest

from services.inference.app.models import ActionPrediction, LabelScore
from services.inference.app.runtime_model import (
    build_runtime_feature_dict,
    build_runtime_snapshot,
    derive_runtime_display_label,
    get_runtime_fusion_bundle,
)


def _action(
    *,
    label: str,
    canonical_label: str,
    confidence: float,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
    top_labels: list[tuple[str, float]] | None = None,
) -> ActionPrediction:
    ranked = [
        LabelScore(label=name, confidence=score, rawLabel=name, modelVersion="unit-test")
        for name, score in (top_labels or [(canonical_label, confidence)])
    ]
    return ActionPrediction(
        label=label,
        canonicalLabel=canonical_label,
        confidence=confidence,
        modelVersion="unit-test",
        eventFamily=event_family,
        outcome=outcome,
        shotSubtype=shot_subtype,
        topLabels=ranked,
    )


class RuntimeModelTests(unittest.TestCase):
    def test_runtime_bundle_loads(self) -> None:
        bundle = get_runtime_fusion_bundle()

        self.assertIsNotNone(bundle)
        assert bundle is not None
        self.assertEqual(bundle.model_version, "runtime-fusion-v1")
        self.assertIn("eventFamily", bundle.targets)
        self.assertIn("outcome", bundle.targets)
        self.assertIn("shotSubtype", bundle.targets)

    def test_display_label_derivation_never_maps_miss_to_made_shot(self) -> None:
        canonical_label, display_label = derive_runtime_display_label(
            event_family="shot_attempt",
            outcome="missed",
            shot_subtype="jumper",
        )

        self.assertEqual(canonical_label, "miss")
        self.assertEqual(display_label, "Highlight")

    def test_runtime_feature_builder_keeps_shared_training_schema(self) -> None:
        action = _action(
            label="Highlight",
            canonical_label="miss",
            confidence=0.58,
            event_family="shot_attempt",
            outcome="missed",
            shot_subtype="jumper",
            top_labels=[("miss", 0.58), ("jumper", 0.44), ("three", 0.22)],
        )
        snapshot = build_runtime_snapshot(
            action=action,
            structured_signals={
                "ballNearRim": 0.81,
                "ballThroughHoopLikelihood": 0.06,
                "shotReleaseCandidate": 0.73,
            },
            primary_action=action,
            comparison_action=action,
            clip_duration_seconds=4.9,
            event_center_seconds=2.45,
            pre_roll_seconds=2.4,
            post_roll_seconds=2.5,
            source_event_count=1,
            was_merged=False,
        )
        feature_dict = build_runtime_feature_dict(snapshot)

        self.assertIn("runtimeConfidence", feature_dict)
        self.assertIn("ballNearRim", feature_dict)
        self.assertIn("runtimeLabel=highlight", feature_dict)
        self.assertIn("runtimeVideoMAE=miss", feature_dict)
        self.assertGreater(feature_dict["clipDurationSeconds"], 0.0)


if __name__ == "__main__":
    unittest.main()

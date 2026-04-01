from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets import ANNOTATION_SCHEMA_VERSION
from services.inference.scripts.build_disagreement_queue import (
    build_disagreement_queue,
    build_summary,
    load_annotations,
    render_markdown,
    write_artifacts,
)


class DisagreementQueueTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def fixture_path(self) -> Path:
        return self.repo_root() / "services" / "inference" / "tests" / "fixtures" / "disagreement_annotations.json"

    def test_builds_prioritized_queue_from_high_value_disagreements(self) -> None:
        annotations = load_annotations(self.fixture_path())
        queue = build_disagreement_queue(
            annotations,
            min_teacher_confidence=0.75,
            max_runtime_confidence=0.55,
            min_ball_evidence=0.7,
        )

        self.assertEqual(len(queue), 4)
        highlight_disagree = next(item for item in queue if item.clip_id == "clip-highlight-disagree-001")
        self.assertEqual(highlight_disagree.schema_version, ANNOTATION_SCHEMA_VERSION)
        self.assertIn("runtime_teacher_disagree", highlight_disagree.priority_reasons)
        self.assertIn("runtime_missed_likely_event", highlight_disagree.priority_reasons)
        self.assertIn("app_facing_label_only_highlight", highlight_disagree.priority_reasons)
        self.assertIn("strong_ball_hoop_evidence_null_subtype", highlight_disagree.priority_reasons)
        self.assertIn("high_teacher_low_runtime", highlight_disagree.priority_reasons)
        self.assertIn("uncertainty_sampling", highlight_disagree.priority_reasons)
        self.assertIn("event_localization_needed", highlight_disagree.priority_reasons)
        self.assertEqual(highlight_disagree.event_localization_state, "coarse")
        self.assertAlmostEqual(highlight_disagree.event_center_seconds or 0.0, 2.9)

        miss_made = next(item for item in queue if item.clip_id == "clip-miss-made-001")
        self.assertIn("miss_vs_made_conflict", miss_made.priority_reasons)
        self.assertIn("runtime_teacher_disagree", miss_made.priority_reasons)

        strong_signal = next(item for item in queue if item.clip_id == "clip-null-subtype-strong-evidence-001")
        self.assertIn("strong_ball_hoop_evidence_null_subtype", strong_signal.priority_reasons)
        self.assertIn("high_teacher_low_runtime", strong_signal.priority_reasons)

        high_teacher_low_runtime = next(item for item in queue if item.clip_id == "clip-high-teacher-low-runtime-001")
        self.assertIn("high_teacher_low_runtime", high_teacher_low_runtime.priority_reasons)
        self.assertNotIn("runtime_missed_likely_event", high_teacher_low_runtime.priority_reasons)
        self.assertNotIn("clip-human-verified-gold-001", [item.clip_id for item in queue])

    def test_rendered_outputs_are_stable_and_machine_readable(self) -> None:
        annotations = load_annotations(self.fixture_path())
        queue = build_disagreement_queue(annotations)
        summary = build_summary(queue, annotations)

        self.assertEqual(summary["queuedClips"], 4)
        self.assertEqual(summary["byBucket"]["runtime_missed_likely_event"], 1)
        self.assertEqual(summary["byBucket"]["runtime_teacher_disagree"], 3)
        self.assertEqual(summary["byEventLocalizationState"]["coarse"], 1)
        self.assertEqual(summary["byEventLocalizationState"]["missing"], 3)
        self.assertEqual(summary["bySourceDomain"]["broadcast"], 1)
        self.assertEqual(summary["bySourceDomain"]["fixed_camera"], 3)

        markdown = render_markdown(summary, queue)
        self.assertIn("# Disagreement Review Queue", markdown)
        self.assertIn("## Event Localization", markdown)
        self.assertIn("clip-highlight-disagree-001", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path, md_path = write_artifacts(Path(temp_dir), summary, queue)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["queuedClips"], 4)
            self.assertEqual(len(payload["queue"]), 4)
            self.assertTrue(md_path.exists())


if __name__ == "__main__":
    unittest.main()

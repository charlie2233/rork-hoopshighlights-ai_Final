from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.scripts.build_disagreement_queue import (
    UnifiedClipAnnotation,
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
        self.assertEqual(queue[0].clip_id, "clip-highlight-disagree-001")
        self.assertEqual(queue[0].schema_version, annotations[0].schema_version)
        self.assertIn("runtime_teacher_disagree", queue[0].priority_reasons)
        self.assertIn("app_facing_label_only_highlight", queue[0].priority_reasons)
        self.assertIn("strong_ball_hoop_evidence_null_subtype", queue[0].priority_reasons)
        self.assertIn("high_teacher_low_runtime", queue[0].priority_reasons)
        self.assertTrue(queue[0].hard_example)
        self.assertGreater(queue[0].hard_example_weight, 1.0)

        miss_made = next(item for item in queue if item.clip_id == "clip-miss-made-001")
        self.assertIn("miss_vs_made_conflict", miss_made.priority_reasons)
        self.assertIn("runtime_teacher_disagree", miss_made.priority_reasons)
        self.assertTrue(miss_made.hard_example)

        strong_signal = next(item for item in queue if item.clip_id == "clip-null-subtype-strong-evidence-001")
        self.assertIn("strong_ball_hoop_evidence_null_subtype", strong_signal.priority_reasons)
        self.assertIn("high_teacher_low_runtime", strong_signal.priority_reasons)
        self.assertIn(strong_signal.hard_example_tier, {"critical", "high", "medium"})

        high_teacher_low_runtime = next(item for item in queue if item.clip_id == "clip-high-teacher-low-runtime-001")
        self.assertIn("high_teacher_low_runtime", high_teacher_low_runtime.priority_reasons)
        self.assertNotIn("clip-human-verified-gold-001", [item.clip_id for item in queue])

    def test_rendered_outputs_are_stable_and_machine_readable(self) -> None:
        annotations = load_annotations(self.fixture_path())
        queue = build_disagreement_queue(annotations)
        summary = build_summary(queue, annotations)

        self.assertEqual(summary["queuedClips"], 4)
        self.assertEqual(summary["byBucket"]["runtime_teacher_disagree"], 4)
        self.assertEqual(summary["bySourceDomain"]["broadcast"], 1)
        self.assertEqual(summary["bySourceDomain"]["fixed_camera"], 3)
        self.assertEqual(summary["hardExampleQueued"], 4)
        self.assertGreaterEqual(summary["hardExampleByTier"].get("critical", 0), 1)

        markdown = render_markdown(summary, queue)
        self.assertIn("# Disagreement Review Queue", markdown)
        self.assertIn("clip-highlight-disagree-001", markdown)
        self.assertIn("hard=", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path, md_path = write_artifacts(Path(temp_dir), summary, queue)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["queuedClips"], 4)
            self.assertEqual(len(payload["queue"]), 4)
            self.assertTrue(md_path.exists())

    def test_ineligible_teacher_pseudo_labels_do_not_drive_disagreement_scoring(self) -> None:
        queue = build_disagreement_queue(
            [
                UnifiedClipAnnotation(
                    clip_id="clip-low-confidence-teacher-001",
                    source_domain="fixed_camera",
                    schema_version="2026-03-31",
                    event_family="shot_attempt",
                    outcome="missed",
                    shot_subtype="jumper",
                    ball_visible=True,
                    hoop_visible=True,
                    ball_near_rim=0.81,
                    ball_through_hoop_likelihood=0.12,
                    possession_change_likelihood=0.04,
                    transition_likelihood=0.05,
                    teacher_confidence=0.63,
                    human_verified=False,
                    reviewer_notes="Teacher was uncertain; do not train on this.",
                    raw_runtime_outputs={
                        "label": "Highlight",
                        "eventFamily": "shot_attempt",
                        "outcome": "made",
                        "shotSubtype": None,
                        "confidence": 0.41,
                    },
                    raw_teacher_outputs={
                        "displayLabelSuggestion": "Highlight",
                        "eventFamily": "shot_attempt",
                        "outcome": "missed",
                        "shotSubtype": "jumper",
                        "confidence": 0.63,
                        "pseudoLabel": {"eligible": False, "reason": "confidence_below_threshold"},
                    },
                )
            ],
            min_teacher_confidence=0.75,
            max_runtime_confidence=0.55,
            min_ball_evidence=0.7,
        )

        self.assertEqual(len(queue), 1)
        self.assertNotIn("runtime_teacher_disagree", queue[0].priority_reasons)
        self.assertNotIn("miss_vs_made_conflict", queue[0].priority_reasons)
        self.assertIn("app_facing_label_only_highlight", queue[0].priority_reasons)
        self.assertIn("strong_ball_hoop_evidence_null_subtype", queue[0].priority_reasons)


if __name__ == "__main__":
    unittest.main()

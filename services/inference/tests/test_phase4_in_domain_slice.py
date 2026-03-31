from __future__ import annotations

import json
import unittest
from pathlib import Path

from services.inference.datasets import load_annotation_rows


class Phase4InDomainSliceTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_phase4_slice_loads_and_covers_live_domains(self) -> None:
        path = self.repo_root() / "services" / "inference" / "datasets" / "phase4_in_domain_annotations.json"
        rows = load_annotation_rows(path)

        self.assertGreaterEqual(len(rows), 6)
        self.assertIn("staging_smoke", {row.sourceDomain for row in rows})
        self.assertIn("live_staging", {row.sourceDomain for row in rows})
        self.assertIn("live_shadow", {row.sourceDomain for row in rows})
        self.assertTrue(any(row.humanVerified for row in rows))
        self.assertTrue(any(not row.humanVerified for row in rows))
        self.assertTrue(any(row.eventStart is not None for row in rows))
        self.assertTrue(any(row.shotReleaseTime is not None for row in rows))
        self.assertTrue(any(row.transitionStartTime is not None for row in rows))

    def test_phase4_queue_prioritizes_disagreements_and_hard_negatives(self) -> None:
        path = self.repo_root() / "services" / "inference" / "datasets" / "phase4_event_localization_queue.jsonl"
        queue_rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.assertGreaterEqual(len(queue_rows), 5)
        self.assertEqual(queue_rows, sorted(queue_rows, key=lambda row: (-row["priorityScore"], row["clipId"])))

        reasons = {reason for row in queue_rows for reason in row["reasons"]}
        self.assertIn("runtime_teacher_outcome_disagreement", reasons)
        self.assertIn("app_facing_highlight_only", reasons)
        self.assertIn("event_family_other", reasons)
        self.assertIn("high_uncertainty", reasons)
        self.assertTrue(any(row["eventStart"] is not None for row in queue_rows))


if __name__ == "__main__":
    unittest.main()

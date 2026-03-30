from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets import annotation_template, load_annotation_rows, write_annotation_rows


class AnnotationDatasetTests(unittest.TestCase):
    def test_round_trip_annotation_rows(self) -> None:
        row = annotation_template(clip_id="clip-001", source_domain="gold:human_review")
        row.eventFamily = "shot_attempt"
        row.outcome = "missed"
        row.shotSubtype = "jumper"
        row.ballVisible = True
        row.hoopVisible = True
        row.ballNearRim = 0.83
        row.ballThroughHoopLikelihood = 0.12
        row.possessionChangeLikelihood = 0.09
        row.transitionLikelihood = 0.14
        row.teacherConfidence = 0.67
        row.humanVerified = True
        row.reviewerNotes = "Clean miss with visible rim."
        row.rawRuntimeOutputs = {"label": "Highlight"}
        row.rawTeacherOutputs = {"eventFamily": "shot_attempt"}

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "annotations.json"
            write_annotation_rows(path, [row])
            reloaded = load_annotation_rows(path)

        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0].clipId, "clip-001")
        self.assertEqual(reloaded[0].eventFamily, "shot_attempt")
        self.assertEqual(reloaded[0].outcome, "missed")
        self.assertEqual(reloaded[0].rawTeacherOutputs["eventFamily"], "shot_attempt")

    def test_write_rejects_probability_out_of_range(self) -> None:
        row = annotation_template(clip_id="clip-002", source_domain="silver:teacher")
        row.ballNearRim = 1.2

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "annotations.json"
            with self.assertRaisesRegex(ValueError, "ballNearRim"):
                write_annotation_rows(path, [row])

    def test_load_rejects_missing_required_fields(self) -> None:
        payload = [
            {
                "clipId": "clip-003",
                "sourceDomain": "gold:human_review",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "annotations.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required fields"):
                load_annotation_rows(path)


if __name__ == "__main__":
    unittest.main()

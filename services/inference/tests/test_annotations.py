from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets import (
    ANNOTATION_SCHEMA_VERSION,
    annotation_template,
    derive_coarse_event_window,
    load_annotation_rows,
    write_annotation_rows,
)


class AnnotationDatasetTests(unittest.TestCase):
    @staticmethod
    def repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    def test_round_trip_annotation_rows(self) -> None:
        row = annotation_template(clip_id="clip-001", source_domain="gold:human_review")
        row.eventFamily = "shot_attempt"
        row.outcome = "missed"
        row.shotSubtype = "jumper"
        row.sourceRef = "r2://basketball/gold/clip-001.mp4"
        row.ballVisible = True
        row.hoopVisible = True
        row.ballNearRim = 0.83
        row.ballThroughHoopLikelihood = 0.12
        row.possessionChangeLikelihood = 0.09
        row.transitionLikelihood = 0.14
        row.eventStart = 1.2
        row.eventCenter = 2.4
        row.eventEnd = 3.8
        row.shotReleaseTime = 1.8
        row.ballNearRimTime = 2.8
        row.ballThroughHoopTime = 3.1
        row.possessionChangeTime = 0.9
        row.transitionStartTime = 0.3
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
        self.assertEqual(reloaded[0].sourceRef, "r2://basketball/gold/clip-001.mp4")
        self.assertEqual(reloaded[0].eventFamily, "shot_attempt")
        self.assertEqual(reloaded[0].outcome, "missed")
        self.assertEqual(reloaded[0].rawTeacherOutputs["eventFamily"], "shot_attempt")
        self.assertEqual(reloaded[0].eventStart, 1.2)
        self.assertEqual(reloaded[0].transitionStartTime, 0.3)

    def test_annotation_template_defaults_event_localization_fields_to_null(self) -> None:
        row = annotation_template(clip_id="clip-004", source_domain="gold:human_review")
        self.assertIsNone(row.eventStart)
        self.assertIsNone(row.eventCenter)
        self.assertIsNone(row.eventEnd)
        self.assertIsNone(row.shotReleaseTime)
        self.assertIsNone(row.ballNearRimTime)
        self.assertIsNone(row.ballThroughHoopTime)
        self.assertIsNone(row.possessionChangeTime)
        self.assertIsNone(row.transitionStartTime)

    def test_legacy_rows_load_with_missing_event_localization_fields(self) -> None:
        payload = [
            {
                "clipId": "clip-legacy",
                "sourceDomain": "gold:human_review",
                "schemaVersion": ANNOTATION_SCHEMA_VERSION,
                "sourceRef": None,
                "eventFamily": "other",
                "outcome": "uncertain",
                "shotSubtype": None,
                "ballVisible": False,
                "hoopVisible": False,
                "ballNearRim": None,
                "ballThroughHoopLikelihood": None,
                "possessionChangeLikelihood": None,
                "transitionLikelihood": None,
                "teacherConfidence": None,
                "humanVerified": False,
                "reviewerNotes": "",
                "rawRuntimeOutputs": {},
                "rawTeacherOutputs": None,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "annotations.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            reloaded = load_annotation_rows(path)

        self.assertIsNone(reloaded[0].eventStart)
        self.assertIsNone(reloaded[0].eventCenter)
        self.assertIsNone(reloaded[0].eventEnd)
        self.assertIsNone(reloaded[0].shotReleaseTime)

    def test_derive_coarse_event_window_clips_to_source_duration(self) -> None:
        window = derive_coarse_event_window(5.0, clip_duration_seconds=6.0, half_window_seconds=1.5)
        self.assertEqual(window["eventCenter"], 5.0)
        self.assertEqual(window["eventStart"], 3.5)
        self.assertEqual(window["eventEnd"], 6.0)

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

    def test_loads_seed_gold_set_rows(self) -> None:
        path = self.repo_root() / "services" / "inference" / "datasets" / "gold_set.json"
        rows = load_annotation_rows(path)

        self.assertGreaterEqual(len(rows), 16)
        self.assertTrue(rows[0].humanVerified)
        self.assertIsNotNone(rows[0].sourceRef)
        self.assertEqual(rows[0].schemaVersion, ANNOTATION_SCHEMA_VERSION)
        self.assertIsNotNone(rows[0].teacherConfidence)
        self.assertGreaterEqual(rows[0].teacherConfidence, 0.0)
        self.assertLessEqual(rows[0].teacherConfidence, 1.0)
        self.assertIn("broadcast", {row.sourceDomain for row in rows})
        self.assertIn("fixed_camera_indoor", {row.sourceDomain for row in rows})
        self.assertIn("fixed_camera_outdoor", {row.sourceDomain for row in rows})
        self.assertIn("phone_casual", {row.sourceDomain for row in rows})

    def test_seed_silver_set_rows_cover_new_domains(self) -> None:
        path = self.repo_root() / "services" / "inference" / "datasets" / "silver_set.json"
        rows = load_annotation_rows(path)

        self.assertGreaterEqual(len(rows), 16)
        self.assertFalse(rows[0].humanVerified)
        self.assertIn("broadcast", {row.sourceDomain for row in rows})
        self.assertIn("fixed_camera_indoor", {row.sourceDomain for row in rows})
        self.assertIn("fixed_camera_outdoor", {row.sourceDomain for row in rows})
        self.assertIn("phone_casual", {row.sourceDomain for row in rows})


if __name__ == "__main__":
    unittest.main()

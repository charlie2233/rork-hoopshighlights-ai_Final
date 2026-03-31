from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets.dataset_bridge import (
    DEFAULT_BARD_SOURCE_DOMAIN,
    DEFAULT_EBARD_SOURCE_DOMAIN,
    DEFAULT_SPORTSMOT_SOURCE_DOMAIN,
    DEFAULT_TRACKID3X3_SOURCE_DOMAIN,
    import_bard_event_rows,
    import_ebard_detection_rows,
    import_external_basketball_dataset,
    import_sportsmot_tracking_rows,
    import_trackid3x3_tracking_rows,
    load_records,
)
from services.inference.scripts.import_external_basketball_dataset import main as import_cli_main


class DatasetBridgeTests(unittest.TestCase):
    def test_import_bard_event_rows_maps_hierarchy_and_evidence(self) -> None:
        rows = import_bard_event_rows(
            [
                {
                    "clip_id": "bard-made-001",
                    "label": "made layup",
                    "source_ref": "r2://clips/bard-made-001.mp4",
                    "evidenceText": "Drive and finish at the rim.",
                    "confidence": 0.91,
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.sourceDomain, DEFAULT_BARD_SOURCE_DOMAIN)
        self.assertEqual(row.eventFamily, "shot_attempt")
        self.assertEqual(row.outcome, "made")
        self.assertEqual(row.shotSubtype, "layup")
        self.assertEqual(row.sourceRef, "r2://clips/bard-made-001.mp4")
        self.assertFalse(row.humanVerified)
        self.assertEqual(row.rawTeacherOutputs["sourceKind"], "bard-event")
        self.assertIn("evidenceText", row.rawTeacherOutputs["evidence"])
        self.assertIn("sourceLabel", row.rawTeacherOutputs["evidence"])

    def test_import_bard_event_rows_maps_negative_to_other(self) -> None:
        rows = import_bard_event_rows(
            [
                {
                    "clipId": "bard-negative-001",
                    "label": "camera pan replay after timeout",
                    "confidence": 0.63,
                }
            ]
        )

        row = rows[0]
        self.assertEqual(row.eventFamily, "other")
        self.assertEqual(row.outcome, "uncertain")
        self.assertIsNone(row.shotSubtype)
        self.assertEqual(row.rawTeacherOutputs["sourceDataset"], "BARD")
        self.assertEqual(row.sourceDomain, DEFAULT_BARD_SOURCE_DOMAIN)
        self.assertEqual(row.rawTeacherOutputs["sourceDomainTag"], DEFAULT_BARD_SOURCE_DOMAIN)

    def test_import_ebard_detection_rows_uses_detection_evidence(self) -> None:
        rows = import_ebard_detection_rows(
            [
                {
                    "clipId": "ebard-det-001",
                    "detections": [
                        {"label": "ball", "score": 0.93, "bbox": [0.35, 0.4, 0.42, 0.47], "frameIndex": 2},
                        {"label": "rim", "score": 0.9, "bbox": [0.38, 0.39, 0.46, 0.45], "frameIndex": 2},
                        {"label": "player", "score": 0.88, "bbox": [0.2, 0.5, 0.5, 0.9], "frameIndex": 2},
                    ],
                    "sourceRef": "s3://ebard/clip-001.mp4",
                    "evidence": {"annotator": "detector"},
                }
            ]
        )

        row = rows[0]
        self.assertEqual(row.sourceDomain, DEFAULT_EBARD_SOURCE_DOMAIN)
        self.assertTrue(row.ballVisible)
        self.assertTrue(row.hoopVisible)
        self.assertEqual(row.eventFamily, "shot_attempt")
        self.assertEqual(row.outcome, "uncertain")
        self.assertGreater(row.ballNearRim, 0.0)
        self.assertIn("detections", row.rawTeacherOutputs)
        self.assertEqual(row.rawTeacherOutputs["sourceKind"], "ebard-detection")
        self.assertEqual(row.rawTeacherOutputs["evidence"]["evidence"]["annotator"], "detector")

    def test_import_sportsmot_tracking_rows_maps_transition_context(self) -> None:
        rows = import_sportsmot_tracking_rows(
            [
                {
                    "clipId": "sportsmot-fastbreak-001",
                    "sequenceLabel": "fast break transition finish",
                    "tracks": [
                        {"trackId": "player-1", "label": "player", "score": 0.95, "bbox": [0.1, 0.2, 0.2, 0.6], "frameIndex": 1},
                        {"trackId": "ball-1", "label": "ball", "score": 0.97, "bbox": [0.3, 0.35, 0.35, 0.42], "frameIndex": 2},
                        {"trackId": "player-2", "label": "player", "score": 0.92, "bbox": [0.45, 0.18, 0.55, 0.58], "frameIndex": 2},
                    ],
                    "sourceRef": "s3://sportsmot/clip-001.mp4",
                    "confidence": 0.84,
                }
            ]
        )

        row = rows[0]
        self.assertEqual(row.sourceDomain, DEFAULT_SPORTSMOT_SOURCE_DOMAIN)
        self.assertEqual(row.eventFamily, "transition")
        self.assertEqual(row.outcome, "uncertain")
        self.assertTrue(row.ballVisible)
        self.assertFalse(row.hoopVisible)
        self.assertEqual(row.rawTeacherOutputs["sourceKind"], "sportsmot-tracking")
        self.assertEqual(row.rawTeacherOutputs["canonicalHierarchy"]["eventFamily"], "transition")
        self.assertEqual(row.rawTeacherOutputs["sourceDomainTag"], DEFAULT_SPORTSMOT_SOURCE_DOMAIN)

    def test_import_trackid3x3_rows_maps_fixed_camera_setup_to_other(self) -> None:
        rows = import_trackid3x3_tracking_rows(
            [
                {
                    "clipId": "trackid3x3-setup-001",
                    "sequenceLabel": "half-court setup before event",
                    "cameraType": "fixed",
                    "tracks": [
                        {"trackId": "p1", "label": "player", "score": 0.9, "bbox": [0.12, 0.25, 0.2, 0.62], "frameIndex": 1},
                        {"trackId": "p2", "label": "player", "score": 0.91, "bbox": [0.34, 0.22, 0.42, 0.61], "frameIndex": 1},
                    ],
                    "sourceRef": "s3://trackid3x3/clip-setup-001.mp4",
                    "confidence": 0.69,
                }
            ]
        )

        row = rows[0]
        self.assertEqual(row.sourceDomain, DEFAULT_TRACKID3X3_SOURCE_DOMAIN)
        self.assertEqual(row.eventFamily, "other")
        self.assertEqual(row.outcome, "uncertain")
        self.assertFalse(row.hoopVisible)
        self.assertEqual(row.rawTeacherOutputs["sourceKind"], "trackid3x3-tracking")
        self.assertEqual(row.rawTeacherOutputs["canonicalHierarchy"]["eventFamily"], "other")

    def test_import_external_basketball_dataset_summary(self) -> None:
        result = import_external_basketball_dataset(
            [{"clipId": "bard-made-001", "label": "made dunk"}],
            source_kind="bard-event",
            source_domain="bard:events:test",
            source_dataset="BARD-test",
        )

        summary = result.to_summary()
        self.assertEqual(summary["sourceKind"], "bard-event")
        self.assertEqual(summary["sourceDomain"], "bard:events:test")
        self.assertEqual(summary["sourceDataset"], "BARD-test")
        self.assertEqual(summary["rowCount"], 1)

        tracking_result = import_external_basketball_dataset(
            [{"clipId": "sportsmot-setup-001", "sequenceLabel": "setup only", "tracks": [{"label": "player", "score": 0.8}]}],
            source_kind="sportsmot-tracking",
        )
        tracking_summary = tracking_result.to_summary()
        self.assertEqual(tracking_summary["sourceKind"], "sportsmot-tracking")
        self.assertEqual(tracking_summary["sourceDomain"], DEFAULT_SPORTSMOT_SOURCE_DOMAIN)

    def test_cli_round_trip_writes_canonical_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            input_path = tmp / "input.jsonl"
            output_path = tmp / "output.json"
            summary_path = tmp / "summary.json"
            input_path.write_text(
                "\n".join(
                    [
                        json.dumps({"clipId": "bard-made-002", "label": "made three"}),
                        json.dumps({"clipId": "bard-miss-002", "label": "missed jumper"}),
                    ]
                ),
                encoding="utf-8",
            )

            import sys

            argv = sys.argv
            try:
                sys.argv = [
                    "import_external_basketball_dataset.py",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-kind",
                    "bard-event",
                    "--summary",
                    str(summary_path),
                ]
                self.assertEqual(import_cli_main(), 0)
            finally:
                sys.argv = argv

            rows = load_records(output_path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["sourceDomain"], DEFAULT_BARD_SOURCE_DOMAIN)
            self.assertEqual(rows[0]["eventFamily"], "shot_attempt")
            self.assertTrue(summary_path.exists())

    def test_load_records_supports_json_array_and_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            json_path = tmp / "rows.json"
            jsonl_path = tmp / "rows.jsonl"
            json_path.write_text(json.dumps([{"clipId": "one"}]), encoding="utf-8")
            jsonl_path.write_text(json.dumps({"clipId": "two"}) + "\n", encoding="utf-8")
            self.assertEqual(len(load_records(json_path)), 1)
            self.assertEqual(len(load_records(jsonl_path)), 1)


if __name__ == "__main__":
    unittest.main()

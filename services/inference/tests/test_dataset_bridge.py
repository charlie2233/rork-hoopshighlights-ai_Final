from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.inference.datasets.dataset_bridge import (
    DEFAULT_BARD_SOURCE_DOMAIN,
    DEFAULT_EBARD_SOURCE_DOMAIN,
    import_bard_event_rows,
    import_ebard_detection_rows,
    import_external_basketball_dataset,
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
                    "label": "replay",
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


if __name__ == "__main__":
    unittest.main()

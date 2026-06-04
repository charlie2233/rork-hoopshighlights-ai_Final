import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_team_highlight_review_queue import build_review_queue, render_markdown_queue


class ExportTeamHighlightReviewQueueTests(unittest.TestCase):
    def test_exports_only_incomplete_launch_label_rows_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            labels_path = root / "case_a" / "manual_labels_template.json"
            labels_path.parent.mkdir(parents=True)
            labels_path.write_text(
                json.dumps(
                    {
                        "caseId": "case_a",
                        "videoId": "video_a",
                        "teamMode": "team",
                        "selectedTeamId": "team_black",
                        "clips": [
                            {
                                "labelId": "label_001",
                                "predictionClipId": "clip_1",
                                "start": 1.0,
                                "end": 5.0,
                                "needsLabel": True,
                                "reviewedByHuman": False,
                                "expected": {
                                    "teamId": None,
                                    "isHighlight": None,
                                    "eventType": None,
                                    "outcome": None,
                                },
                                "predicted": {
                                    "label": "Block",
                                    "outcome": "blocked",
                                    "keep": True,
                                    "confidence": 0.93,
                                    "teamId": "team_black",
                                    "teamAttributionStatus": "matched",
                                },
                            },
                            {
                                "labelId": "label_002",
                                "predictionClipId": "clip_2",
                                "start": 6.0,
                                "end": 9.0,
                                "needsLabel": False,
                                "reviewedByHuman": True,
                                "expected": {
                                    "teamId": "team_black",
                                    "isHighlight": True,
                                    "eventType": "made_shot",
                                    "outcome": "made",
                                },
                                "predicted": {"label": "Made shot"},
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "team-highlight-accuracy-manifest-v1",
                        "cases": [
                            {
                                "caseId": "case_a",
                                "videoId": "video_a",
                                "teamMode": "team",
                                "selectedTeamId": "team_black",
                                "labels": "case_a/manual_labels_template.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            rows = build_review_queue(manifest_path=manifest_path, include_complete=False, limit=0)
            markdown = render_markdown_queue(
                manifest_path=manifest_path,
                rows=rows,
                include_complete=False,
                limit=0,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["labelId"], "label_001")
        self.assertIn("expected.teamId", rows[0]["missingFields"])
        self.assertIn("reviewedByHuman=true", rows[0]["missingFields"])
        self.assertIn("label_001", markdown)
        self.assertIn("1.00s-5.00s", markdown)
        self.assertIn("Block", markdown)
        self.assertIn("This file is reviewer navigation help only", markdown)
        self.assertNotIn("label_002", markdown)

    def test_limit_caps_rows_without_marking_anything_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            labels_path = root / "labels.json"
            labels_path.write_text(
                json.dumps(
                    {
                        "caseId": "case_a",
                        "videoId": "video_a",
                        "clips": [
                            {
                                "labelId": "label_001",
                                "needsLabel": True,
                                "expected": {},
                            },
                            {
                                "labelId": "label_002",
                                "needsLabel": True,
                                "expected": {},
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps([{"caseId": "case_a", "labels": str(labels_path)}]), encoding="utf-8")

            rows = build_review_queue(manifest_path=manifest_path, include_complete=False, limit=1)

        self.assertEqual([row["labelId"] for row in rows], ["label_001"])
        self.assertIn("needsLabel=false", rows[0]["missingFields"])


if __name__ == "__main__":
    unittest.main()

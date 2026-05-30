import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_team_highlight_label_review_page import build_review_payload, render_review_page


class BuildTeamHighlightLabelReviewPageTests(unittest.TestCase):
    def test_builds_local_review_page_without_raw_urls_or_object_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "accuracy" / "case_a" / "analysis_result.json"
            labels_path = root / "accuracy" / "case_a" / "manual_labels_template.json"
            video_path = root / "source.mp4"
            video_path.write_bytes(b"fake video")
            analysis_path.parent.mkdir(parents=True)
            write_json(
                analysis_path,
                {
                    "jobId": "job_123",
                    "uploadUrl": "https://r2.example.test/upload?X-Amz-Signature=secret",
                    "sourceObjectKey": "uploads/job_123/source.mp4",
                    "results": {
                        "videoId": "video_a",
                        "sourceUrl": "https://r2.example.test/source?X-Amz-Signature=secret",
                        "detectedTeams": [
                            {"teamId": "team_black", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93},
                            {"teamId": "team_white", "label": "White jerseys", "colorLabel": "white", "confidence": 0.91},
                        ],
                        "clips": [
                            {
                                "id": "clip_1",
                                "startTime": 1.0,
                                "endTime": 5.0,
                                "eventCenter": 3.0,
                                "label": "Made Shot",
                            }
                        ],
                    },
                },
            )
            write_json(
                labels_path,
                {
                    "schemaVersion": "team-highlight-manual-label-template-v1",
                    "caseId": "case_a",
                    "videoId": "video_a",
                    "teamMode": "team",
                    "selectedTeamId": "team_black",
                    "selectedTeamColorLabel": "black",
                    "detectedTeams": [
                        {"teamId": "team_black", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93},
                    ],
                    "clips": [
                        {
                            "labelId": "label_001",
                            "predictionIndex": 0,
                            "predictionClipId": "clip_1",
                            "start": 1.0,
                            "end": 5.0,
                            "needsLabel": True,
                            "predicted": {
                                "label": "Made Shot",
                                "teamId": "team_black",
                                "teamConfidence": 0.91,
                                "teamAttributionStatus": "matched",
                                "outcome": "made",
                                "eventCenter": 3.0,
                            },
                            "expected": {"teamId": None, "isHighlight": None, "eventType": None, "outcome": None},
                            "labelingNotes": "",
                        }
                    ],
                },
            )

            payload = build_review_payload(
                manifest={
                    "schemaVersion": "team-highlight-accuracy-manifest-v1",
                    "cases": [
                        {
                            "caseId": "case_a",
                            "videoId": "video_a",
                            "teamMode": "team",
                            "selectedTeamId": "team_black",
                            "analysisResult": "accuracy/case_a/analysis_result.json",
                            "labels": "accuracy/case_a/manual_labels_template.json",
                        }
                    ],
                },
                manifest_dir=root,
                video_paths={},
                default_video_path=video_path,
            )
            page = render_review_page(payload, title="Review")

        self.assertIn("case_a", page)
        self.assertIn("clip_1", page)
        self.assertIn("Event 3.000s", page)
        self.assertIn("seekClip(&quot;video_a&quot;, 3.000)", page)
        self.assertNotIn('onclick="seekClip("', page)
        self.assertIn(video_path.as_uri(), page)
        self.assertIn("downloadCaseLabels", page)
        self.assertNotIn("X-Amz-Signature", page)
        self.assertNotIn("sourceObjectKey", page)
        self.assertNotIn("uploadUrl", page)
        self.assertNotIn("sourceUrl", page)

    def test_missing_video_mapping_fails_with_actionable_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            write_json(analysis_path, {"results": {"videoId": "video_a", "clips": [{"id": "clip_1"}]}})
            write_json(
                labels_path,
                {
                    "caseId": "case_a",
                    "videoId": "video_a",
                    "clips": [
                        {
                            "labelId": "label_001",
                            "predictionIndex": 0,
                            "predictionClipId": "clip_1",
                            "start": 1.0,
                            "end": 5.0,
                            "needsLabel": True,
                            "predicted": {},
                            "expected": {},
                        }
                    ],
                },
            )

            with self.assertRaisesRegex(ValueError, "Missing source video path"):
                build_review_payload(
                    manifest={"cases": [{"analysisResult": "analysis.json", "labels": "labels.json"}]},
                    manifest_dir=root,
                    video_paths={},
                    default_video_path=None,
                )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

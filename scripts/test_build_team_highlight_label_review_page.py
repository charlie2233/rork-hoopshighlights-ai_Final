import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_team_highlight_label_review_page import build_review_payload, render_review_page, review_page_output_metadata


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
        self.assertIn("Label Progress", page)
        self.assertIn("team_black / selected team", page)
        self.assertIn('value="block"', page)
        self.assertIn('value="steal"', page)
        self.assertIn('value="defensive_stop"', page)
        self.assertIn('value="blocked"', page)
        self.assertIn("seekClip(&quot;video_a&quot;, 3.000)", page)
        self.assertNotIn('onclick="seekClip("', page)
        self.assertIn(video_path.as_uri(), page)
        self.assertIn("downloadCaseLabels", page)
        self.assertIn("downloadAllCaseLabels", page)
        self.assertIn("Next incomplete", page)
        self.assertIn("focusNextIncomplete", page)
        self.assertIn("markReviewedAndNext", page)
        self.assertIn("Fill team, highlight, event, and outcome", page)
        self.assertIn('tabindex="-1"', page)
        self.assertIn("Import draft bundle", page)
        self.assertIn("bundle-import", page)
        self.assertIn("importDraftBundle", page)
        self.assertIn("applyDraftBundlePayload", page)
        self.assertIn("humanReviewRequired", page)
        self.assertIn("team-highlight-manual-label-bundle-v1", page)
        self.assertIn("team_highlight_manual_labels_bundle.json", page)
        self.assertIn("team-highlight-manual-label-draft-v1", page)
        self.assertIn("hoopclips-team-label-draft", page)
        self.assertIn("prefill:none", page)
        self.assertIn("restoreDraft", page)
        self.assertIn("clearSavedDraft", page)
        self.assertIn("clipCompleteFromCard", page)
        self.assertIn("Download anyway", page)
        self.assertIn("Download all anyway", page)
        self.assertNotIn("Approve all", page)
        self.assertNotIn("markAllReviewed", page)
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

    def test_draft_bundle_prefills_expected_fields_but_still_requires_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            video_path = root / "source.mp4"
            video_path.write_bytes(b"fake video")
            write_json(analysis_path, {"results": {"videoId": "video_a", "clips": [{"id": "clip_1"}]}})
            write_json(
                labels_path,
                {
                    "caseId": "case_a",
                    "videoId": "video_a",
                    "selectedTeamId": "team_black",
                    "selectedTeamColorLabel": "black",
                    "clips": [
                        {
                            "labelId": "label_001",
                            "predictionClipId": "clip_1",
                            "start": 1.0,
                            "end": 5.0,
                            "needsLabel": True,
                            "predicted": {"eventCenter": 3.0},
                            "expected": {"teamId": None, "isHighlight": None, "eventType": None, "outcome": None},
                        }
                    ],
                },
            )

            payload = build_review_payload(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                video_paths={},
                default_video_path=video_path,
                draft_bundle={
                    "schemaVersion": "team-highlight-manual-label-bundle-v1",
                    "source": "gpt_team_highlight_label_draft",
                    "humanReviewRequired": True,
                    "cases": [
                        {
                            "caseId": "case_a",
                            "clips": [
                                {
                                    "labelId": "label_001",
                                    "predictionClipId": "clip_1",
                                    "needsLabel": False,
                                    "expected": {
                                        "teamId": "team_black",
                                        "isHighlight": True,
                                        "eventType": "block",
                                        "outcome": "blocked",
                                        "sourceUrl": "https://r2.example.test/source?X-Amz-Signature=secret",
                                    },
                                    "labelingNotes": "GPT draft: visible block by black jerseys.",
                                }
                            ],
                        }
                    ],
                },
            )
            page = render_review_page(payload, title="Review")

        self.assertEqual(payload["draftPrefill"]["appliedClipCount"], 1)
        self.assertTrue(payload["draftPrefill"]["humanReviewRequired"])
        self.assertTrue(payload["cases"][0]["clips"][0]["needsLabel"])
        self.assertEqual(payload["cases"][0]["clips"][0]["expected"]["eventType"], "block")
        self.assertEqual(
            review_page_output_metadata(Path("/tmp/review.html"), payload),
            {
                "output": "/tmp/review.html",
                "caseCount": 1,
                "clipCount": 1,
                "draftPrefill": {
                    "schemaVersion": "team-highlight-label-review-draft-prefill-v1",
                    "source": "draft_bundle",
                    "appliedClipCount": 1,
                    "skippedClipCount": 0,
                    "humanReviewRequired": True,
                },
            },
        )
        self.assertIn("GPT draft prefilled 1 clips", page)
        self.assertIn("draftPrefill", page)
        self.assertIn("prefill:${draftPrefill.source", page)
        self.assertIn('value="team_black" selected', page)
        self.assertIn('value="true" selected', page)
        self.assertIn('value="block" selected', page)
        self.assertIn('value="blocked" selected', page)
        self.assertIn("GPT draft: visible block by black jerseys.", page)
        self.assertNotIn('class="reviewed" type="checkbox" checked', page)
        self.assertNotIn("X-Amz-Signature", page)
        self.assertNotIn("sourceUrl", page)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

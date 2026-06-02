import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_team_highlight_label_review_page import (
    build_review_payload,
    parse_video_angle_paths,
    parse_video_angle_urls,
    parse_video_urls,
    render_review_page,
    review_page_output_metadata,
)


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
        self.assertIn("review-position", page)
        self.assertIn("Current queue position will appear here.", page)
        self.assertIn("missing-fields", page)
        self.assertIn("Needs: reviewed, team, highlight, event, outcome", page)
        self.assertIn("missingFieldsFromCard", page)
        self.assertIn("updateClipMissingFields", page)
        self.assertIn("focusFirstMissingField", page)
        self.assertIn("Complete", page)
        self.assertIn("Shortcuts:", page)
        self.assertIn("J/L scrub", page)
        self.assertIn("team_black / selected team", page)
        self.assertIn('value="block"', page)
        self.assertIn('value="steal"', page)
        self.assertIn('value="defensive_stop"', page)
        self.assertIn('value="blocked"', page)
        self.assertIn("seekClip(&quot;video_a&quot;, 3.000)", page)
        self.assertIn('id="video-video-a-main"', page)
        self.assertIn("videoElementsFor(videoId)", page)
        self.assertNotIn('onclick="seekClip("', page)
        self.assertIn('data-video-id="video_a"', page)
        self.assertIn('data-start-seconds="1.000"', page)
        self.assertIn('data-event-seconds="3.000"', page)
        self.assertIn('data-finish-seconds="5.000"', page)
        self.assertIn("handleReviewShortcut", page)
        self.assertIn('window.addEventListener("keydown", handleReviewShortcut)', page)
        self.assertIn('["input", "select", "textarea"].includes(targetTag)', page)
        self.assertIn('seekClipFromCard(card, "event")', page)
        self.assertIn("markReviewedAndNext(Number(card.dataset.caseIndex)", page)
        self.assertIn("Use prediction", page)
        self.assertIn("fillFromPrediction", page)
        self.assertIn("eventTypeFromPrediction", page)
        self.assertIn("outcomeFromPrediction", page)
        self.assertIn('card.querySelector(".reviewed").checked = false', page)
        self.assertIn("Fast-filled from HoopClips prediction; verify video before marking reviewed.", page)
        self.assertIn("Selected highlight", page)
        self.assertIn("Not highlight", page)
        self.assertIn("Bad window", page)
        self.assertIn("quickLabelClip", page)
        self.assertIn("selectedTeamValue", page)
        self.assertIn("Quick-labeled as selected-team highlight after human review.", page)
        self.assertIn("Quick-labeled as not a highlight after human review.", page)
        self.assertIn("Quick-labeled as bad timing window after human review.", page)
        self.assertIn("scrubVideosForCard", page)
        self.assertIn("togglePlaybackForCard", page)
        self.assertIn("Playing synced angles.", page)
        self.assertIn('["s", "e", "f", "j", "k", "l", "p", "r", "n", "1", "2", "3"].includes(key)', page)
        self.assertIn("scrubVideosForCard(card, -0.5)", page)
        self.assertIn("togglePlaybackForCard(card)", page)
        self.assertIn("scrubVideosForCard(card, 0.5)", page)
        self.assertIn('quickLabelClip(Number(card.dataset.caseIndex), Number(card.dataset.clipIndex), "selected_highlight")', page)
        self.assertIn(video_path.as_uri(), page)
        self.assertIn(".video-panel", page)
        self.assertIn("position: sticky", page)
        self.assertIn("max-height: min(42vh, 420px)", page)
        self.assertIn("downloadCaseLabels", page)
        self.assertIn("downloadProgressCheckpoint", page)
        self.assertIn("Download progress checkpoint", page)
        self.assertIn("team_highlight_label_review_page_progress_checkpoint", page)
        self.assertIn("team_highlight_manual_labels_progress_", page)
        self.assertIn("--allow-incomplete only", page)
        self.assertIn("download-ready-button", page)
        self.assertIn("download-checkpoint-button", page)
        self.assertIn("downloadLaunchReadyLabels", page)
        self.assertIn("Download launch-ready labels", page)
        self.assertIn("Finish labels first", page)
        self.assertIn("Finish ${incomplete} label", page)
        self.assertIn("Finish every label before downloading launch-ready labels", page)
        self.assertIn("Next incomplete", page)
        self.assertIn("Next close review", page)
        self.assertIn("priority-filter", page)
        self.assertIn("All 1", page)
        self.assertIn("Close 0", page)
        self.assertIn("Standard 1", page)
        self.assertIn("Quick 0", page)
        self.assertIn("setPriorityFilter", page)
        self.assertIn("updatePriorityFilterVisibility", page)
        self.assertIn("card.hidden = !matches", page)
        self.assertIn("allClipCards({ visibleOnly: false })", page)
        self.assertIn("focusNextIncomplete", page)
        self.assertIn("focusNextCloseReview", page)
        self.assertIn('data-review-priority="standard_review"', page)
        self.assertIn("review-priority standard-review", page)
        self.assertIn("markReviewedAndNext", page)
        self.assertIn("Fill ${missing.join", page)
        self.assertIn("before marking this clip reviewed", page)
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
        self.assertIn("updateReviewPosition", page)
        self.assertIn("Current ${visibleIndex}/${visibleCards.length} visible", page)
        self.assertIn("Overall ${counts.complete}/${counts.total} complete", page)
        self.assertIn("Local draft restored from ${new Date(payload.savedAt).toLocaleString()}: ${counts.complete}/${counts.total} complete.", page)
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

    def test_local_video_url_mapping_supports_browser_smoke_without_remote_urls(self) -> None:
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
                            "predicted": {"eventCenter": 3.0},
                            "expected": {},
                        }
                    ],
                },
            )

            payload = build_review_payload(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                video_paths={},
                video_urls=parse_video_urls(["video_a=http://127.0.0.1:8787/artifacts/source.mp4"]),
                default_video_path=None,
            )
            page = render_review_page(payload, title="Review")

        self.assertEqual(payload["videos"]["video_a"], "http://127.0.0.1:8787/artifacts/source.mp4")
        self.assertIn('src="http://127.0.0.1:8787/artifacts/source.mp4"', page)
        self.assertNotIn("X-Amz-Signature", page)
        self.assertNotIn("sourceObjectKey", page)

    def test_multi_angle_video_mapping_seeks_synced_local_angles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            broadcast_path = root / "broadcast.mp4"
            baseline_path = root / "baseline.mp4"
            broadcast_path.write_bytes(b"fake broadcast")
            baseline_path.write_bytes(b"fake baseline")
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
                            "predicted": {"eventCenter": 3.0},
                            "expected": {},
                        }
                    ],
                },
            )

            payload = build_review_payload(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                video_paths={},
                video_angle_paths=parse_video_angle_paths([f"video_a:broadcast={broadcast_path}"]),
                video_angle_urls=parse_video_angle_urls(["video_a:baseline=http://127.0.0.1:8787/baseline.mp4"]),
                default_video_path=None,
            )
            page = render_review_page(payload, title="Review")

        self.assertEqual(len(payload["videoAngles"]["video_a"]), 2)
        self.assertEqual(payload["videoAngles"]["video_a"][0]["angleId"], "broadcast")
        self.assertEqual(payload["videoAngles"]["video_a"][1]["angleId"], "baseline")
        self.assertEqual(payload["videos"]["video_a"], broadcast_path.resolve().as_uri())
        self.assertIn("Source Video: video_a (2 angles)", page)
        self.assertIn('id="video-video-a-broadcast"', page)
        self.assertIn('id="video-video-a-baseline"', page)
        self.assertIn("videoElementsFor(videoId)", page)
        self.assertIn("videos.forEach(video =>", page)
        self.assertEqual(review_page_output_metadata(Path("/tmp/review.html"), payload)["videoAngleCount"], 2)
        self.assertNotIn("X-Amz-Signature", page)

    def test_video_url_mapping_rejects_remote_or_presigned_urls(self) -> None:
        with self.assertRaisesRegex(ValueError, "localhost"):
            parse_video_urls(["video_a=https://r2.example.test/source.mp4"])
        with self.assertRaisesRegex(ValueError, "query strings"):
            parse_video_urls(["video_a=http://127.0.0.1:8787/source.mp4?X-Amz-Signature=secret"])
        with self.assertRaisesRegex(ValueError, "signed URL"):
            parse_video_urls(["video_a=http://127.0.0.1:8787/source-signature=secret.mp4"])

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
                "videoAngleCount": 1,
                "reviewPriorityCounts": {
                    "quick_check": 1,
                },
                "draftPrefill": {
                    "schemaVersion": "team-highlight-label-review-draft-prefill-v1",
                    "source": "draft_bundle",
                    "appliedClipCount": 1,
                    "skippedClipCount": 0,
                    "fallbackCaseMatchCount": 0,
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

    def test_draft_bundle_can_match_case_by_team_signature_when_case_ids_changed(self) -> None:
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
                    "caseId": "current_team_black_case",
                    "videoId": "video_a",
                    "teamMode": "team",
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
                manifest={
                    "cases": [
                        {
                            "caseId": "current_team_black_case",
                            "analysisResult": "analysis.json",
                            "labels": "labels.json",
                            "teamMode": "team",
                            "selectedTeamId": "team_black",
                        }
                    ]
                },
                manifest_dir=root,
                video_paths={},
                default_video_path=video_path,
                draft_bundle={
                    "schemaVersion": "team-highlight-manual-label-bundle-v1",
                    "source": "gpt_team_highlight_label_draft",
                    "humanReviewRequired": True,
                    "cases": [
                        {
                            "caseId": "old_team_black_case",
                            "teamMode": "team",
                            "selectedTeamId": "team_black",
                            "clips": [
                                {
                                    "labelId": "label_001",
                                    "predictionClipId": "clip_1",
                                    "expected": {
                                        "teamId": "team_black",
                                        "isHighlight": True,
                                        "eventType": "steal",
                                        "outcome": "steal",
                                    },
                                }
                            ],
                        }
                    ],
                },
            )

        self.assertEqual(payload["draftPrefill"]["appliedClipCount"], 1)
        self.assertEqual(payload["draftPrefill"]["skippedClipCount"], 0)
        self.assertEqual(payload["draftPrefill"]["fallbackCaseMatchCount"], 1)
        self.assertTrue(payload["cases"][0]["clips"][0]["needsLabel"])
        self.assertEqual(payload["cases"][0]["clips"][0]["expected"]["eventType"], "steal")

    def test_review_priority_marks_close_review_and_quick_check_clips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "analysis.json"
            labels_path = root / "labels.json"
            video_path = root / "source.mp4"
            video_path.write_bytes(b"fake video")
            write_json(analysis_path, {"results": {"videoId": "video_a", "clips": [{"id": "clip_1"}, {"id": "clip_2"}]}})
            write_json(
                labels_path,
                {
                    "caseId": "case_a",
                    "videoId": "video_a",
                    "selectedTeamId": "team_black",
                    "clips": [
                        {
                            "labelId": "label_001",
                            "predictionClipId": "clip_1",
                            "start": 1.0,
                            "end": 5.0,
                            "needsLabel": True,
                            "predicted": {
                                "confidence": 0.72,
                                "teamConfidence": 0.6,
                                "teamAttributionStatus": "uncertain",
                                "eventCenter": 3.0,
                            },
                            "expected": {
                                "teamId": "unclear",
                                "isHighlight": True,
                                "eventType": "three_pointer",
                                "outcome": "unclear",
                            },
                            "labelingNotes": "Uncertainty: outcome unclear; verify before launch evidence.",
                        },
                        {
                            "labelId": "label_002",
                            "predictionClipId": "clip_2",
                            "start": 7.0,
                            "end": 11.0,
                            "needsLabel": True,
                            "predicted": {
                                "confidence": 0.96,
                                "teamConfidence": 0.94,
                                "teamAttributionStatus": "matched",
                                "eventCenter": 9.0,
                            },
                            "expected": {
                                "teamId": "team_black",
                                "isHighlight": True,
                                "eventType": "made_shot",
                                "outcome": "made",
                            },
                            "labelingNotes": "Clean made shot by black jerseys.",
                        },
                    ],
                },
            )

            payload = build_review_payload(
                manifest={"cases": [{"caseId": "case_a", "analysisResult": "analysis.json", "labels": "labels.json"}]},
                manifest_dir=root,
                video_paths={},
                default_video_path=video_path,
            )
            page = render_review_page(payload, title="Review")

        self.assertEqual(payload["cases"][0]["clips"][0]["reviewPriority"]["key"], "needs_close_review")
        self.assertEqual(payload["cases"][0]["clips"][1]["reviewPriority"]["key"], "quick_check")
        self.assertEqual(
            review_page_output_metadata(Path("/tmp/review.html"), payload)["reviewPriorityCounts"],
            {
                "needs_close_review": 1,
                "quick_check": 1,
            },
        )
        self.assertIn('data-review-priority="needs_close_review"', page)
        self.assertIn('data-review-priority="quick_check"', page)
        self.assertIn("All 2", page)
        self.assertIn("Close 1", page)
        self.assertIn("Standard 0", page)
        self.assertIn("Quick 1", page)
        self.assertIn("review-priority needs-close-review", page)
        self.assertIn("review-priority quick-check", page)
        self.assertIn("No close-review clips remain", page)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

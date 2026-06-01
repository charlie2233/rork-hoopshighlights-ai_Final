import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import draft_team_highlight_manual_labels_with_gpt as draft


class DraftTeamHighlightManualLabelsWithGPTTests(unittest.TestCase):
    def test_builds_openai_context_from_candidate_keyframes_without_paths_or_urls(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-label-draft-test-") as temp_dir:
            root = Path(temp_dir)
            manifest, video_path = fixture_files(root)

            with mock.patch.object(draft.shutil, "which", return_value="/usr/bin/ffmpeg"), mock.patch.object(
                draft,
                "extract_clip_frames",
                return_value=[
                    {"role": "start", "time": 1.1, "dataUrl": "data:image/jpeg;base64,AAA"},
                    {"role": "eventCenter", "time": 3.0, "dataUrl": "data:image/jpeg;base64,BBB"},
                    {"role": "finish", "time": 4.9, "dataUrl": "data:image/jpeg;base64,CCC"},
                ],
            ):
                request = draft.build_openai_draft_request(
                    manifest=manifest,
                    manifest_dir=root,
                    video_paths={},
                    default_video_path=video_path,
                    model="gpt-test",
                    frames_per_clip=3,
                    frame_width=512,
                    jpeg_quality=5,
                    case_filter=set(),
                )

        serialized = json.dumps(draft.scrub_images_for_context_output(request))
        self.assertIn("gpt-test", serialized)
        self.assertIn("fullVideoNotProvided", serialized)
        self.assertIn("label_001", serialized)
        self.assertIn("motionScore", serialized)
        self.assertIn("teamEvidence", serialized)
        self.assertIn("data:image/jpeg;base64,<redacted>", serialized)
        self.assertNotIn(str(video_path), serialized)
        self.assertNotIn("X-Amz-Signature", serialized)
        self.assertNotIn("sourceObjectKey", serialized)
        self.assertNotIn("uploadUrl", serialized)
        self.assertNotIn("sourceUrl", serialized)

    def test_build_draft_bundle_keeps_human_review_required(self) -> None:
        label_cases = [
            {
                "caseId": "case_a",
                "clips": [
                    {
                        "labelId": "label_001",
                        "predictionClipId": "clip_1",
                        "needsLabel": True,
                        "expected": {"teamId": None, "isHighlight": None, "eventType": None, "outcome": None},
                        "labelingNotes": "",
                    }
                ],
            }
        ]
        decisions = draft.parse_decisions_response(
            {
                "output_text": json.dumps(
                    {
                        "cases": [
                            {
                                "caseId": "case_a",
                                "clips": [
                                    {
                                        "labelId": "label_001",
                                        "predictionClipId": "clip_1",
                                        "expected": {
                                            "teamId": "team_black",
                                            "isHighlight": True,
                                            "eventType": "block",
                                            "outcome": "blocked",
                                        },
                                        "confidence": 0.82,
                                        "reason": "Visible defensive challenge and blocked shot.",
                                        "uncertaintyTags": ["verify possession"],
                                    }
                                ],
                            }
                        ]
                    }
                )
            }
        )

        bundle = draft.build_draft_bundle(label_cases, decisions)

        self.assertEqual(bundle["schemaVersion"], "team-highlight-manual-label-bundle-v1")
        self.assertEqual(bundle["source"], "gpt_draft_requires_human_review")
        self.assertTrue(bundle["humanReviewRequired"])
        clip = bundle["cases"][0]["clips"][0]
        self.assertTrue(clip["needsLabel"])
        self.assertEqual(clip["expected"]["teamId"], "team_black")
        self.assertEqual(clip["expected"]["eventType"], "block")
        self.assertEqual(clip["expected"]["outcome"], "blocked")
        self.assertIn("GPT draft only", clip["labelingNotes"])

    def test_sample_times_include_start_event_finish_and_context(self) -> None:
        samples = draft.sample_times(start=10.0, end=18.0, event_center=14.0, frames_per_clip=5)

        roles = [role for role, _ in samples]
        self.assertEqual(roles[:3], ["start", "eventCenter", "finish"])
        self.assertIn("preEvent", roles)
        self.assertIn("postEvent", roles)
        self.assertEqual(len(samples), 5)

    def test_rejects_missing_or_mismatched_gpt_decisions(self) -> None:
        label_cases = [
            {
                "caseId": "case_a",
                "clips": [{"labelId": "label_001", "predictionClipId": "clip_1", "needsLabel": True}],
            }
        ]

        with self.assertRaisesRegex(ValueError, "missing case"):
            draft.build_draft_bundle(label_cases, {})
        with self.assertRaisesRegex(ValueError, "predictionClipId mismatch"):
            draft.build_draft_bundle(
                label_cases,
                {
                    "case_a": {
                        "label_001": {
                            "predictionClipId": "clip_wrong",
                            "expected": {
                                "teamId": "team_black",
                                "isHighlight": True,
                                "eventType": "steal",
                                "outcome": "steal",
                            },
                            "confidence": 0.7,
                            "reason": "test",
                            "uncertaintyTags": [],
                        }
                    }
                },
            )


def fixture_files(root: Path) -> tuple[dict, Path]:
    video_path = root / "source.mp4"
    video_path.write_bytes(b"fake")
    analysis_path = root / "case_a" / "analysis_result.json"
    labels_path = root / "case_a" / "manual_labels_template.json"
    write_json(
        analysis_path,
        {
            "uploadUrl": "https://example.test/upload?X-Amz-Signature=secret",
            "sourceObjectKey": "uploads/source.mp4",
            "results": {
                "videoId": "video_a",
                "sourceUrl": "https://example.test/source?X-Amz-Signature=secret",
                "clips": [{"id": "clip_1", "startTime": 1.0, "endTime": 5.0}],
                "detectedTeams": [{"teamId": "team_black", "colorLabel": "black", "label": "Black jerseys"}],
            },
        },
    )
    write_json(
        labels_path,
        {
            "caseId": "case_a",
            "videoId": "video_a",
            "clips": [
                {
                    "labelId": "label_001",
                    "predictionClipId": "clip_1",
                    "predictionIndex": 0,
                    "start": 1.0,
                    "end": 5.0,
                    "needsLabel": True,
                    "predicted": {
                        "label": "Block",
                        "eventCenter": 3.0,
                        "motionScore": 0.76,
                        "audioPeak": 0.41,
                        "watchabilityScore": 0.82,
                        "teamId": "team_black",
                        "teamConfidence": 0.9,
                        "teamAttributionStatus": "matched",
                        "teamEvidence": {"status": "evidence_backed", "evidenceBacked": True},
                        "sourceUrl": "https://example.test/leak",
                    },
                    "expected": {"teamId": None, "isHighlight": None, "eventType": None, "outcome": None},
                }
            ],
        },
    )
    return (
        {
            "schemaVersion": "team-highlight-accuracy-manifest-v1",
            "cases": [
                {
                    "caseId": "case_a",
                    "videoId": "video_a",
                    "teamMode": "team",
                    "selectedTeamId": "team_black",
                    "analysisResult": "case_a/analysis_result.json",
                    "labels": "case_a/manual_labels_template.json",
                }
            ],
        },
        video_path,
    )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

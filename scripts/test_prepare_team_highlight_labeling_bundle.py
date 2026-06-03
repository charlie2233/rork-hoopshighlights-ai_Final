import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts import draft_team_highlight_manual_labels_with_gpt as draft
from scripts.prepare_team_highlight_labeling_bundle import main


class PrepareTeamHighlightLabelingBundleTests(unittest.TestCase):
    def test_prepares_review_page_status_and_next_steps_with_multi_angle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis_path = root / "case_a" / "analysis_result.json"
            labels_path = root / "case_a" / "manual_labels_template.json"
            video_path = root / "source.mp4"
            angle_path = root / "baseline.mp4"
            output_dir = root / "bundle"
            video_path.write_bytes(b"fake main")
            angle_path.write_bytes(b"fake angle")
            write_json(
                analysis_path,
                {
                    "jobId": "job_123",
                    "results": {
                        "videoId": "video_a",
                        "detectedTeams": [
                            {"teamId": "team_black", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93}
                        ],
                        "clips": [{"id": "clip_1", "startTime": 1.0, "endTime": 5.0, "eventCenter": 3.0}],
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
                        {"teamId": "team_black", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93}
                    ],
                    "clips": [
                        {
                            "labelId": "label_001",
                            "predictionIndex": 0,
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
            manifest_path = root / "manifest.json"
            write_json(
                manifest_path,
                {
                    "schemaVersion": "team-highlight-accuracy-manifest-v1",
                    "cases": [
                        {
                            "caseId": "case_a",
                            "videoId": "video_a",
                            "teamMode": "team",
                            "analysisResult": "case_a/analysis_result.json",
                            "labels": "case_a/manual_labels_template.json",
                            "selectedTeamId": "team_black",
                        }
                    ],
                },
            )

            with redirect_stdout(StringIO()):
                exit_code = main_with_args(
                    [
                        "--manifest",
                        str(manifest_path),
                        "--output-dir",
                        str(output_dir),
                        "--video-path",
                        str(video_path),
                        "--video-angle",
                        f"video_a:baseline={angle_path}",
                        "--json",
                    ]
                )

            self.assertEqual(exit_code, 0)
            metadata = json.loads((output_dir / "bundle_metadata.json").read_text())
            review_page = (output_dir / "team_highlight_label_review.html").read_text()
            next_steps = (output_dir / "next_steps.md").read_text()

        self.assertEqual(metadata["schemaVersion"], "team-highlight-labeling-bundle-v1")
        self.assertEqual(metadata["status"], "incomplete")
        self.assertEqual(metadata["reviewPageMetadata"]["videoAngleCount"], 2)
        self.assertIn('id="video-video-a-main"', review_page)
        self.assertIn('id="video-video-a-baseline"', review_page)
        self.assertIn("Download launch-ready labels", review_page)
        self.assertIn("Download progress checkpoint", review_page)
        self.assertIn("apply_team_highlight_manual_labels.py", next_steps)
        self.assertIn("Commands To Save Partial Progress", next_steps)
        self.assertIn("Download progress checkpoint", next_steps)
        self.assertIn("--allow-incomplete", next_steps)
        self.assertIn("PROGRESS_BUNDLE", next_steps)
        self.assertIn("not launch evidence", next_steps)
        self.assertIn("build_launch_team_accuracy_report.py", next_steps)
        self.assertIn("submission_readiness_preflight.py", next_steps)
        self.assertIn("Next close review", next_steps)
        self.assertIn("uncertainty or weak evidence", next_steps)
        self.assertIn("Quick-check clips are faster", next_steps)
        self.assertIn("data-entry help only", next_steps)
        self.assertIn("not evidence until you watch the video and mark reviewed", next_steps)
        self.assertIn("needsLabel=false", next_steps)
        self.assertIn("reviewedByHuman=true", next_steps)
        self.assertIn("filled expected fields alone are not enough", next_steps)
        self.assertIn("J/L", next_steps)
        self.assertIn("K", next_steps)
        self.assertIn("The page auto-saves a local browser draft", next_steps)

    def test_can_generate_gpt_draft_and_prefill_review_page_from_keyframes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path, video_path = write_bundle_fixture(root)
            output_dir = root / "bundle"
            mock_response_path = root / "mock_response.json"
            write_json(
                mock_response_path,
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
                                            "confidence": 0.83,
                                            "reason": "Visible defensive play from sampled keyframes.",
                                            "uncertaintyTags": ["verify outcome"],
                                        }
                                    ],
                                }
                            ]
                        }
                    )
                },
            )

            with mock.patch.object(draft.shutil, "which", return_value="/usr/bin/ffmpeg"), mock.patch.object(
                draft,
                "extract_clip_frames",
                return_value=[
                    {"role": "start", "time": 1.1, "dataUrl": "data:image/jpeg;base64,AAA"},
                    {"role": "eventCenter", "time": 3.0, "dataUrl": "data:image/jpeg;base64,BBB"},
                    {"role": "finish", "time": 4.9, "dataUrl": "data:image/jpeg;base64,CCC"},
                ],
            ):
                with redirect_stdout(StringIO()):
                    exit_code = main_with_args(
                        [
                            "--manifest",
                            str(manifest_path),
                            "--output-dir",
                            str(output_dir),
                            "--video-path",
                            str(video_path),
                            "--draft-with-gpt",
                            "--draft-mock-response",
                            str(mock_response_path),
                            "--json",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            metadata = json.loads((output_dir / "bundle_metadata.json").read_text())
            draft_bundle = json.loads((output_dir / "gpt_draft_labels.json").read_text())
            review_page = (output_dir / "team_highlight_label_review.html").read_text()
            next_steps = (output_dir / "next_steps.md").read_text()

        self.assertEqual(metadata["gptDraft"]["source"], "gpt_draft_requires_human_review")
        self.assertEqual(metadata["gptDraft"]["clipCount"], 1)
        self.assertTrue(draft_bundle["humanReviewRequired"])
        self.assertIn("GPT draft prefilled 1 clips", review_page)
        self.assertIn("Visible defensive play", review_page)
        self.assertIn("GPT Draft", next_steps)
        self.assertIn("human review", next_steps)


def main_with_args(args: list[str]) -> int:
    import sys

    previous_argv = sys.argv
    try:
        sys.argv = ["prepare_team_highlight_labeling_bundle.py", *args]
        return main()
    finally:
        sys.argv = previous_argv


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_bundle_fixture(root: Path) -> tuple[Path, Path]:
    analysis_path = root / "case_a" / "analysis_result.json"
    labels_path = root / "case_a" / "manual_labels_template.json"
    video_path = root / "source.mp4"
    video_path.write_bytes(b"fake main")
    write_json(
        analysis_path,
        {
            "jobId": "job_123",
            "results": {
                "videoId": "video_a",
                "detectedTeams": [
                    {"teamId": "team_black", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93}
                ],
                "clips": [{"id": "clip_1", "startTime": 1.0, "endTime": 5.0, "eventCenter": 3.0}],
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
                {"teamId": "team_black", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93}
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
                        "label": "Block",
                        "eventCenter": 3.0,
                        "teamId": "team_black",
                        "teamConfidence": 0.93,
                        "teamEvidence": {"status": "evidence_backed", "evidenceBacked": True},
                    },
                    "expected": {"teamId": None, "isHighlight": None, "eventType": None, "outcome": None},
                }
            ],
        },
    )
    manifest_path = root / "manifest.json"
    write_json(
        manifest_path,
        {
            "schemaVersion": "team-highlight-accuracy-manifest-v1",
            "cases": [
                {
                    "caseId": "case_a",
                    "videoId": "video_a",
                    "teamMode": "team",
                    "analysisResult": "case_a/analysis_result.json",
                    "labels": "case_a/manual_labels_template.json",
                    "selectedTeamId": "team_black",
                }
            ],
        },
    )
    return manifest_path, video_path


if __name__ == "__main__":
    unittest.main()

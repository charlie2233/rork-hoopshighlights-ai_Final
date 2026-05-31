import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

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
        self.assertIn("apply_team_highlight_manual_labels.py", next_steps)
        self.assertIn("build_launch_team_accuracy_report.py", next_steps)
        self.assertIn("submission_readiness_preflight.py", next_steps)


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


if __name__ == "__main__":
    unittest.main()

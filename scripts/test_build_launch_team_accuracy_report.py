import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.build_launch_team_accuracy_report import build_label_status, build_launch_eval_payload, main
from scripts.evaluate_team_highlight_accuracy import evaluate_accuracy
from scripts.test_build_team_highlight_eval_payload import analysis_clip
from scripts.test_team_highlight_accuracy_eval import defensive_outcome_evidence, made_shot_evidence


class BuildLaunchTeamAccuracyReportTests(unittest.TestCase):
    def test_manifest_combines_real_analysis_label_pairs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-launch-accuracy-") as temp_dir:
            temp_path = Path(temp_dir)
            selected_analysis = temp_path / "selected_analysis.json"
            selected_labels = temp_path / "selected_labels.json"
            all_analysis = temp_path / "all_analysis.json"
            all_labels = temp_path / "all_labels.json"

            write_json(selected_analysis, selected_team_analysis_payload())
            write_json(
                selected_labels,
                {
                    "caseId": "selected_case",
                    "videoId": "video_selected",
                    "selectedTeamId": "team_dark",
                    "clips": [
                        {
                            "labelId": "made_001",
                            "predictionIndex": 0,
                            "predictionClipId": "clip_selected_made",
                            "start": 10.0,
                            "end": 14.2,
                            "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_shot", "outcome": "made"},
                        }
                    ],
                },
            )
            write_json(all_analysis, all_teams_analysis_payload())
            write_json(
                all_labels,
                {
                    "caseId": "all_case",
                    "videoId": "video_all",
                    "teamMode": "all",
                    "clips": [
                        {
                            "labelId": "steal_001",
                            "predictionIndex": 0,
                            "predictionClipId": "clip_all_steal",
                            "start": 40.0,
                            "end": 43.4,
                            "expected": {"teamId": "team_light", "isHighlight": True, "eventType": "steal", "outcome": "steal"},
                        }
                    ],
                },
            )

            payload = build_launch_eval_payload(
                manifest={
                    "cases": [
                        {"analysisResult": "selected_analysis.json", "labels": "selected_labels.json"},
                        {"analysisResult": "all_analysis.json", "labels": "all_labels.json"},
                    ]
                },
                manifest_dir=temp_path,
            )

        report = evaluate_accuracy(payload)

        self.assertEqual(payload["schemaVersion"], "team-highlight-eval-v1")
        self.assertEqual(payload["source"], "real_cloud_analysis_with_manual_labels")
        self.assertEqual(len(payload["cases"]), 2)
        self.assertEqual(payload["cases"][0]["caseId"], "selected_case")
        self.assertEqual(payload["cases"][1]["teamMode"], "all")
        self.assertEqual(report.evidence.caseCount, 2)
        self.assertEqual(report.evidence.allTeamsCaseCount, 1)

    def test_manifest_rejects_missing_analysis_or_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing analysisResult"):
            build_launch_eval_payload(manifest={"cases": [{"labels": "labels.json"}]}, manifest_dir=Path.cwd())

        with self.assertRaisesRegex(ValueError, "missing labels"):
            build_launch_eval_payload(manifest={"cases": [{"analysisResult": "analysis.json"}]}, manifest_dir=Path.cwd())

    def test_cli_writes_eval_and_report_outputs_even_when_thresholds_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-launch-accuracy-cli-") as temp_dir:
            temp_path = Path(temp_dir)
            analysis_path = temp_path / "analysis.json"
            labels_path = temp_path / "labels.json"
            manifest_path = temp_path / "manifest.json"
            eval_output = temp_path / "out" / "team_highlight_eval.json"
            report_output = temp_path / "out" / "team_highlight_accuracy_report.json"

            write_json(analysis_path, selected_team_analysis_payload())
            write_json(
                labels_path,
                {
                    "caseId": "selected_case",
                    "videoId": "video_selected",
                    "selectedTeamId": "team_dark",
                    "clips": [
                        {
                            "labelId": "made_001",
                            "predictionIndex": 0,
                            "predictionClipId": "clip_selected_made",
                            "start": 10.0,
                            "end": 14.2,
                            "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "made_shot", "outcome": "made"},
                        }
                    ],
                },
            )
            write_json(manifest_path, {"cases": [{"analysisResult": "analysis.json", "labels": "labels.json"}]})

            import sys

            old_argv = sys.argv
            try:
                sys.argv = [
                    "build_launch_team_accuracy_report.py",
                    "--manifest",
                    str(manifest_path),
                    "--eval-output",
                    str(eval_output),
                    "--report-output",
                    str(report_output),
                    "--json",
                ]
                with redirect_stdout(StringIO()):
                    exit_code = main()
            finally:
                sys.argv = old_argv

            self.assertEqual(exit_code, 1)
            self.assertTrue(eval_output.exists())
            self.assertTrue(report_output.exists())
            self.assertEqual(json.loads(eval_output.read_text(encoding="utf-8"))["source"], "real_cloud_analysis_with_manual_labels")
            self.assertEqual(json.loads(report_output.read_text(encoding="utf-8"))["status"], "fail")

    def test_label_status_summarizes_every_incomplete_manifest_case(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hoopclips-launch-label-status-") as temp_dir:
            temp_path = Path(temp_dir)
            selected_analysis = temp_path / "selected_analysis.json"
            selected_labels = temp_path / "selected_labels.json"
            all_analysis = temp_path / "all_analysis.json"
            all_labels = temp_path / "all_labels.json"
            write_json(selected_analysis, selected_team_analysis_payload())
            write_json(all_analysis, all_teams_analysis_payload())
            write_json(
                selected_labels,
                {
                    "caseId": "selected_case",
                    "clips": [
                        {
                            "labelId": "needs_review",
                            "needsLabel": True,
                            "expected": {"teamId": None, "isHighlight": None, "eventType": None, "outcome": None},
                        },
                        {
                            "labelId": "complete_negative",
                            "needsLabel": False,
                            "reviewedByHuman": True,
                            "expected": {"teamId": "team_light", "isHighlight": "false", "eventType": "bad_window", "outcome": "bad_window"},
                        },
                    ],
                },
            )
            write_json(
                all_labels,
                {
                    "caseId": "all_case",
                    "teamMode": "all",
                    "clips": [
                        {
                            "labelId": "missing_outcome",
                            "needsLabel": False,
                            "reviewedByHuman": True,
                            "expected": {"teamId": "team_dark", "isHighlight": True, "eventType": "steal"},
                        }
                    ],
                },
            )

            status = build_label_status(
                manifest={
                    "cases": [
                        {"analysisResult": "selected_analysis.json", "labels": "selected_labels.json"},
                        {"analysisResult": "all_analysis.json", "labels": "all_labels.json"},
                    ]
                },
                manifest_dir=temp_path,
            )

        self.assertEqual(status["schemaVersion"], "team-highlight-label-status-v1")
        self.assertEqual(status["status"], "incomplete")
        self.assertEqual(status["caseCount"], 2)
        self.assertEqual(status["clipCount"], 3)
        self.assertEqual(status["completeClipCount"], 0)
        self.assertEqual(status["incompleteClipCount"], 3)
        self.assertEqual(status["missingFieldCounts"]["needsLabel=false"], 2)
        self.assertEqual(status["missingFieldCounts"]["reviewedByHuman=true"], 2)
        self.assertEqual(status["missingFieldCounts"]["expected.outcome"], 2)
        self.assertEqual(status["cases"][0]["incompleteExamples"][0]["labelId"], "needs_review")


def selected_team_analysis_payload() -> dict:
    return {
        "jobId": "analysis_selected_001",
        "teamScanJobId": "scan_selected_001",
        "results": {
            "teamSelection": {"mode": "team", "teamId": "team_dark", "colorLabel": "black", "confidenceThreshold": 0.85},
            "detectedTeams": [
                {"teamId": "team_dark", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93},
                {"teamId": "team_light", "label": "White jerseys", "colorLabel": "white", "confidence": 0.91},
            ],
            "clips": [
                {**analysis_clip(10.0, 14.2, "Made Shot", True, "team_dark", 0.94), **made_shot_evidence(), "id": "clip_selected_made"},
            ],
        },
    }


def all_teams_analysis_payload() -> dict:
    return {
        "jobId": "analysis_all_001",
        "teamScanJobId": "scan_all_001",
        "results": {
            "teamSelection": {"mode": "all"},
            "detectedTeams": [
                {"teamId": "team_dark", "label": "Black jerseys", "colorLabel": "black", "confidence": 0.93},
                {"teamId": "team_light", "label": "White jerseys", "colorLabel": "white", "confidence": 0.91},
            ],
            "clips": [
                {
                    **analysis_clip(40.0, 43.4, "Steal", True, "team_light", 0.92),
                    **defensive_outcome_evidence("steal"),
                    "id": "clip_all_steal",
                },
            ],
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_team_highlight_accuracy_gate import build_accuracy_gate_summary


class SummarizeTeamHighlightAccuracyGateTests(unittest.TestCase):
    def test_missing_artifacts_dir_reports_actionable_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "missing"

            summary = build_accuracy_gate_summary(artifacts_dir)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("artifacts_dir_missing", summary["blockers"])
        self.assertIn("no_label_status_files", summary["blockers"])
        self.assertIn("no_accuracy_reports", summary["blockers"])
        self.assertTrue(any("restore" in action for action in summary["nextActions"]))

    def test_incomplete_label_bundle_and_failing_report_remain_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            bundle_dir = artifacts_dir / "team_highlight_labeling_bundle_current"
            bundle_dir.mkdir()
            write_json(
                bundle_dir / "label_status.json",
                {
                    "status": "incomplete",
                    "launchEvidenceEligible": False,
                    "caseCount": 2,
                    "clipCount": 18,
                    "completeClipCount": 0,
                    "incompleteClipCount": 18,
                    "missingFieldCounts": {"reviewedByHuman=true": 18},
                },
            )
            write_json(
                bundle_dir / "team_highlight_accuracy_report.json",
                {
                    "status": "fail",
                    "metrics": {
                        "caseCount": 1,
                        "clipCount": 43,
                        "selectedTeamPrecision": 1.0,
                        "highlightPrecision": 0.1163,
                        "shotOutcomeEvidenceQuality": 0.0,
                    },
                    "evidence": {
                        "inputSource": "real_cloud_analysis_with_manual_labels",
                        "distinctVideoCount": 1,
                    },
                    "failures": [
                        "highlightPrecision 0.116 is below required 0.850.",
                        "caseCoverage 1 is below required 2.",
                    ],
                },
            )

            summary = build_accuracy_gate_summary(artifacts_dir)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("manual_labels_incomplete", summary["blockers"])
        self.assertIn("no_passing_launch_grade_report", summary["blockers"])
        self.assertEqual(summary["bestReviewBundle"]["incompleteClipCount"], 18)
        self.assertEqual(summary["bestAccuracyReport"]["failureCount"], 2)
        self.assertTrue(any("18 clips remaining" in action for action in summary["nextActions"]))

    def test_complete_labels_and_passing_report_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            bundle_dir = artifacts_dir / "team_highlight_labeling_bundle_ready"
            bundle_dir.mkdir()
            write_json(
                bundle_dir / "label_status.json",
                {
                    "status": "complete",
                    "launchEvidenceEligible": True,
                    "caseCount": 2,
                    "clipCount": 18,
                    "completeClipCount": 18,
                    "incompleteClipCount": 0,
                    "missingFieldCounts": {},
                },
            )
            write_json(
                bundle_dir / "team_highlight_accuracy_report.json",
                {
                    "status": "pass",
                    "metrics": {
                        "caseCount": 2,
                        "clipCount": 18,
                        "selectedTeamPrecision": 0.9,
                        "highlightPrecision": 0.9,
                        "shotOutcomeEvidenceQuality": 0.9,
                    },
                    "evidence": {
                        "inputSource": "real_cloud_analysis_with_manual_labels",
                        "distinctVideoCount": 2,
                    },
                    "failures": [],
                },
            )

            summary = build_accuracy_gate_summary(artifacts_dir)

        self.assertEqual(summary["status"], "pass")
        self.assertEqual(summary["blockers"], [])
        self.assertIn("--team-accuracy-report", summary["nextActions"][0])


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

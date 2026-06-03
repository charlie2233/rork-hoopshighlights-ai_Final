import json
import tempfile
import unittest
from pathlib import Path

from scripts.collect_launch_evidence_snapshot import (
    label_status_snapshot,
    latest_for_head,
    latest_success_for_head,
)


class CollectLaunchEvidenceSnapshotTest(unittest.TestCase):
    def test_label_status_uses_generated_status_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            label_status = repo_root / "artifacts/team_highlight_labeling_bundle/label_status.json"
            label_status.parent.mkdir(parents=True)
            label_status.write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "clipCount": 54,
                        "completeClipCount": 54,
                        "incompleteClipCount": 0,
                        "launchEvidenceEligible": True,
                        "missingFieldCounts": {},
                    }
                )
            )
            summary = repo_root / "docs/launch_evidence/label_status_summary_2026-06-03.json"
            summary.parent.mkdir(parents=True)
            summary.write_text(
                json.dumps(
                    {
                        "status": "incomplete",
                        "clipCount": 54,
                        "completeClipCount": 0,
                        "incompleteClipCount": 54,
                        "launchEvidenceEligible": False,
                        "missingFieldCounts": {"reviewedByHuman=true": 54},
                    }
                )
            )

            snapshot = label_status_snapshot(repo_root, Path("artifacts/team_highlight_labeling_bundle/label_status.json"), summary)

            self.assertTrue(snapshot["exists"])
            self.assertEqual(snapshot["source"], "generatedStatus")
            self.assertEqual(snapshot["status"], "complete")
            self.assertEqual(snapshot["completeClipCount"], 54)
            self.assertTrue(snapshot["launchEvidenceEligible"])

    def test_label_status_falls_back_to_tracked_summary_when_generated_status_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            summary = repo_root / "docs/launch_evidence/label_status_summary_2026-06-03.json"
            summary.parent.mkdir(parents=True)
            summary.write_text(
                json.dumps(
                    {
                        "generatedAt": "2026-06-03T22:04:06Z",
                        "sourceKind": "tracked_non_secret_summary",
                        "status": "incomplete",
                        "clipCount": 54,
                        "completeClipCount": 0,
                        "incompleteClipCount": 54,
                        "launchEvidenceEligible": False,
                        "missingFieldCounts": {"reviewedByHuman=true": 54},
                        "notLaunchEvidence": True,
                    }
                )
            )

            snapshot = label_status_snapshot(repo_root, Path("artifacts/team_highlight_labeling_bundle/label_status.json"), summary)

            self.assertFalse(snapshot["exists"])
            self.assertEqual(snapshot["source"], "trackedSummary")
            self.assertEqual(snapshot["summaryPath"], str(summary))
            self.assertEqual(snapshot["summaryGeneratedAt"], "2026-06-03T22:04:06Z")
            self.assertEqual(snapshot["status"], "incomplete")
            self.assertEqual(snapshot["completeClipCount"], 0)
            self.assertEqual(snapshot["clipCount"], 54)
            self.assertFalse(snapshot["launchEvidenceEligible"])
            self.assertTrue(snapshot["notLaunchEvidence"])

    def test_label_status_reports_missing_when_generated_status_and_summary_are_absent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            summary = Path("docs/launch_evidence/label_status_summary_2026-06-03.json")

            snapshot = label_status_snapshot(repo_root, Path("artifacts/team_highlight_labeling_bundle/label_status.json"), summary)

            self.assertFalse(snapshot["exists"])
            self.assertEqual(snapshot["source"], "missing")
            self.assertFalse(snapshot["summaryExists"])
            self.assertEqual(snapshot["status"], "missing")
            self.assertIsNone(snapshot["clipCount"])
            self.assertFalse(snapshot["launchEvidenceEligible"])

    def test_latest_for_head_reports_in_progress_run_while_success_requires_completed_success(self):
        head = "abcdef123456"
        runs = [
            {
                "workflowName": "Cloud Edit Deploy Preflight",
                "headSha": head,
                "status": "in_progress",
                "conclusion": None,
                "databaseId": 1,
            },
            {
                "workflowName": "Cloud Edit Deploy Preflight",
                "headSha": "oldhead",
                "status": "completed",
                "conclusion": "success",
                "databaseId": 2,
            },
        ]

        latest = latest_for_head(runs, "Cloud Edit Deploy Preflight", head)
        success = latest_success_for_head(runs, "Cloud Edit Deploy Preflight", head)

        self.assertEqual(latest["databaseId"], 1)
        self.assertIsNone(success)

    def test_latest_success_for_head_returns_completed_success_for_matching_head(self):
        head = "abcdef123456"
        runs = [
            {
                "workflowName": "iOS Internal TestFlight Upload",
                "headSha": head,
                "status": "completed",
                "conclusion": "failure",
                "databaseId": 1,
            },
            {
                "workflowName": "iOS Internal TestFlight Upload",
                "headSha": head,
                "status": "completed",
                "conclusion": "success",
                "databaseId": 2,
            },
        ]

        latest = latest_for_head(runs, "iOS Internal TestFlight Upload", head)
        success = latest_success_for_head(runs, "iOS Internal TestFlight Upload", head)

        self.assertEqual(latest["databaseId"], 1)
        self.assertEqual(success["databaseId"], 2)


if __name__ == "__main__":
    unittest.main()

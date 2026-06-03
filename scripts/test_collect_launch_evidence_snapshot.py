import json
import tempfile
import unittest
from pathlib import Path

from scripts.collect_launch_evidence_snapshot import (
    label_review_guidance,
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

    def test_label_review_guidance_turns_incomplete_summary_into_reviewer_actions(self):
        guidance = label_review_guidance(
            {
                "source": "trackedSummary",
                "status": "incomplete",
                "clipCount": 54,
                "completeClipCount": 0,
                "incompleteClipCount": 54,
                "launchEvidenceEligible": False,
                "missingFieldCounts": {
                    "expected.eventType": 54,
                    "expected.isHighlight": 54,
                    "expected.outcome": 54,
                    "expected.teamId": 54,
                    "needsLabel=false": 54,
                    "reviewedByHuman=true": 54,
                },
            }
        )

        self.assertEqual(guidance["status"], "human_review_required")
        self.assertFalse(guidance["sourceIsLaunchEvidence"])
        self.assertEqual(guidance["reviewedClipCount"], 0)
        self.assertEqual(guidance["remainingClipCount"], 54)
        self.assertIn("expected.outcome", guidance["missingRequiredFields"])
        self.assertIn("reviewedByHuman=true", guidance["missingRequiredFields"])
        self.assertIn("Complete human review", " ".join(guidance["nextActions"]))

    def test_label_review_guidance_marks_generated_complete_status_as_launch_evidence(self):
        guidance = label_review_guidance(
            {
                "source": "generatedStatus",
                "status": "complete",
                "clipCount": 54,
                "completeClipCount": 54,
                "incompleteClipCount": 0,
                "launchEvidenceEligible": True,
                "missingFieldCounts": {},
            }
        )

        self.assertEqual(guidance["status"], "complete")
        self.assertTrue(guidance["sourceIsLaunchEvidence"])
        self.assertEqual(guidance["remainingClipCount"], 0)
        self.assertEqual(guidance["missingRequiredFields"], [])
        self.assertEqual(guidance["nextActions"], [])


if __name__ == "__main__":
    unittest.main()

class LaunchBlockerSummaryTest(unittest.TestCase):
    def test_launch_blockers_list_all_open_external_gates(self):
        from scripts.collect_launch_evidence_snapshot import launch_blockers

        blockers = launch_blockers(
            production_variables={"missingRequired": ["HOOPS_CLOUD_ANALYSIS_BASE_URL", "HOOPS_CLOUD_EDIT_BASE_URL"]},
            latest_release={"databaseId": 26884199422, "status": "completed", "conclusion": "failure"},
            labels={"status": "incomplete", "completeClipCount": 0, "clipCount": 54, "launchEvidenceEligible": False},
        )

        self.assertEqual(len(blockers), 5)
        self.assertIn("HOOPS_CLOUD_ANALYSIS_BASE_URL", blockers[0])
        self.assertIn("26884199422", blockers[1])
        self.assertIn("0/54", blockers[2])
        self.assertIn("Signed App Store Connect archive/upload", blockers[3])
        self.assertIn("Installed trusted-device TestFlight smoke", blockers[4])

    def test_launch_blockers_empty_when_all_external_gates_are_proven(self):
        from scripts.collect_launch_evidence_snapshot import launch_blockers

        blockers = launch_blockers(
            production_variables={"missingRequired": []},
            latest_release={"databaseId": 1, "status": "completed", "conclusion": "success"},
            labels={"status": "complete", "completeClipCount": 54, "clipCount": 54, "launchEvidenceEligible": True},
            signed_archive_upload_proven=True,
            installed_testflight_smoke_proven=True,
        )

        self.assertEqual(blockers, [])

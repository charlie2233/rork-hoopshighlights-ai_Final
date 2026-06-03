import json
import tempfile
import unittest
from pathlib import Path

from scripts.collect_launch_evidence_snapshot import (
    cloud_backend_readiness_handoff,
    ios_usability_and_import_handoff,
    label_review_guidance,
    label_status_snapshot,
    latest_for_head,
    latest_success_for_head,
    production_cloud_url_handoff,
    release_preflight_for_head,
    testflight_proof_handoff,
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

    def test_production_cloud_url_handoff_lists_release_owner_actions_without_secret_values(self):
        handoff = production_cloud_url_handoff(
            {"missingRequired": ["HOOPS_CLOUD_ANALYSIS_BASE_URL", "HOOPS_CLOUD_EDIT_BASE_URL"]},
            "codex/test-branch",
        )

        self.assertEqual(handoff["status"], "blocked")
        self.assertTrue(handoff["requiresReleaseOwnerConfirmation"])
        self.assertTrue(handoff["secretSafe"])
        self.assertIn("HOOPS_CLOUD_ANALYSIS_BASE_URL", handoff["missingVariables"])
        self.assertIn("HOOPS_CLOUD_EDIT_BASE_URL", handoff["missingVariables"])
        self.assertIn("staging", handoff["candidateInternalTestFlightWorkerUrl"])
        self.assertIn("URL query strings", handoff["doNotReturn"])
        self.assertIn("--body '<confirmed-analysis-base-url>'", "\n".join(handoff["commandsAfterConfirmation"]))
        self.assertIn("--ref codex/test-branch", "\n".join(handoff["commandsAfterConfirmation"]))
        self.assertIn("Release Secrets Preflight passes", "\n".join(handoff["proofRequiredAfterSetting"]))
        self.assertNotIn("ghp_", json.dumps(handoff))

    def test_production_cloud_url_handoff_marks_configured_when_urls_are_present(self):
        handoff = production_cloud_url_handoff({"missingRequired": []}, "codex/test-branch")

        self.assertEqual(handoff["status"], "configured")
        self.assertFalse(handoff["requiresReleaseOwnerConfirmation"])
        self.assertEqual(handoff["missingVariables"], [])

    def test_testflight_proof_handoff_keeps_codecheck_from_counting_as_launch_evidence(self):
        handoff = testflight_proof_handoff("codex/test-branch")

        self.assertEqual(handoff["status"], "blocked")
        self.assertEqual(handoff["signedArchiveUpload"]["status"], "not_proven")
        self.assertEqual(handoff["installedTrustedDeviceSmoke"]["status"], "not_proven")
        self.assertIn("operation=upload", handoff["signedArchiveUpload"]["commandAfterReleaseGatesPass"])
        self.assertIn("--ref codex/test-branch", handoff["signedArchiveUpload"]["commandAfterReleaseGatesPass"])
        self.assertTrue(handoff["codecheckIsNotLaunchEvidence"])
        self.assertIn("operation=codecheck", handoff["doNotClaimFrom"])
        self.assertIn("skipped archive job", handoff["doNotClaimFrom"])
        self.assertIn("App Store Connect private key contents", handoff["doNotReturn"])
        self.assertIn("trusted internal tester", " ".join(handoff["installedTrustedDeviceSmoke"]["requiredProof"]))

    def test_testflight_proof_handoff_can_represent_completed_external_proof(self):
        handoff = testflight_proof_handoff(
            "codex/test-branch",
            signed_archive_upload_proven=True,
            installed_testflight_smoke_proven=True,
        )

        self.assertEqual(handoff["status"], "complete")
        self.assertEqual(handoff["signedArchiveUpload"]["status"], "proven")
        self.assertEqual(handoff["installedTrustedDeviceSmoke"]["status"], "proven")

    def test_cloud_backend_readiness_handoff_keeps_cloud_gate_blocked_without_live_proof(self):
        handoff = cloud_backend_readiness_handoff(
            {"missingRequired": ["HOOPS_CLOUD_ANALYSIS_BASE_URL", "HOOPS_CLOUD_EDIT_BASE_URL"]},
            release_preflight_passing=False,
            cloud_latest_run={"databaseId": 1, "status": "completed", "conclusion": "success"},
            cloud_success_run={"databaseId": 1, "status": "completed", "conclusion": "success"},
        )

        self.assertEqual(handoff["status"], "blocked")
        self.assertTrue(handoff["cloudOwnedPathRequired"])
        self.assertIn("analysis", handoff["backendOwns"])
        self.assertIn("rendering", handoff["backendOwns"])
        self.assertIn("upload", handoff["iosScope"])
        self.assertEqual(handoff["productionCloudUrls"]["status"], "blocked")
        self.assertEqual(handoff["releaseSecretsPreflight"]["status"], "blocked")
        self.assertEqual(handoff["cloudDeployPreflight"]["status"], "proven_current_head")
        self.assertEqual(handoff["liveBackendStatus"]["status"], "not_proven")
        self.assertEqual(handoff["renderReliability"]["status"], "not_proven")
        self.assertEqual(handoff["jobStateReporting"]["status"], "not_proven")
        self.assertIn("green iOS codecheck alone", handoff["doNotClaimFrom"])
        self.assertIn("local AVFoundation rendering", handoff["doNotClaimFrom"])
        self.assertIn("Record cloud render reliability proof", " ".join(handoff["nextActions"]))

    def test_cloud_backend_readiness_handoff_can_represent_complete_cloud_backend_proof(self):
        handoff = cloud_backend_readiness_handoff(
            {"missingRequired": []},
            release_preflight_passing=True,
            cloud_latest_run={"databaseId": 1, "status": "completed", "conclusion": "success"},
            cloud_success_run={"databaseId": 1, "status": "completed", "conclusion": "success"},
            live_backend_status_proven=True,
            render_reliability_proven=True,
            job_state_reporting_proven=True,
        )

        self.assertEqual(handoff["status"], "complete")
        self.assertEqual(handoff["productionCloudUrls"]["status"], "configured")
        self.assertEqual(handoff["releaseSecretsPreflight"]["status"], "passing")
        self.assertEqual(handoff["liveBackendStatus"]["status"], "proven")
        self.assertEqual(handoff["renderReliability"]["status"], "proven")
        self.assertEqual(handoff["jobStateReporting"]["status"], "proven")
        self.assertEqual(handoff["nextActions"], [])

    def test_ios_usability_and_import_handoff_requires_installed_device_proof(self):
        handoff = ios_usability_and_import_handoff()

        self.assertEqual(handoff["status"], "blocked")
        self.assertTrue(handoff["installedTestFlightSmokeRequired"])
        self.assertIn("Photos/file import", handoff["iosScope"])
        self.assertIn("history resume/source/saved reel/share/delete", handoff["iosScope"])
        self.assertIn("export.aiEdit.workReceipt", handoff["stableAccessibilityIdsToSmoke"])
        self.assertIn("backend-owned", handoff["cloudBoundary"])
        self.assertEqual(handoff["requiredProof"]["importHistory"]["status"], "not_proven")
        self.assertEqual(handoff["requiredProof"]["readableControls"]["status"], "not_proven")
        self.assertEqual(handoff["requiredProof"]["exportShare"]["status"], "not_proven")
        self.assertIn("iOS codecheck alone", handoff["doNotClaimFrom"])
        self.assertIn("simulator-only UI smoke", handoff["doNotClaimFrom"])
        self.assertIn("Run trusted-device installed TestFlight smoke", " ".join(handoff["nextActions"]))

    def test_ios_usability_and_import_handoff_can_represent_completed_installed_smoke(self):
        handoff = ios_usability_and_import_handoff(
            installed_testflight_smoke_proven=True,
            import_history_proven=True,
            readable_controls_proven=True,
            export_share_proven=True,
        )

        self.assertEqual(handoff["status"], "complete")
        self.assertEqual(handoff["requiredProof"]["importHistory"]["status"], "proven")
        self.assertEqual(handoff["requiredProof"]["readableControls"]["status"], "proven")
        self.assertEqual(handoff["requiredProof"]["exportShare"]["status"], "proven")
        self.assertEqual(handoff["nextActions"], [])


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

        release_run = {"databaseId": 1, "status": "completed", "conclusion": "success", "headSha": "abcdef123"}
        blockers = launch_blockers(
            production_variables={"missingRequired": []},
            latest_release=release_run,
            labels={"status": "complete", "completeClipCount": 54, "clipCount": 54, "launchEvidenceEligible": True},
            current_head_release=release_run,
            signed_archive_upload_proven=True,
            installed_testflight_smoke_proven=True,
        )

        self.assertEqual(blockers, [])

    def test_launch_blockers_require_release_preflight_on_current_head(self):
        from scripts.collect_launch_evidence_snapshot import launch_blockers

        blockers = launch_blockers(
            production_variables={"missingRequired": []},
            latest_release={"databaseId": 10, "status": "completed", "conclusion": "success", "headSha": "oldhead123"},
            labels={"status": "complete", "completeClipCount": 54, "clipCount": 54, "launchEvidenceEligible": True},
            current_head_release=None,
            signed_archive_upload_proven=True,
            installed_testflight_smoke_proven=True,
        )

        self.assertEqual(len(blockers), 1)
        self.assertIn("no current-head run evidence", blockers[0])
        self.assertIn("oldhead", blockers[0])

    def test_release_preflight_for_head_selects_current_head_run(self):
        head = "abcdef123456"
        runs = [
            {"databaseId": 1, "headSha": "oldhead", "status": "completed", "conclusion": "success"},
            {"databaseId": 2, "headSha": head, "status": "completed", "conclusion": "failure"},
        ]

        selected = release_preflight_for_head(runs, head)

        self.assertEqual(selected["databaseId"], 2)

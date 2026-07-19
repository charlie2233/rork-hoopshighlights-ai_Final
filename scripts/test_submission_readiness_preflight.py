import os
import json
import plistlib
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError
from unittest.mock import patch

from scripts.evaluate_team_highlight_accuracy import AccuracyThresholds
from scripts.submission_readiness_preflight import (
    BLOCKER_DOCS,
    Collector,
    EXPECTED_IOS_BUNDLE_ID,
    EXPECTED_IOS_BUILD_NUMBER,
    EXPECTED_IOS_MARKETING_VERSION,
    GithubEnvironmentNameLookup,
    REQUIRED_IOS_UPLOAD_SECRET_INPUTS,
    REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS,
    REQUIRED_PRODUCTION_CLOUD_URL_VARIABLE_INPUTS,
    check_production_cloud_url_inputs,
    check_upload_artifact,
    check_bundle_id_references,
    check_blocker_docs,
    check_ci_deploy_inputs,
    check_connected_ios_device,
    check_github_workflow_runs,
    check_installed_testflight_build,
    check_ios_signing,
    check_ios_upload_inputs,
    check_live_editing_version,
    check_live_worker_version,
    check_secret_gated_deploy_preflight,
    check_team_highlight_accuracy_report,
    has_failures,
    ios_device_state_is_smoke_ready,
    parse_devicectl_devices,
    redacted_endpoint_label,
    run_checks,
    _gh_stderr_detail,
)


class SubmissionReadinessPreflightTests(unittest.TestCase):
    def test_ready_fixture_passes_without_printing_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            archive_path = create_ready_fixture(repo_root)
            team_accuracy_report_path = repo_root / "artifacts/team_accuracy_report.json"
            write_json(team_accuracy_report_path, launch_grade_team_accuracy_report())

            with patch(
                "scripts.submission_readiness_preflight.run_backend_config_checks",
                return_value=[SimpleNamespace(status="pass")],
            ), patch(
                "scripts.submission_readiness_preflight.check_git_state",
                side_effect=lambda _repo_root, collector: collector.pass_("git tracked changes", "repo", "No tracked working-tree changes."),
            ), patch(
                "scripts.submission_readiness_preflight.check_live_worker_version",
                side_effect=lambda _url, collector, skip_live, timeout_seconds: collector.pass_(
                    "live worker feature flags",
                    "staging-worker/v1/editing/version",
                    "Worker returned non-secret AI Edit kill-switch state.",
                ),
            ), patch(
                "scripts.submission_readiness_preflight.check_connected_ios_device",
                side_effect=lambda collector: collector.pass_(
                    "connected ios device",
                    "xcrun devicectl",
                    "1 available iPhone device(s) detected for TestFlight smoke.",
                ),
            ), patch(
                "scripts.submission_readiness_preflight.check_installed_testflight_build",
                side_effect=lambda _repo_root, collector: collector.pass_(
                    "installed TestFlight build",
                    "scripts/check_installed_testflight_build.py",
                    "Installed app is atrak.charlie.hoopsclips 1.0.0 (52).",
                ),
            ), patch(
                "scripts.submission_readiness_preflight.check_live_editing_version",
                side_effect=lambda _url, collector, repo_root, skip_live, timeout_seconds: collector.pass_(
                    "live editing feature flags",
                    "editing-staging/version",
                    "Direct editing service returned non-secret AI Edit kill-switch state.",
                ),
            ), patch(
                "scripts.submission_readiness_preflight.check_github_workflow_runs",
                side_effect=lambda _repo_root, collector: collector.pass_(
                    "github workflow status",
                    "GitHub Actions",
                    "Required main-branch workflow runs are green.",
                ),
            ), patch(
                "scripts.submission_readiness_preflight.check_secret_gated_deploy_preflight",
                side_effect=lambda _repo_root, collector: collector.pass_(
                    "secret-gated deploy preflight",
                    "Cloud Edit Deploy Preflight",
                    "Current-commit workflow_dispatch deploy preflight completed successfully with provider-auth job proof.",
                ),
            ), patch.dict(
                os.environ,
                {
                    "CLOUDFLARE_API_TOKEN": "present",
                    "GCP_WORKLOAD_IDENTITY_PROVIDER": "present",
                    "GCP_DEPLOY_SERVICE_ACCOUNT": "present",
                    "GCP_PROJECT_ID": "present",
                    "GCP_REGION": "present",
                    **{name: "present" for name in REQUIRED_PRODUCTION_CLOUD_URL_VARIABLE_INPUTS},
                    **{name: "present" for name in REQUIRED_IOS_UPLOAD_SECRET_INPUTS},
                    **{name: "present" for name in REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS},
                },
                clear=True,
            ):
                findings = run_checks(repo_root, archive_path=archive_path, team_accuracy_report_path=team_accuracy_report_path)

            self.assertFalse(has_failures(findings), "\n".join(f"{item.check}: {item.detail}" for item in findings if item.status == "fail"))
            details = "\n".join(item.detail for item in findings)
            self.assertNotIn("TEAM123456", details)
            self.assertNotIn("K99RADPB9G", details)

    def test_team_accuracy_report_is_required_for_submission_readiness(self) -> None:
        collector = Collector()

        check_team_highlight_accuracy_report(Path.cwd(), collector, None)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("--team-accuracy-report", collector.findings[0].detail)

    def test_missing_team_accuracy_report_points_to_existing_labeling_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            create_labeling_bundle_fixture(repo_root, complete_clip_count=7, incomplete_clip_count=47)
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, None)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("7/54 clips complete", detail)
        self.assertIn("47 remaining", detail)
        self.assertIn("team_highlight_label_review.html", detail)
        self.assertIn("next_steps.md", detail)
        self.assertIn("GPT draft prefilled 54 clip(s)", detail)
        self.assertIn("49 close-review", detail)
        self.assertIn("Launch label gate requires", detail)
        self.assertIn("expected.teamId", detail)
        self.assertIn("expected.isHighlight", detail)
        self.assertIn("expected.eventType", detail)
        self.assertIn("expected.outcome", detail)
        self.assertIn("needsLabel=false", detail)
        self.assertIn("reviewedByHuman=true", detail)
        self.assertIn("current status still reports missing", detail)
        self.assertIn("GPT draft labels do not count", detail)
        self.assertNotIn("Labeling bundle looks stale", detail)

    def test_missing_team_accuracy_report_can_point_to_custom_labeling_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            bundle_dir = Path("artifacts/team_highlight_labeling_bundle_launch_current_reduced")
            create_labeling_bundle_fixture(
                repo_root,
                complete_clip_count=0,
                incomplete_clip_count=18,
                clip_count=18,
                bundle_dir=bundle_dir,
            )
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, None, labeling_bundle_dir=bundle_dir)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("0/18 clips complete", detail)
        self.assertIn("18 remaining", detail)
        self.assertIn("team_highlight_labeling_bundle_launch_current_reduced/team_highlight_label_review.html", detail)
        self.assertIn("team_highlight_labeling_bundle_launch_current_reduced/label_status.json", detail)
        self.assertNotIn("0/54 clips complete", detail)

    def test_missing_team_accuracy_report_warns_when_labeling_bundle_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            manifest_path = repo_root / "artifacts/team_highlight_accuracy_manifest.json"
            write_json(manifest_path, {"schemaVersion": "team-highlight-accuracy-manifest-v1", "cases": []})
            bundle_dir = repo_root / "artifacts/team_highlight_labeling_bundle"
            write_json(
                bundle_dir / "label_status.json",
                {
                    "schemaVersion": "team-highlight-label-status-v1",
                    "status": "incomplete",
                    "clipCount": 54,
                    "completeClipCount": 0,
                    "incompleteClipCount": 54,
                },
            )
            write_json(
                bundle_dir / "bundle_metadata.json",
                {
                    "schemaVersion": "team-highlight-labeling-bundle-v1",
                    "reviewPage": "artifacts/team_highlight_labeling_bundle/team_highlight_label_review.html",
                    "labelStatus": "artifacts/team_highlight_labeling_bundle/label_status.json",
                    "clipCount": 54,
                    "completeClipCount": 0,
                    "incompleteClipCount": 54,
                    "gptDraft": {
                        "path": "artifacts/team_highlight_labeling_bundle/gpt_draft_labels.json",
                    },
                },
            )
            (bundle_dir / "team_highlight_label_review.html").write_text("Next incomplete\n", encoding="utf-8")
            (bundle_dir / "next_steps.md").write_text("Use the review page.\n", encoding="utf-8")
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, None)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("Labeling bundle looks stale or incomplete", detail)
        self.assertIn("video scrub shortcuts", detail)
        self.assertIn("scrub shortcut instruction", detail)
        self.assertIn("GPT draft data-entry-only warning", detail)
        self.assertIn("GPT draft human-review evidence warning", detail)
        self.assertIn("prepare_team_highlight_labeling_bundle.py", detail)
        self.assertIn("team_highlight_accuracy_manifest.json", detail)
        self.assertIn("--video-path", detail)
        self.assertIn("/absolute/path/to/source.mp4", detail)
        self.assertIn("--draft-bundle", detail)
        self.assertIn("gpt_draft_labels.json", detail)

    def test_missing_team_accuracy_report_points_to_manifest_when_bundle_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            manifest_path = repo_root / "artifacts/team_highlight_accuracy_manifest.json"
            write_json(manifest_path, {"schemaVersion": "team-highlight-accuracy-manifest-v1", "cases": []})
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, None)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("team_highlight_accuracy_manifest.json", detail)
        self.assertIn("prepare_team_highlight_labeling_bundle.py", detail)

    def test_team_accuracy_report_rejects_relaxed_launch_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            report_path = repo_root / "team_accuracy_report.json"
            report = launch_grade_team_accuracy_report(
                threshold_overrides={
                    "minScoredClips": 2,
                    "minOpponentHighlights": 0,
                }
            )
            write_json(report_path, report)
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, report_path)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("minScoredClips threshold", collector.findings[0].detail)
        self.assertIn("minOpponentHighlights threshold", collector.findings[0].detail)

    def test_team_accuracy_report_requires_real_cloud_label_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            report_path = repo_root / "team_accuracy_report.json"
            report = launch_grade_team_accuracy_report()
            report.pop("evidence")
            write_json(report_path, report)
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, report_path)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("evaluator evidence", collector.findings[0].detail)

    def test_team_accuracy_report_rejects_temporary_draft_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            create_labeling_bundle_fixture(repo_root, complete_clip_count=0, incomplete_clip_count=54)
            report_path = (
                repo_root
                / "artifacts/team_highlight_labeling_bundle/temp_mapped_draft/team_highlight_accuracy_report.json"
            )
            write_json(report_path, launch_grade_team_accuracy_report())
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, report_path)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("temporary/draft", detail)
        self.assertIn("temp_mapped_draft", detail)
        self.assertIn("0/54 clips complete", detail)
        self.assertIn("team_highlight_label_review.html", detail)
        self.assertIn("GPT draft prefilled 54 clip(s)", detail)
        self.assertNotIn("Labeling bundle looks stale", detail)
        self.assertIn("GPT draft labels do not count", detail)

    def test_team_accuracy_report_does_not_reject_unrelated_draft_substring(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            report_path = repo_root / "artifacts/undrafted_cases/team_highlight_accuracy_report.json"
            write_json(report_path, launch_grade_team_accuracy_report())
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, report_path)

        self.assertFalse(has_failures(collector.findings))

    def test_team_accuracy_report_rejects_synthetic_or_incomplete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            report_path = repo_root / "team_accuracy_report.json"
            write_json(
                report_path,
                launch_grade_team_accuracy_report(
                    evidence_overrides={
                        "inputSource": "unit_test_fixture",
                        "distinctVideoCount": 1,
                        "casesMissingAnalysisJobId": 1,
                    }
                ),
            )
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, report_path)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("inputSource", detail)
        self.assertIn("distinctVideoCount", detail)
        self.assertIn("casesMissingAnalysisJobId", detail)

    def test_team_accuracy_report_rejects_missing_quick_scan_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            report_path = repo_root / "team_accuracy_report.json"
            write_json(
                report_path,
                launch_grade_team_accuracy_report(
                    evidence_overrides={
                        "casesMissingTeamScanJobId": 1,
                        "casesMissingDetectedTeamOptions": 1,
                        "casesMissingSelectedTeamColorLabel": 1,
                        "casesMissingSelectedTeamDetectedOption": 1,
                    }
                ),
            )
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, report_path)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("casesMissingTeamScanJobId", detail)
        self.assertIn("casesMissingDetectedTeamOptions", detail)
        self.assertIn("casesMissingSelectedTeamColorLabel", detail)
        self.assertIn("casesMissingSelectedTeamDetectedOption", detail)

    def test_team_accuracy_report_requires_hard_case_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            report_path = repo_root / "team_accuracy_report.json"
            report = launch_grade_team_accuracy_report(
                metric_overrides={
                    "madeShotOutcomeEvidenceClipCount": 0,
                    "missedShotOutcomeEvidenceClipCount": 0,
                    "opponentHighlightCount": 0,
                    "negativeClipCount": 0,
                    "badWindowNegativeCount": 0,
                    "uncertainReviewCount": 0,
                }
            )
            write_json(report_path, report)
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, report_path)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("madeShotOutcomeEvidenceClipCount", detail)
        self.assertIn("missedShotOutcomeEvidenceClipCount", detail)
        self.assertIn("opponentHighlightCount", detail)
        self.assertIn("badWindowNegativeCount", detail)
        self.assertIn("uncertainReviewCount", detail)

    def test_team_accuracy_report_passes_launch_grade_default_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            report_path = repo_root / "team_accuracy_report.json"
            write_json(report_path, launch_grade_team_accuracy_report())
            collector = Collector()

            check_team_highlight_accuracy_report(repo_root, collector, report_path)

        self.assertFalse(has_failures(collector.findings))
        self.assertIn("default-or-stricter", collector.findings[0].detail)

    def test_blocker_docs_fail_when_known_no_go_markers_remain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            for doc_path, marker, _detail in BLOCKER_DOCS:
                path = repo_root / doc_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{marker}\n", encoding="utf-8")

            collector = Collector()
            check_blocker_docs(repo_root, collector)

            failures = [finding for finding in collector.findings if finding.status == "fail"]
            self.assertEqual(len(failures), len(BLOCKER_DOCS))

    def test_conflicting_bundle_id_reference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            handoff = repo_root / "ios/docs/runbooks/rork-release-operator-handoff.md"
            handoff.parent.mkdir(parents=True, exist_ok=True)
            handoff.write_text("Apple access for bundle ID `app.rork.hoopshighlights-ai`\n", encoding="utf-8")

            collector = Collector()
            check_bundle_id_references(repo_root, collector)

            self.assertTrue(has_failures(collector.findings))

    def test_parse_devicectl_devices_preserves_state_and_model(self) -> None:
        output = """
Name             Hostname                           Identifier                             State         Model
--------------   --------------------------------   ------------------------------------   -----------   --------------------------
charlie的iPhone   charliedeiPhone.coredevice.local   E5786BB6-0095-5509-8B85-110C0B5CE6D3   unavailable   iPhone 15 Pro (iPhone16,1)
"""

        devices = parse_devicectl_devices(output)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["state"], "unavailable")
        self.assertEqual(devices[0]["model"], "iPhone 15 Pro (iPhone16,1)")

    def test_parse_devicectl_devices_handles_available_paired_state(self) -> None:
        output = """
Name             Hostname                           Identifier                             State                Model
--------------   --------------------------------   ------------------------------------   ------------------   --------------------------
charlie的iPhone   charliedeiPhone.coredevice.local   E5786BB6-0095-5509-8B85-110C0B5CE6D3   available (paired)   iPhone 15 Pro (iPhone16,1)
"""

        devices = parse_devicectl_devices(output)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["state"], "available (paired)")
        self.assertEqual(devices[0]["model"], "iPhone 15 Pro (iPhone16,1)")

    def test_connected_device_state_is_smoke_ready(self) -> None:
        self.assertTrue(ios_device_state_is_smoke_ready("connected"))
        self.assertTrue(ios_device_state_is_smoke_ready("available (paired)"))
        self.assertFalse(ios_device_state_is_smoke_ready("unavailable"))

    def test_connected_ios_device_passes_when_detected_iphone_is_available_paired(self) -> None:
        output = """
Name             Hostname                           Identifier                             State                Model
--------------   --------------------------------   ------------------------------------   ------------------   --------------------------
charlie的iPhone   charliedeiPhone.coredevice.local   E5786BB6-0095-5509-8B85-110C0B5CE6D3   available (paired)   iPhone 15 Pro (iPhone16,1)
"""
        collector = Collector()

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=output),
        ):
            check_connected_ios_device(collector)

        self.assertFalse(has_failures(collector.findings))
        self.assertIn("available iPhone", collector.findings[0].detail)

    def test_connected_ios_device_fails_when_detected_iphone_is_unavailable(self) -> None:
        output = """
Name             Hostname                           Identifier                             State         Model
--------------   --------------------------------   ------------------------------------   -----------   --------------------------
charlie的iPhone   charliedeiPhone.coredevice.local   E5786BB6-0095-5509-8B85-110C0B5CE6D3   unavailable   iPhone 15 Pro (iPhone16,1)
"""
        collector = Collector()

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=output),
        ):
            check_connected_ios_device(collector)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("unavailable", collector.findings[0].detail)

    def test_connected_ios_device_reports_unavailable_tunnel_detail(self) -> None:
        devices_output = """
Name             Hostname                           Identifier                             State         Model
--------------   --------------------------------   ------------------------------------   -----------   --------------------------
charlie的iPhone   charliedeiPhone.coredevice.local   E5786BB6-0095-5509-8B85-110C0B5CE6D3   unavailable   iPhone 15 Pro (iPhone16,1)
"""
        details_output = """
Current device information:
▿ deviceProperties:
    • developerModeStatus: enabled
    • ddiServicesAvailable: false
▿ connectionProperties:
    • lastConnectionDate: 2026-05-30 18:42:41 +0000
    • pairingState: paired
    • tunnelState: unavailable
"""
        collector = Collector()

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["xcrun", "devicectl", "list"]:
                return SimpleNamespace(returncode=0, stdout=devices_output)
            if command[:4] == ["xcrun", "devicectl", "device", "info"]:
                return SimpleNamespace(returncode=0, stdout=details_output)
            return SimpleNamespace(returncode=1, stdout="")

        with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run):
            check_connected_ios_device(collector)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("tunnelState=unavailable", collector.findings[0].detail)
        self.assertIn("developerModeStatus=enabled", collector.findings[0].detail)
        self.assertIn("Recovery: unlock the iPhone", collector.findings[0].detail)
        self.assertIn("connect it by USB", collector.findings[0].detail)

    def test_installed_testflight_build_passes_for_build_54(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            helper = repo_root / "scripts/check_installed_testflight_build.py"
            helper.parent.mkdir(parents=True, exist_ok=True)
            helper.write_text("# helper exists\n", encoding="utf-8")
            collector = Collector()
            payload = {
                "installedTestFlightBuildReady": True,
                "installedApp": {
                    "bundleId": "atrak.charlie.hoopsclips",
                    "marketingVersion": "1.0.0",
                    "buildNumber": "54",
                },
                "blockers": [],
            }

            with patch(
                "scripts.submission_readiness_preflight.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload)),
            ):
                check_installed_testflight_build(repo_root, collector)

        self.assertFalse(has_failures(collector.findings))
        self.assertIn("1.0.0 (54)", collector.findings[0].detail)

    def test_installed_testflight_build_fails_for_old_build(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            helper = repo_root / "scripts/check_installed_testflight_build.py"
            helper.parent.mkdir(parents=True, exist_ok=True)
            helper.write_text("# helper exists\n", encoding="utf-8")
            collector = Collector()
            payload = {
                "installedTestFlightBuildReady": False,
                "installedApp": {
                    "bundleId": "atrak.charlie.hoopsclips",
                    "marketingVersion": "1.0.0",
                    "buildNumber": "49",
                },
                "blockers": ["Build number mismatch: expected 54, got 49."],
            }

            with patch(
                "scripts.submission_readiness_preflight.subprocess.run",
                return_value=SimpleNamespace(returncode=1, stdout=json.dumps(payload)),
            ):
                check_installed_testflight_build(repo_root, collector)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("Build number mismatch", detail)
        self.assertIn("buildNumber=49", detail)
        self.assertIn("Install/update build 54", detail)

    def test_github_workflow_runs_fail_when_latest_required_runs_failed(self) -> None:
        payload = [
            {
                "workflowName": "iOS Internal TestFlight Upload",
                "headSha": "abc1234567890",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-05-23T21:27:18Z",
            },
            {
                "workflowName": "Cloud Edit Deploy Preflight",
                "headSha": "abc1234567890",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-05-23T20:31:19Z",
            },
        ]
        collector = Collector()

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(returncode=0, stdout="services/editing/app.py\n")
            return SimpleNamespace(returncode=1, stdout="")

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            side_effect=fake_run,
        ), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_github_workflow_runs(Path.cwd(), collector)

        failures = [finding for finding in collector.findings if finding.status == "fail"]
        self.assertEqual(len(failures), 2)
        self.assertTrue(all("conclusion=failure" in finding.detail for finding in failures))

    def test_github_workflow_runs_fail_when_runners_cannot_start(self) -> None:
        payload = [
            {
                "workflowName": "iOS Internal TestFlight Upload",
                "headSha": "abc1234567890",
                "status": "completed",
                "conclusion": "startup_failure",
                "createdAt": "2026-05-23T21:27:18Z",
            },
            {
                "workflowName": "Cloud Edit Deploy Preflight",
                "headSha": "abc1234567890",
                "status": "completed",
                "conclusion": "action_required",
                "createdAt": "2026-05-23T20:31:19Z",
            },
        ]
        collector = Collector()

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(returncode=0, stdout="services/editing/app.py\n")
            return SimpleNamespace(returncode=1, stdout="")

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            side_effect=fake_run,
        ), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_github_workflow_runs(Path.cwd(), collector)

        failures = [finding for finding in collector.findings if finding.status == "fail"]
        self.assertEqual(len(failures), 2)
        self.assertTrue(all(finding.check == "github actions startability" for finding in failures))
        self.assertTrue(all("billing/spending/action-required" in finding.detail for finding in failures))

    def test_github_workflow_runs_fail_when_latest_required_runs_are_stale(self) -> None:
        payload = [
            {
                "workflowName": "iOS Internal TestFlight Upload",
                "headSha": "old1234567890",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-23T21:27:18Z",
            },
            {
                "workflowName": "Cloud Edit Deploy Preflight",
                "headSha": "old1234567890",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-23T20:31:19Z",
            },
        ]
        collector = Collector()

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(
                    returncode=0,
                    stdout="ios/HoopsClips/HoopsClips/Views/AIEditView.swift\nservices/editing/editing_app/main.py\n",
                )
            return SimpleNamespace(returncode=1, stdout="")

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            side_effect=fake_run,
        ), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_github_workflow_runs(Path.cwd(), collector)

        failures = [finding for finding in collector.findings if finding.status == "fail"]
        self.assertEqual(len(failures), 2)
        self.assertTrue(all("not current checkout" in finding.detail for finding in failures))

    def test_github_workflow_runs_pass_when_only_docs_changed_after_latest_runs(self) -> None:
        payload = [
            {
                "workflowName": "iOS Internal TestFlight Upload",
                "headSha": "old1234567890",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-23T21:27:18Z",
            },
            {
                "workflowName": "Cloud Edit Deploy Preflight",
                "headSha": "old1234567890",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-23T20:31:19Z",
            },
        ]
        collector = Collector()

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(returncode=0, stdout="docs/phase_launch58_team_scan_unavailable_debug.md\n")
            return SimpleNamespace(returncode=1, stdout="")

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            side_effect=fake_run,
        ), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_github_workflow_runs(Path.cwd(), collector)

        self.assertFalse(has_failures(collector.findings))
        self.assertTrue(all("no workflow-relevant files changed afterward" in finding.detail for finding in collector.findings))

    def test_github_workflow_runs_fail_cloud_preflight_when_launch_script_changed(self) -> None:
        payload = [
            {
                "workflowName": "iOS Internal TestFlight Upload",
                "headSha": "old1234567890",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-23T21:27:18Z",
            },
            {
                "workflowName": "Cloud Edit Deploy Preflight",
                "headSha": "old1234567890",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-23T20:31:19Z",
            },
        ]
        collector = Collector()

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(returncode=0, stdout="scripts/build_launch_team_accuracy_report.py\n")
            return SimpleNamespace(returncode=1, stdout="")

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            side_effect=fake_run,
        ), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_github_workflow_runs(Path.cwd(), collector)

        failures = [finding for finding in collector.findings if finding.status == "fail"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].path, "Cloud Edit Deploy Preflight")
        self.assertIn("not current checkout", failures[0].detail)

    def test_github_workflow_runs_pass_when_latest_required_runs_match_current_sha(self) -> None:
        payload = [
            {
                "workflowName": "iOS Internal TestFlight Upload",
                "headSha": "abc1234567890",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-23T21:27:18Z",
            },
            {
                "workflowName": "Cloud Edit Deploy Preflight",
                "headSha": "abc1234567890",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-23T20:31:19Z",
            },
        ]
        collector = Collector()

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload)),
        ), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_github_workflow_runs(Path.cwd(), collector)

        self.assertFalse(has_failures(collector.findings))

    def test_secret_gated_deploy_preflight_fails_when_latest_dispatch_is_stale(self) -> None:
        payload = [
            {
                "databaseId": 222,
                "headSha": "abc1234567890",
                "event": "push",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-29T22:07:56Z",
            },
            {
                "databaseId": 111,
                "headSha": "old1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-05-29T22:01:08Z",
            },
        ]
        collector = Collector()

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(returncode=0, stdout="services/editing/app.py\n")
            return SimpleNamespace(returncode=1, stdout="")

        with patch(
            "scripts.submission_readiness_preflight.subprocess.run",
            side_effect=fake_run,
        ), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_secret_gated_deploy_preflight(Path.cwd(), collector)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("not current checkout", collector.findings[0].detail)
        self.assertIn("operation=credential-check", collector.findings[0].detail)
        self.assertIn("operation=preflight", collector.findings[0].detail)
        self.assertIn("operation=deploy", collector.findings[0].detail)

    def test_secret_gated_deploy_preflight_rejects_dispatch_without_secret_job(self) -> None:
        run_list_payload = [
            {
                "databaseId": 111,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-29T22:01:08Z",
            }
        ]
        run_view_payload = {
            "jobs": [
                {"name": "Worker typecheck and dry run", "status": "completed", "conclusion": "success"},
                {"name": "Editing backend Python tests", "status": "completed", "conclusion": "success"},
            ]
        }

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_view_payload))
            return SimpleNamespace(returncode=1, stdout="")

        collector = Collector()
        with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_secret_gated_deploy_preflight(Path.cwd(), collector)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("operation=credential-check", collector.findings[0].detail)
        self.assertIn("operation=preflight", collector.findings[0].detail)
        self.assertIn("operation=deploy", collector.findings[0].detail)
        self.assertIn("provider-auth preflight is not proven", collector.findings[0].detail)

    def test_secret_gated_deploy_preflight_passes_with_current_successful_secret_job(self) -> None:
        run_list_payload = [
            {
                "databaseId": 111,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-29T22:01:08Z",
            }
        ]
        run_view_payload = {
            "jobs": [
                {
                    "name": "Verify cloud edit deploy secrets",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        }

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_view_payload))
            return SimpleNamespace(returncode=1, stdout="")

        collector = Collector()
        with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_secret_gated_deploy_preflight(Path.cwd(), collector)

        self.assertFalse(has_failures(collector.findings))
        self.assertIn("provider-auth job proof", collector.findings[0].detail)

    def test_secret_gated_deploy_preflight_accepts_prior_dispatch_when_only_docs_changed(self) -> None:
        run_list_payload = [
            {
                "databaseId": 111,
                "headSha": "old1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-30T04:21:49Z",
            }
        ]
        run_view_payload = {
            "jobs": [
                {
                    "name": "Verify cloud edit deploy secrets",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        }

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_view_payload))
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(returncode=0, stdout="docs/phase_launch51_testflight_build4_readiness.md\n")
            return SimpleNamespace(returncode=1, stdout="")

        collector = Collector()
        with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_secret_gated_deploy_preflight(Path.cwd(), collector)

        self.assertFalse(has_failures(collector.findings))
        self.assertIn("no deploy-relevant files changed", collector.findings[0].detail)

    def test_secret_gated_deploy_preflight_accepts_prior_dispatch_after_testflight_status_tooling(self) -> None:
        run_list_payload = [
            {
                "databaseId": 111,
                "headSha": "old1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-07-15T19:11:20Z",
            }
        ]
        run_view_payload = {
            "jobs": [
                {
                    "name": "Verify cloud edit deploy secrets",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        }

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_view_payload))
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(
                    returncode=0,
                    stdout=(
                        ".github/workflows/ios-testflight-upload.yml\n"
                        "scripts/app_store_connect_build_status.py\n"
                        "scripts/test_app_store_connect_build_status.py\n"
                    ),
                )
            return SimpleNamespace(returncode=1, stdout="")

        collector = Collector()
        with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
            "scripts.submission_readiness_preflight.run_git",
            return_value="abc1234567890\n",
        ):
            check_secret_gated_deploy_preflight(Path.cwd(), collector)

        self.assertFalse(has_failures(collector.findings))
        self.assertIn("no deploy-relevant files changed", collector.findings[0].detail)

    def test_deploy_inputs_can_come_from_github_environment_names(self) -> None:
        def fake_github_lookup(kind: str) -> GithubEnvironmentNameLookup:
            if kind == "secret":
                return GithubEnvironmentNameLookup(
                    {"CLOUDFLARE_API_TOKEN", "GCP_WORKLOAD_IDENTITY_PROVIDER", "GCP_DEPLOY_SERVICE_ACCOUNT"}
                )
            if kind == "variable":
                return GithubEnvironmentNameLookup({"GCP_PROJECT_ID", "GCP_REGION"})
            return GithubEnvironmentNameLookup(set())

        collector = Collector()
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.submission_readiness_preflight.github_environment_name_lookup",
            side_effect=fake_github_lookup,
        ):
            check_ci_deploy_inputs(collector)

        self.assertFalse(has_failures(collector.findings))

    def test_deploy_inputs_failure_points_to_name_only_github_staging_check(self) -> None:
        collector = Collector()
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.submission_readiness_preflight.github_environment_name_lookup",
            return_value=GithubEnvironmentNameLookup(set()),
        ):
            check_ci_deploy_inputs(collector)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("Missing required deploy input name(s)", detail)
        self.assertIn("GitHub staging environment secret/variable names only", detail)
        self.assertIn("secret values are not needed", detail)
        self.assertIn("cloud-edit-deploy-preflight.yml", detail)

    def test_deploy_inputs_failure_reports_unavailable_github_name_lookup(self) -> None:
        collector = Collector()
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.submission_readiness_preflight.github_environment_name_lookup",
            return_value=GithubEnvironmentNameLookup(set(), "gh secret list --env staging needs a valid GitHub login"),
        ):
            check_ci_deploy_inputs(collector)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("GitHub staging name lookup was incomplete", collector.findings[0].detail)
        self.assertIn("valid GitHub login", collector.findings[0].detail)

    def test_production_cloud_url_inputs_can_come_from_github_production_variables(self) -> None:
        collector = Collector()
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.submission_readiness_preflight.github_production_variable_name_lookup",
            return_value=GithubEnvironmentNameLookup(set(REQUIRED_PRODUCTION_CLOUD_URL_VARIABLE_INPUTS)),
        ):
            check_production_cloud_url_inputs(collector)

        self.assertFalse(has_failures(collector.findings))

    def test_production_cloud_url_inputs_failure_points_to_name_only_github_production_check(self) -> None:
        collector = Collector()
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.submission_readiness_preflight.github_production_variable_name_lookup",
            return_value=GithubEnvironmentNameLookup(set(), "gh variable list --env production needs a valid GitHub login"),
        ):
            check_production_cloud_url_inputs(collector)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("Missing required production cloud URL input name(s)", detail)
        self.assertIn("GitHub production environment variable names only", detail)
        self.assertIn("GitHub production name lookup was incomplete", detail)
        self.assertIn("secret values are not needed", detail)
        self.assertIn("release-secrets-preflight.yml", detail)

    def test_github_stderr_detail_redacts_token_like_values(self) -> None:
        detail = _gh_stderr_detail(
            "HTTP 401 Authorization: bearer ghp_abcdefghijklmnopqrstuvwxyz1234567890ABCDEFG\n"
            "fallback token abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            "run list",
        )

        self.assertIn("<redacted-token>", detail)
        self.assertIn("Authorization: bearer <redacted>", detail)
        self.assertNotIn("ghp_", detail)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", detail)

    def test_ios_upload_inputs_can_come_from_github_environment_names(self) -> None:
        def fake_github_lookup(kind: str) -> GithubEnvironmentNameLookup:
            if kind == "secret":
                return GithubEnvironmentNameLookup(set(REQUIRED_IOS_UPLOAD_SECRET_INPUTS))
            if kind == "variable":
                return GithubEnvironmentNameLookup(set(REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS))
            return GithubEnvironmentNameLookup(set())

        collector = Collector()
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.submission_readiness_preflight.github_environment_name_lookup",
            side_effect=fake_github_lookup,
        ):
            check_ios_upload_inputs(collector)

        self.assertFalse(has_failures(collector.findings))

    def test_ios_upload_inputs_failure_points_to_name_only_github_staging_check(self) -> None:
        collector = Collector()
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.submission_readiness_preflight.github_environment_name_lookup",
            return_value=GithubEnvironmentNameLookup(set()),
        ):
            check_ios_upload_inputs(collector)

        self.assertTrue(has_failures(collector.findings))
        detail = collector.findings[0].detail
        self.assertIn("Missing required iOS upload input name(s)", detail)
        self.assertIn("GitHub staging environment secret/variable names only", detail)
        self.assertIn("secret values are not needed", detail)
        self.assertIn("ios-testflight-upload.yml", detail)

    def test_ios_signing_team_can_come_from_github_environment_secret_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            create_ready_fixture(repo_root)
            local_secrets = repo_root / "ios/HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig"
            local_secrets.write_text("HOOPS_DEVELOPMENT_TEAM = $(HOOPS_DEVELOPMENT_TEAM)\n", encoding="utf-8")

            collector = Collector()
            with patch.dict(os.environ, {}, clear=True), patch(
                "scripts.submission_readiness_preflight.github_environment_names",
                return_value={"HOOPS_DEVELOPMENT_TEAM"},
            ):
                check_ios_signing(repo_root, collector)

            self.assertFalse(has_failures(collector.findings))

    def test_ios_signing_checks_app_target_build_number_not_test_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            create_ready_fixture(repo_root)
            project_path = repo_root / "ios/HoopsClips.xcodeproj/project.pbxproj"
            project_path.write_text(
                ios_project_fixture(app_build_number="13", test_build_number=EXPECTED_IOS_BUILD_NUMBER),
                encoding="utf-8",
            )
            collector = Collector()
            with patch(
                "scripts.submission_readiness_preflight.github_environment_names",
                return_value={"HOOPS_DEVELOPMENT_TEAM"},
            ):
                check_ios_signing(repo_root, collector)

        failures = [finding for finding in collector.findings if finding.status == "fail"]
        self.assertTrue(any("build number" in finding.detail for finding in failures))

    def test_endpoint_label_omits_scheme_and_query(self) -> None:
        label = redacted_endpoint_label("https://example.test/v1/editing/version?token=secret")

        self.assertEqual(label, "example.test/v1/editing/version")

    def test_upload_artifact_rejects_stale_archive_build_number(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            archive_path = repo_root / "build/HoopsClips.xcarchive"
            archive_path.mkdir(parents=True, exist_ok=True)
            write_archive_info_plist(archive_path, build_number="3")

            collector = Collector()
            check_upload_artifact(repo_root, collector, archive_path)

            self.assertTrue(has_failures(collector.findings))

    def test_upload_artifact_accepts_current_ci_testflight_upload_proof(self) -> None:
        run_list_payload = [
            {
                "databaseId": 111,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-30T04:33:01Z",
            }
        ]
        upload_log = "\n".join(
            [
                "Progress 21%: Uploaded package is processing.",
                "Progress 21%: Upload succeeded.",
                "Uploaded HoopsClips",
                "Internal TestFlight upload command completed",
            ]
        )

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=upload_log)
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(repo_root, collector, None)

            self.assertFalse(has_failures(collector.findings))

    def test_upload_artifact_reports_current_ci_archive_signing_failure(self) -> None:
        run_list_payload = [
            {
                "databaseId": 222,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-06-06T05:51:22Z",
            }
        ]
        archive_log = "\n".join(
            [
                "** ARCHIVE FAILED **",
                "Choose a certificate to revoke. Your account has reached the maximum number of certificates.",
                "No profiles for 'atrak.charlie.hoopsclips' were found.",
            ]
        )

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=archive_log)
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(repo_root, collector, None)

            self.assertTrue(has_failures(collector.findings))
            detail = collector.findings[0].detail
            self.assertIn("internal TestFlight archive/upload workflow", detail)
            self.assertIn("conclusion=failure", detail)
            self.assertIn("maximum number of certificates", detail)
            self.assertIn("No profiles for 'atrak.charlie.hoopsclips' were found", detail)

    def test_upload_artifact_prefers_current_ci_archive_failure_over_stale_default_archive(self) -> None:
        run_list_payload = [
            {
                "databaseId": 222,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-06-06T05:51:22Z",
            }
        ]
        archive_log = "Choose a certificate to revoke. Your account has reached the maximum number of certificates."

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=archive_log)
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            stale_archive = repo_root / "ios/build/HoopsClips-InternalStaging-Build14.xcarchive"
            stale_archive.mkdir(parents=True, exist_ok=True)
            write_archive_info_plist(stale_archive, build_number="14")
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(repo_root, collector, None)

            self.assertTrue(has_failures(collector.findings))
            detail = collector.findings[0].detail
            self.assertIn("maximum number of certificates", detail)
            self.assertNotIn("CFBundleVersion", detail)

    def test_upload_artifact_reports_current_codecheck_success_without_upload_proof(self) -> None:
        run_list_payload = [
            {
                "databaseId": 333,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-06-06T08:13:24Z",
            },
            {
                "databaseId": 222,
                "headSha": "old1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-06-06T05:51:22Z",
            },
        ]

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout="Unsigned codecheck completed.")
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            stale_archive = repo_root / "ios/build/HoopsClips-InternalStaging-Build14.xcarchive"
            stale_archive.mkdir(parents=True, exist_ok=True)
            write_archive_info_plist(stale_archive, build_number="14")
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(repo_root, collector, None)

            self.assertTrue(has_failures(collector.findings))
            detail = collector.findings[0].detail
            self.assertIn("completed successfully", detail)
            self.assertIn("upload log proof was not found", detail)
            self.assertIn("codecheck-only run", detail)
            self.assertNotIn("CFBundleVersion", detail)
            self.assertNotIn("maximum number of certificates", detail)

    def test_upload_artifact_accepts_current_signed_archive_without_claiming_upload(self) -> None:
        run_list_payload = [
            {
                "databaseId": 444,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-07-19T15:06:10Z",
            },
        ]
        archive_log = "\n".join(
            [
                "Archive created",
                "CFBundleIdentifier=expected",
                "CFBundleShortVersionString=expected",
                "CFBundleVersion=expected",
                "HOOPSAppEnvironment=expected",
                "HOOPSCloudLaunchMode=expected",
                "HOOPSCloudAnalysisBaseURL=expected",
                "HOOPSCloudEditBaseURL=expected",
                "PrivacyInfo.xcprivacy=present-and-valid",
                "Archive signing certificate serial captured",
                "Archive/preflight operation completed; no App Store Connect upload was attempted.",
            ]
        )

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=archive_log)
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(repo_root, collector, None)

            self.assertFalse(has_failures(collector.findings))
            detail = collector.findings[0].detail
            self.assertIn("Successful signed internal staging archive log proof exists", detail)
            self.assertIn("No App Store Connect upload is claimed", detail)
            self.assertNotIn("Successful internal TestFlight upload", detail)

    def test_upload_artifact_prefers_current_upload_proof_over_stale_local_archive(self) -> None:
        run_list_payload = [
            {
                "databaseId": 444,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-06-07T04:36:20Z",
            },
        ]
        upload_log = "\n".join(
            [
                "Progress 9%: Upload succeeded.",
                "Uploaded HoopsClips",
                "Internal TestFlight upload command completed",
            ]
        )

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=upload_log)
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            stale_archive = repo_root / "ios/build/HoopsClips-InternalStaging-Build14.xcarchive"
            stale_archive.mkdir(parents=True, exist_ok=True)
            write_archive_info_plist(stale_archive, build_number="14")
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(repo_root, collector, None)

            self.assertFalse(has_failures(collector.findings))
            self.assertIn("Successful internal TestFlight upload log proof exists", collector.findings[0].detail)

    def test_upload_artifact_accepts_prior_ci_upload_when_only_docs_changed(self) -> None:
        run_list_payload = [
            {
                "databaseId": 111,
                "headSha": "old1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-30T04:33:01Z",
            }
        ]
        upload_log = "\n".join(
            [
                "Progress 21%: Upload succeeded.",
                "Uploaded HoopsClips",
                "Internal TestFlight upload command completed",
            ]
        )

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=upload_log)
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(returncode=0, stdout="docs/phase_launch51_testflight_build4_readiness.md\nscripts/submission_readiness_preflight.py\n")
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(repo_root, collector, None)

            self.assertFalse(has_failures(collector.findings))

    def test_upload_artifact_accepts_prior_ci_upload_when_only_ios_backend_changed(self) -> None:
        run_list_payload = [
            {
                "databaseId": 111,
                "headSha": "old1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-05-30T04:33:01Z",
            }
        ]
        upload_log = "\n".join(
            [
                "Progress 21%: Upload succeeded.",
                "Uploaded HoopsClips",
                "Internal TestFlight upload command completed",
            ]
        )

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=upload_log)
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(returncode=0, stdout="ios/backend/app/editing.py\nservices/editing/editing_app/gpt_reranker.py\n")
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(repo_root, collector, None)

            self.assertFalse(has_failures(collector.findings))

    def test_upload_artifact_accepts_prior_upload_after_read_only_status_dispatch(self) -> None:
        run_list_payload = [
            {
                "databaseId": 999,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-07-15T19:37:20Z",
            },
            {
                "databaseId": 111,
                "headSha": "old1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-07-15T19:11:20Z",
            },
        ]
        upload_log = "\n".join(
            [
                "Progress 21%: Upload succeeded.",
                "Uploaded HoopsClips",
                "Internal TestFlight upload command completed",
            ]
        )
        status_log = "App Store Connect confirms this build is ready for internal TestFlight."

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=status_log if command[3] == "999" else upload_log)
            if command[:3] == ["git", "diff", "--name-only"]:
                return SimpleNamespace(
                    returncode=0,
                    stdout=(
                        ".github/workflows/ios-testflight-upload.yml\n"
                        "scripts/app_store_connect_build_status.py\n"
                    ),
                )
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(Path(temp_dir), collector, None)

        self.assertFalse(has_failures(collector.findings))
        self.assertIn("Successful internal TestFlight upload log proof exists", collector.findings[0].detail)

    def test_upload_artifact_accepts_duplicate_upload_when_status_proves_internal_testing(self) -> None:
        run_list_payload = [
            {
                "databaseId": 999,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2026-07-18T10:40:28Z",
            },
            {
                "databaseId": 555,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-07-18T10:33:27Z",
            },
        ]
        status_log = "App Store Connect confirms this build is ready for internal TestFlight."
        duplicate_log = "The bundle version must be higher than the previously uploaded version: ‘54’."

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=status_log if command[3] == "999" else duplicate_log)
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(Path(temp_dir), collector, None)

        self.assertFalse(has_failures(collector.findings))
        self.assertIn("already exists", collector.findings[0].detail)
        self.assertIn("ready for internal testing", collector.findings[0].detail)

    def test_upload_artifact_rejects_duplicate_upload_without_status_proof(self) -> None:
        run_list_payload = [
            {
                "databaseId": 555,
                "headSha": "abc1234567890",
                "event": "workflow_dispatch",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-07-18T10:33:27Z",
            },
        ]
        duplicate_log = "The bundle version must be higher than the previously uploaded version: ‘54’."

        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            if command[:3] == ["gh", "run", "list"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(run_list_payload))
            if command[:3] == ["gh", "run", "view"]:
                return SimpleNamespace(returncode=0, stdout=duplicate_log)
            return SimpleNamespace(returncode=1, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            collector = Collector()
            with patch("scripts.submission_readiness_preflight.subprocess.run", side_effect=fake_run), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_upload_artifact(Path(temp_dir), collector, None)

        self.assertTrue(has_failures(collector.findings))
        self.assertIn("already uploaded", collector.findings[0].detail)
        self.assertIn("status operation", collector.findings[0].detail)

    def test_live_editing_version_fails_when_required_flag_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()
            payload = {
                "gitSha": "abc1234",
                "featureFlags": {
                    "aiEditEnabled": True,
                    "aiEditRevisionEnabled": True,
                    "aiEditTemplatePackEnabled": True,
                },
            }

            with patch(
                "scripts.submission_readiness_preflight.fetch_version_payload",
                return_value=(200, json.dumps(payload).encode("utf-8")),
            ), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_live_editing_version("https://editing.example.test/version?token=secret", collector, repo_root=repo_root, skip_live=False, timeout_seconds=1.0)

            failures = [finding for finding in collector.findings if finding.status == "fail"]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].check, "live editing feature flags")
            self.assertIn("aiEditLiveRenderEnabled", failures[0].detail)
            self.assertNotIn("secret", failures[0].path)

    def test_live_editing_version_fails_when_git_sha_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()
            payload = {
                "gitSha": "deadbee",
                "featureFlags": {
                    "aiEditEnabled": True,
                    "aiEditLiveRenderEnabled": True,
                    "aiEditRevisionEnabled": True,
                    "aiEditTemplatePackEnabled": True,
                    "aiClipGptEditorEnabled": True,
                    "aiClipGptPlanEditEnabled": True,
                    "aiClipGptRevisionEnabled": True,
                    "gptHighlightRerankerEnabled": True,
                },
            }

            with patch(
                "scripts.submission_readiness_preflight.fetch_version_payload",
                return_value=(200, json.dumps(payload).encode("utf-8")),
            ), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ):
                check_live_editing_version("https://editing.example.test/version", collector, repo_root=repo_root, skip_live=False, timeout_seconds=1.0)

            failures = [finding for finding in collector.findings if finding.status == "fail"]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].check, "live editing git sha")
            self.assertIn("does not match", failures[0].detail)

    def test_live_editing_version_includes_network_error_detail_on_urLError(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()

            with patch(
                "scripts.submission_readiness_preflight.fetch_version_payload",
                return_value=URLError("Name or service not known"),
            ):
                check_live_editing_version(
                    "https://editing.example.test/version",
                    collector,
                    repo_root=repo_root,
                    skip_live=False,
                    timeout_seconds=1.0,
                )

            failures = [finding for finding in collector.findings if finding.status == "fail"]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].check, "live editing version route")
            self.assertIn("Probe failed: URLError", failures[0].detail)
            self.assertIn("Name or service not known", failures[0].detail)
            self.assertIn("authorized/networked environment", failures[0].detail)

    def test_live_worker_version_includes_network_error_detail_on_urLError(self) -> None:
        collector = Collector()

        with patch(
            "scripts.submission_readiness_preflight.fetch_version_payload",
            return_value=URLError("certificate verify failed"),
        ):
            check_live_worker_version(
                "https://worker.example.test",
                collector,
                skip_live=False,
                timeout_seconds=1.0,
            )

        failures = [finding for finding in collector.findings if finding.status == "fail"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].check, "live worker version route")
        self.assertIn("Probe failed: URLError", failures[0].detail)
        self.assertIn("certificate verify failed", failures[0].detail)
        self.assertIn("authorized/networked environment", failures[0].detail)

    def test_live_editing_version_passes_when_only_docs_changed_after_deploy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            collector = Collector()
            payload = {
                "gitSha": "old1234567890",
                "featureFlags": {
                    "aiEditEnabled": True,
                    "aiEditLiveRenderEnabled": True,
                    "aiEditRevisionEnabled": True,
                    "aiEditTemplatePackEnabled": True,
                    "aiClipGptEditorEnabled": True,
                    "aiClipGptPlanEditEnabled": True,
                    "aiClipGptRevisionEnabled": True,
                    "gptHighlightRerankerEnabled": True,
                },
            }

            def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
                if command[:3] == ["git", "diff", "--name-only"]:
                    return SimpleNamespace(returncode=0, stdout="docs/phase_launch58_team_scan_unavailable_debug.md\n")
                return SimpleNamespace(returncode=1, stdout="")

            with patch(
                "scripts.submission_readiness_preflight.fetch_version_payload",
                return_value=(200, json.dumps(payload).encode("utf-8")),
            ), patch(
                "scripts.submission_readiness_preflight.run_git",
                return_value="abc1234567890\n",
            ), patch(
                "scripts.submission_readiness_preflight.subprocess.run",
                side_effect=fake_run,
            ):
                check_live_editing_version("https://editing.example.test/version", collector, repo_root=repo_root, skip_live=False, timeout_seconds=1.0)

            self.assertFalse(has_failures(collector.findings))
            self.assertTrue(
                any("no editing-service deploy-relevant files changed afterward" in finding.detail for finding in collector.findings)
            )


def launch_grade_team_accuracy_report(
    *,
    metric_overrides: dict[str, object] | None = None,
    threshold_overrides: dict[str, object] | None = None,
    evidence_overrides: dict[str, object] | None = None,
    status: str = "pass",
) -> dict[str, object]:
    thresholds = asdict(AccuracyThresholds())
    thresholds.update(threshold_overrides or {})
    metrics: dict[str, object] = {
        "caseCount": 2,
        "clipCount": 12,
        "allTeamsCaseCount": 1,
        "selectedTeamPrecision": 0.92,
        "selectedTeamEvidenceQuality": 0.92,
        "selectedTeamRecallWithUncertain": 0.92,
        "highlightPrecision": 0.92,
        "highlightRecall": 0.92,
        "defensiveEventRecall": 0.92,
        "clipTimingQuality": 0.92,
        "shotOutcomeEvidenceQuality": 0.92,
        "uncertainReviewCount": 1,
        "selectedTeamHighlightCount": 6,
        "defensiveEventCount": 2,
        "timingQualityClipCount": 12,
        "badTimingClipCount": 0,
        "shotOutcomeEvidenceClipCount": 3,
        "madeShotOutcomeEvidenceClipCount": 1,
        "missedShotOutcomeEvidenceClipCount": 1,
        "badShotOutcomeEvidenceCount": 0,
        "selectedTeamBlockCount": 1,
        "selectedTeamStealCount": 1,
        "selectedTeamForcedTurnoverCount": 1,
        "selectedTeamDefensiveStopCount": 1,
        "opponentHighlightCount": 2,
        "negativeClipCount": 2,
        "badWindowNegativeCount": 2,
        "selectedTeamEvidenceClipCount": 6,
        "badSelectedTeamEvidenceCount": 0,
    }
    metrics.update(metric_overrides or {})
    evidence: dict[str, object] = {
        "inputSchemaVersion": "team-highlight-eval-v1",
        "inputSource": "real_cloud_analysis_with_manual_labels",
        "caseCount": metrics["caseCount"],
        "allTeamsCaseCount": metrics["allTeamsCaseCount"],
        "distinctVideoCount": 2,
        "casesMissingTeamMode": 0,
        "casesMissingCaseId": 0,
        "casesMissingVideoId": 0,
        "casesMissingSelectedTeamId": 0,
        "casesMissingAnalysisJobId": 0,
        "casesMissingTeamScanJobId": 0,
        "casesMissingDetectedTeamOptions": 0,
        "casesMissingSelectedTeamColorLabel": 0,
        "casesMissingSelectedTeamDetectedOption": 0,
    }
    evidence.update(evidence_overrides or {})
    return {
        "status": status,
        "metrics": metrics,
        "thresholds": thresholds,
        "failures": [],
        "evidence": evidence,
    }


def create_labeling_bundle_fixture(
    repo_root: Path,
    *,
    complete_clip_count: int,
    incomplete_clip_count: int,
    clip_count: int = 54,
    bundle_dir: Path = Path("artifacts/team_highlight_labeling_bundle"),
) -> None:
    bundle_dir = repo_root / bundle_dir
    bundle_rel = bundle_dir.relative_to(repo_root).as_posix()
    close_review_count = max(0, clip_count - 5)
    standard_review_count = min(5, clip_count)
    write_json(
        bundle_dir / "label_status.json",
        {
            "schemaVersion": "team-highlight-label-status-v1",
            "status": "incomplete",
            "clipCount": clip_count,
            "completeClipCount": complete_clip_count,
            "incompleteClipCount": incomplete_clip_count,
            "missingFieldCounts": {
                "expected.teamId": incomplete_clip_count,
                "expected.isHighlight": incomplete_clip_count,
                "expected.eventType": incomplete_clip_count,
                "expected.outcome": incomplete_clip_count,
                "needsLabel=false": incomplete_clip_count,
                "reviewedByHuman=true": incomplete_clip_count,
            },
        },
    )
    write_json(
        bundle_dir / "bundle_metadata.json",
        {
            "schemaVersion": "team-highlight-labeling-bundle-v1",
            "reviewPage": f"{bundle_rel}/team_highlight_label_review.html",
            "labelStatus": f"{bundle_rel}/label_status.json",
            "clipCount": clip_count,
            "completeClipCount": complete_clip_count,
            "incompleteClipCount": incomplete_clip_count,
            "reviewPageMetadata": {
                "draftPrefill": {
                    "appliedClipCount": clip_count,
                    "skippedClipCount": 1,
                },
                "reviewPriorityCounts": {
                    "needs_close_review": close_review_count,
                    "standard_review": standard_review_count,
                },
            },
        },
    )
    (bundle_dir / "team_highlight_label_review.html").write_text(
        "Next close review\nJ/L scrub\nfunction scrubVideosForCard\nDownload launch-ready labels\n"
        "Launch evidence checklist\nneedsLabel=false\nreviewedByHuman=true\n",
        encoding="utf-8",
    )
    (bundle_dir / "next_steps.md").write_text(
        "Use `Next close review` first\n"
        "`J/L` scrub back/forward\n"
        "Use `P` to copy the HoopClips/GPT draft into fields as data-entry help only; "
        "it is not evidence until you watch the video and mark reviewed.\n"
        "Launch Evidence Checklist\n"
        "expected.teamId\n"
        "expected.isHighlight\n"
        "expected.eventType\n"
        "expected.outcome\n"
        "final bundle is applied without `--allow-incomplete`\n"
        "Download launch-ready labels\n",
        encoding="utf-8",
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def create_ready_fixture(repo_root: Path) -> Path:
    project_path = repo_root / "ios/HoopsClips.xcodeproj/project.pbxproj"
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(ios_project_fixture(), encoding="utf-8")

    config_dir = repo_root / "ios/HoopsClips/HoopsClips/Config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "LocalSecrets.xcconfig").write_text("HOOPS_DEVELOPMENT_TEAM = TEAM123456\n", encoding="utf-8")
    (config_dir / "InternalStaging.xcconfig").write_text(
        "HOOPS_CLOUD_EDIT_BASE_URL = https:/$()/staging-worker.example.test\n",
        encoding="utf-8",
    )
    handoff = repo_root / "ios/docs/runbooks/rork-release-operator-handoff.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(f"Apple access for bundle ID `{EXPECTED_IOS_BUNDLE_ID}`\n", encoding="utf-8")

    export_options_path = repo_root / "ios/exportOptions.testflight-internal.plist"
    with export_options_path.open("wb") as handle:
        plistlib.dump(
            {
                "destination": "upload",
                "distributionBundleIdentifier": "atrak.charlie.hoopsclips",
                "method": "app-store-connect",
                "signingStyle": "automatic",
                "testFlightInternalTestingOnly": True,
                "teamID": "K99RADPB9G",
                "uploadSymbols": True,
            },
            handle,
        )

    for doc_path, _marker, _detail in BLOCKER_DOCS:
        path = repo_root / doc_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Ready evidence recorded.\n", encoding="utf-8")

    archive_path = repo_root / "build/HoopsClips.xcarchive"
    archive_path.mkdir(parents=True, exist_ok=True)
    write_archive_info_plist(archive_path)
    return archive_path


def ios_project_fixture(*, app_build_number: str = EXPECTED_IOS_BUILD_NUMBER, test_build_number: str = "7") -> str:
    return f"""
        105FC59E2E9EAD3200EA8BCF /* Debug */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                CODE_SIGN_STYLE = Automatic;
                CURRENT_PROJECT_VERSION = {app_build_number};
                DEVELOPMENT_TEAM = "$(HOOPS_DEVELOPMENT_TEAM)";
                MARKETING_VERSION = {EXPECTED_IOS_MARKETING_VERSION};
                PRODUCT_BUNDLE_IDENTIFIER = "{EXPECTED_IOS_BUNDLE_ID}";
            }};
            name = Debug;
        }};
        105FC59F2E9EAD3200EA8BCF /* Release */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                CODE_SIGN_STYLE = Automatic;
                CURRENT_PROJECT_VERSION = {app_build_number};
                DEVELOPMENT_TEAM = "$(HOOPS_DEVELOPMENT_TEAM)";
                MARKETING_VERSION = {EXPECTED_IOS_MARKETING_VERSION};
                PRODUCT_BUNDLE_IDENTIFIER = "{EXPECTED_IOS_BUNDLE_ID}";
            }};
            name = Release;
        }};
        195FC59E2E9EAD3200EA8BCF /* Tests Debug */ = {{
            isa = XCBuildConfiguration;
            buildSettings = {{
                CURRENT_PROJECT_VERSION = {test_build_number};
                MARKETING_VERSION = {EXPECTED_IOS_MARKETING_VERSION};
                PRODUCT_BUNDLE_IDENTIFIER = "{EXPECTED_IOS_BUNDLE_ID}.tests";
            }};
            name = Debug;
        }};
    """


def write_archive_info_plist(archive_path: Path, *, build_number: str = EXPECTED_IOS_BUILD_NUMBER) -> None:
    with (archive_path / "Info.plist").open("wb") as handle:
        plistlib.dump(
            {
                "ApplicationProperties": {
                    "CFBundleIdentifier": EXPECTED_IOS_BUNDLE_ID,
                    "CFBundleShortVersionString": EXPECTED_IOS_MARKETING_VERSION,
                    "CFBundleVersion": build_number,
                }
            },
            handle,
        )


if __name__ == "__main__":
    unittest.main()

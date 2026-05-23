import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.submission_readiness_preflight import (
    BLOCKER_DOCS,
    Collector,
    EXPECTED_IOS_BUNDLE_ID,
    check_bundle_id_references,
    check_blocker_docs,
    check_ci_deploy_inputs,
    has_failures,
    redacted_endpoint_label,
    run_checks,
)


class SubmissionReadinessPreflightTests(unittest.TestCase):
    def test_ready_fixture_passes_without_printing_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            archive_path = create_ready_fixture(repo_root)

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
            ), patch.dict(
                os.environ,
                {
                    "CLOUDFLARE_API_TOKEN": "present",
                    "GCP_WORKLOAD_IDENTITY_PROVIDER": "present",
                    "GCP_DEPLOY_SERVICE_ACCOUNT": "present",
                    "GCP_PROJECT_ID": "present",
                    "GCP_REGION": "present",
                },
                clear=True,
            ):
                findings = run_checks(repo_root, archive_path=archive_path)

            self.assertFalse(has_failures(findings), "\n".join(f"{item.check}: {item.detail}" for item in findings if item.status == "fail"))
            details = "\n".join(item.detail for item in findings)
            self.assertNotIn("TEAM123456", details)
            self.assertNotIn("K99RADPB9G", details)

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

    def test_deploy_inputs_can_come_from_github_environment_names(self) -> None:
        def fake_github_names(kind: str) -> set[str]:
            if kind == "secret":
                return {"CLOUDFLARE_API_TOKEN", "GCP_WORKLOAD_IDENTITY_PROVIDER", "GCP_DEPLOY_SERVICE_ACCOUNT"}
            if kind == "variable":
                return {"GCP_PROJECT_ID", "GCP_REGION"}
            return set()

        collector = Collector()
        with patch.dict(os.environ, {}, clear=True), patch("scripts.submission_readiness_preflight.github_environment_names", side_effect=fake_github_names):
            check_ci_deploy_inputs(collector)

        self.assertFalse(has_failures(collector.findings))

    def test_endpoint_label_omits_scheme_and_query(self) -> None:
        label = redacted_endpoint_label("https://example.test/v1/editing/version?token=secret")

        self.assertEqual(label, "example.test/v1/editing/version")


def create_ready_fixture(repo_root: Path) -> Path:
    project_path = repo_root / "ios/HoopsClips.xcodeproj/project.pbxproj"
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(
        """
        PRODUCT_BUNDLE_IDENTIFIER = "atrak.charlie.hoopsclips";
        MARKETING_VERSION = 1.0.0;
        CURRENT_PROJECT_VERSION = 3;
        CODE_SIGN_STYLE = Automatic;
        DEVELOPMENT_TEAM = "$(HOOPS_DEVELOPMENT_TEAM)";
        """,
        encoding="utf-8",
    )

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
    return archive_path


if __name__ == "__main__":
    unittest.main()

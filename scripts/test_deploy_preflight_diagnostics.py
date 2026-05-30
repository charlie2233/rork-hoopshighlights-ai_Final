import subprocess
import unittest
from unittest.mock import patch

from services.editing.scripts import deploy_preflight


class DeployPreflightDiagnosticsTests(unittest.TestCase):
    def test_secret_classifier_reports_missing_secret(self) -> None:
        with patch.object(deploy_preflight, "run", return_value=completed(1, stderr="NOT_FOUND: Secret [HOOPS_OPENAI_API_KEY] not found")):
            result = deploy_preflight.classify_secret_manager_secret("HOOPS_OPENAI_API_KEY", "hoopsclips-9d38f")

        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "Secret Manager secret HOOPS_OPENAI_API_KEY is missing.")

    def test_secret_classifier_reports_permission_denied(self) -> None:
        with patch.object(deploy_preflight, "run", return_value=completed(1, stderr="PERMISSION_DENIED: Permission denied")):
            result = deploy_preflight.classify_secret_manager_secret("HOOPS_R2_SECRET_ACCESS_KEY", "hoopsclips-9d38f")

        self.assertFalse(result.ok)
        self.assertIn("not readable by the deploy identity", result.detail)
        self.assertIn("Secret Manager Secret Accessor", result.detail)
        self.assertIn("Secret Manager Viewer", result.detail)

    def test_secret_classifier_reports_no_latest_version(self) -> None:
        responses = [
            completed(0, stdout="projects/hoopsclips-9d38f/secrets/HOOPS_OPENAI_API_KEY\n"),
            completed(1, stderr="NOT_FOUND: Secret Version [latest] not found"),
        ]
        with patch.object(deploy_preflight, "run", side_effect=responses):
            result = deploy_preflight.classify_secret_manager_secret("HOOPS_OPENAI_API_KEY", "hoopsclips-9d38f")

        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "Secret Manager secret HOOPS_OPENAI_API_KEY has no latest version.")

    def test_secret_classifier_requires_enabled_latest_version(self) -> None:
        responses = [
            completed(0, stdout="projects/hoopsclips-9d38f/secrets/HOOPS_OPENAI_API_KEY\n"),
            completed(0, stdout="DISABLED\n"),
        ]
        with patch.object(deploy_preflight, "run", side_effect=responses):
            result = deploy_preflight.classify_secret_manager_secret("HOOPS_OPENAI_API_KEY", "hoopsclips-9d38f")

        self.assertFalse(result.ok)
        self.assertEqual(
            result.detail,
            "Secret Manager secret HOOPS_OPENAI_API_KEY latest version is DISABLED; add or enable a latest version.",
        )

    def test_secret_classifier_passes_enabled_latest_version(self) -> None:
        responses = [
            completed(0, stdout="projects/hoopsclips-9d38f/secrets/HOOPS_OPENAI_API_KEY\n"),
            completed(0, stdout="ENABLED\n"),
        ]
        with patch.object(deploy_preflight, "run", side_effect=responses):
            result = deploy_preflight.classify_secret_manager_secret("HOOPS_OPENAI_API_KEY", "hoopsclips-9d38f")

        self.assertTrue(result.ok)
        self.assertEqual(result.detail, "Secret Manager secret HOOPS_OPENAI_API_KEY exists and latest version is ENABLED.")

    def test_wrangler_classifier_reports_rejected_token(self) -> None:
        result = deploy_preflight.classify_wrangler_auth(
            completed(1, stderr="Authentication error [code: 10000]: Invalid API Token"),
            token_present=True,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "Wrangler auth failed because CLOUDFLARE_API_TOKEN was rejected.")

    def test_wrangler_classifier_reports_scope_or_account_failure(self) -> None:
        result = deploy_preflight.classify_wrangler_auth(
            completed(1, stderr="Unauthorized: token does not have permission for this account"),
            token_present=True,
        )

        self.assertFalse(result.ok)
        self.assertIn("missing required account scope or permissions", result.detail)

    def test_wrangler_classifier_reports_missing_ci_token_and_oauth(self) -> None:
        result = deploy_preflight.classify_wrangler_auth(completed(1, stderr="You are not logged in"), token_present=False)

        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "CLOUDFLARE_API_TOKEN is not set and local Wrangler OAuth is not authenticated.")


def completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["probe"], returncode=returncode, stdout=stdout, stderr=stderr)


if __name__ == "__main__":
    unittest.main()

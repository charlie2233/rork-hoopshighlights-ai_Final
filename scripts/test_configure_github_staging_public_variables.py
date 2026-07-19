import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from scripts.configure_github_staging_public_variables import (
    apply_variables,
    resolve_public_variable_values,
)


class ConfigureGitHubStagingPublicVariablesTests(unittest.TestCase):
    def test_resolves_public_values_from_repo_sources(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        values = resolve_public_variable_values(repo_root)

        self.assertEqual(values["GCP_PROJECT_ID"][0], "hoopsclips-9d38f")
        self.assertEqual(values["GCP_PROJECT_ID"][1], "docs/gcp_cost_control_2026_05_10.md")
        self.assertEqual(values["GCP_REGION"][0], "us-central1")
        self.assertEqual(values["GCP_REGION"][1], "services/editing/cloudbuild.yaml")
        self.assertEqual(values["HOOPS_PRIVACY_POLICY_URL"][0], "https://atrak.dev/apps/hoopsclips/privacy.html")
        self.assertEqual(values["HOOPS_PRIVACY_POLICY_URL"][1], "ios/docs/runbooks/rork-release-operator-handoff.md")
        self.assertEqual(values["HOOPS_TERMS_OF_SERVICE_URL"][0], "https://atrak.dev/apps/hoopsclips/terms.html")
        self.assertEqual(values["HOOPS_TERMS_OF_SERVICE_URL"][1], "ios/docs/runbooks/rork-release-operator-handoff.md")

    def test_dry_run_output_does_not_print_variable_values(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        result = subprocess.run(
            [sys.executable, "scripts/configure_github_staging_public_variables.py"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("GCP_PROJECT_ID ready", result.stdout)
        self.assertIn("GCP_REGION ready", result.stdout)
        self.assertIn("HOOPS_PRIVACY_POLICY_URL ready", result.stdout)
        self.assertIn("HOOPS_TERMS_OF_SERVICE_URL ready", result.stdout)
        self.assertNotIn("hoopsclips-9d38f", result.stdout)
        self.assertNotIn("us-central1", result.stdout)
        self.assertNotIn("atrak.dev/apps/hoopsclips/privacy.html", result.stdout)
        self.assertNotIn("atrak.dev/apps/hoopsclips/terms.html", result.stdout)

    def test_json_output_omits_variable_values(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        result = subprocess.run(
            [sys.executable, "scripts/configure_github_staging_public_variables.py", "--json"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertTrue(all(item["value_available"] for item in payload["variables"]))
        self.assertNotIn("hoopsclips-9d38f", result.stdout)
        self.assertNotIn("us-central1", result.stdout)
        self.assertNotIn("atrak.dev/apps/hoopsclips/privacy.html", result.stdout)
        self.assertNotIn("atrak.dev/apps/hoopsclips/terms.html", result.stdout)

    def test_apply_uses_gh_variable_set_without_printing_values(self) -> None:
        values = {
            "GCP_PROJECT_ID": ("hoopsclips-9d38f", "docs/gcp_cost_control_2026_05_10.md"),
            "GCP_REGION": ("us-central1", "services/editing/cloudbuild.yaml"),
            "HOOPS_PRIVACY_POLICY_URL": ("https://atrak.dev/apps/hoopsclips/privacy.html", "ios/docs/runbooks/rork-release-operator-handoff.md"),
            "HOOPS_TERMS_OF_SERVICE_URL": ("https://atrak.dev/apps/hoopsclips/terms.html", "ios/docs/runbooks/rork-release-operator-handoff.md"),
        }

        with mock.patch("scripts.configure_github_staging_public_variables.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

            results = apply_variables(values, repo="owner/repo", environment="staging")

        self.assertEqual([result.status for result in results], ["set", "set", "set", "set"])
        first_call = run.call_args_list[0].args[0]
        self.assertEqual(first_call[:4], ["gh", "variable", "set", "GCP_PROJECT_ID"])
        self.assertIn("--body", first_call)
        self.assertEqual(first_call[first_call.index("--body") + 1], "hoopsclips-9d38f")


if __name__ == "__main__":
    unittest.main()

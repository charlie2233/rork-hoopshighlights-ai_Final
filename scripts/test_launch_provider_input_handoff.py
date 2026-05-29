import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.launch_provider_input_handoff import build_handoff, render_markdown
from scripts.submission_readiness_preflight import (
    REQUIRED_DEPLOY_SECRET_INPUTS,
    REQUIRED_DEPLOY_VARIABLE_INPUTS,
    REQUIRED_IOS_UPLOAD_SECRET_INPUTS,
    REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS,
)


class LaunchProviderInputHandoffTests(unittest.TestCase):
    def test_handoff_includes_every_required_provider_input(self) -> None:
        handoff = build_handoff()

        secret_names = {item.name for item in handoff.githubSecrets}
        variable_names = {item.name for item in handoff.githubVariables}
        gcp_secret_names = {item.name for item in handoff.gcpSecretManagerSecrets}

        self.assertEqual(secret_names, set(REQUIRED_DEPLOY_SECRET_INPUTS) | set(REQUIRED_IOS_UPLOAD_SECRET_INPUTS))
        self.assertEqual(variable_names, set(REQUIRED_DEPLOY_VARIABLE_INPUTS) | set(REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS))
        self.assertEqual(
            gcp_secret_names,
            {"HOOPS_EDITING_SERVICE_SECRET", "HOOPS_R2_ACCESS_KEY_ID", "HOOPS_R2_SECRET_ACCESS_KEY", "HOOPS_OPENAI_API_KEY"},
        )
        self.assertTrue(any("wrangler whoami" in item for item in handoff.cloudflareTokenRequirements))
        self.assertEqual([item.name for item in handoff.localInputs], ["HOOPS_DEVELOPMENT_TEAM"])

    def test_markdown_uses_placeholders_without_secret_values(self) -> None:
        markdown = render_markdown(build_handoff())

        self.assertIn("gh secret set CLOUDFLARE_API_TOKEN", markdown)
        self.assertIn("gh variable set GCP_PROJECT_ID", markdown)
        self.assertIn("gcloud secrets describe HOOPS_OPENAI_API_KEY", markdown)
        self.assertIn("gcloud secrets versions add HOOPS_OPENAI_API_KEY", markdown)
        self.assertIn("GitHub Actions billing/spending/startability fixed", markdown)
        self.assertIn("Atlas / Browser Agent Prompt", markdown)
        self.assertIn("Do not paste, reveal, summarize, screenshot, or return", markdown)
        self.assertIn("HOOPS_DEVELOPMENT_TEAM = <team-id>", markdown)
        self.assertIn("Do not paste secret values", markdown)
        self.assertNotIn("<secret-value>", markdown)
        self.assertNotIn("TEAM123456", markdown)
        self.assertNotIn("K99RADPB9G", markdown)
        self.assertNotIn("BEGIN PRIVATE KEY", markdown)
        self.assertNotIn("sk-", markdown)

    def test_json_output_is_machine_readable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/launch_provider_input_handoff.py", "--json"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["repo"], "charlie2233/rork-hoopshighlights-ai_Final")
        self.assertTrue(any(item["name"] == "APP_STORE_CONNECT_API_KEY_BASE64" for item in payload["githubSecrets"]))
        self.assertTrue(any(item["name"] == "HOOPS_TERMS_OF_SERVICE_URL" for item in payload["githubVariables"]))
        self.assertTrue(any(item["name"] == "HOOPS_OPENAI_API_KEY" for item in payload["gcpSecretManagerSecrets"]))
        self.assertIn("staging / CLOUDFLARE_API_TOKEN", "\n".join(payload["cloudflareTokenRequirements"]))
        self.assertIn("Return only this non-secret status", payload["atlasAgentPrompt"])
        self.assertIn("GitHub Actions billing/spending/startability fixed", payload["atlasAgentPrompt"])
        self.assertTrue(any("billing/spending-limit" in item for item in payload["manualGates"]))
        self.assertIn("python3 scripts/configure_github_staging_public_variables.py", payload["verificationCommands"])
        self.assertIn(
            "python3 -m scripts.evaluate_team_highlight_accuracy artifacts/team_highlight_eval.json --json > artifacts/team_highlight_accuracy_report.json",
            payload["verificationCommands"],
        )
        self.assertIn(
            "python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_report.json",
            payload["verificationCommands"],
        )
        self.assertIn("python3 scripts/configure_github_staging_public_variables.py --apply", payload["verificationCommands"])
        self.assertIn("python3 scripts/staging_version_probe.py", payload["verificationCommands"])


if __name__ == "__main__":
    unittest.main()

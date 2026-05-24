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

        self.assertEqual(secret_names, set(REQUIRED_DEPLOY_SECRET_INPUTS) | set(REQUIRED_IOS_UPLOAD_SECRET_INPUTS))
        self.assertEqual(variable_names, set(REQUIRED_DEPLOY_VARIABLE_INPUTS) | set(REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS))
        self.assertEqual([item.name for item in handoff.localInputs], ["HOOPS_DEVELOPMENT_TEAM"])

    def test_markdown_uses_placeholders_without_secret_values(self) -> None:
        markdown = render_markdown(build_handoff())

        self.assertIn("gh secret set CLOUDFLARE_API_TOKEN", markdown)
        self.assertIn("gh variable set GCP_PROJECT_ID", markdown)
        self.assertIn("HOOPS_DEVELOPMENT_TEAM = <team-id>", markdown)
        self.assertIn("Do not paste secret values", markdown)
        self.assertNotIn("TEAM123456", markdown)
        self.assertNotIn("K99RADPB9G", markdown)
        self.assertNotIn("BEGIN PRIVATE KEY", markdown)

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
        self.assertIn("python3 scripts/staging_version_probe.py", payload["verificationCommands"])


if __name__ == "__main__":
    unittest.main()

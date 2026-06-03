import json
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

from scripts.launch_provider_input_handoff import build_cloudflare_token_form_guide, build_handoff, detect_current_ref, render_markdown
from scripts.submission_readiness_preflight import (
    REQUIRED_DEPLOY_SECRET_INPUTS,
    REQUIRED_DEPLOY_VARIABLE_INPUTS,
    REQUIRED_IOS_UPLOAD_SECRET_INPUTS,
    REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS,
)


class LaunchProviderInputHandoffTests(unittest.TestCase):
    def test_handoff_includes_every_required_provider_input(self) -> None:
        handoff = build_handoff(today=date(2026, 5, 29))

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
        self.assertEqual(handoff.cloudflareTokenFormGuide.accountId, "78fb4442e6e37b2c46d7e539c6e79172")
        self.assertEqual(handoff.cloudflareTokenFormGuide.startDate, "2026-05-29")
        self.assertEqual(handoff.cloudflareTokenFormGuide.endDate, "2026-08-27")
        self.assertIn("Workers Scripts: Edit", handoff.cloudflareTokenFormGuide.permissions)
        self.assertIn("Workers R2 Storage: Edit", handoff.cloudflareTokenFormGuide.permissions)
        self.assertTrue(any("missing Secret Manager secret is a repair action" in item for item in handoff.gcpSecretRepairPolicy))
        self.assertTrue(any("HOOPS_OPENAI_API_KEY" in item for item in handoff.gcpSecretRepairPolicy))
        self.assertTrue(any("Secret Manager Viewer" in item for item in handoff.gcpSecretRepairPolicy))
        self.assertEqual([item.name for item in handoff.localInputs], ["HOOPS_DEVELOPMENT_TEAM"])

    def test_markdown_uses_placeholders_without_secret_values(self) -> None:
        markdown = render_markdown(build_handoff(today=date(2026, 5, 29)))

        self.assertIn("gh secret set CLOUDFLARE_API_TOKEN", markdown)
        self.assertIn("Cloudflare Dashboard Form Guide", markdown)
        self.assertIn("HoopClips staging CI deploy", markdown)
        self.assertIn("TTL start date: `2026-05-29`", markdown)
        self.assertIn("TTL end date: `2026-08-27`", markdown)
        self.assertIn("Workers R2 Storage: Edit", markdown)
        self.assertIn("gh variable set GCP_PROJECT_ID", markdown)
        self.assertIn("gcloud secrets describe HOOPS_OPENAI_API_KEY", markdown)
        self.assertIn("gcloud secrets versions add HOOPS_OPENAI_API_KEY", markdown)
        self.assertIn("--format='value(state)'", markdown)
        self.assertIn("\"ENABLED\"", markdown)
        self.assertIn("Atlas / Browser Agent Prompt", markdown)
        self.assertIn("GCP Secret Repair Policy", markdown)
        self.assertIn("A missing Secret Manager secret is a repair action", markdown)
        self.assertIn("Secret Manager Viewer", markdown)
        self.assertIn("metadata and latest-version state checks", markdown)
        self.assertIn("HOOPS_OPENAI_API_KEY present and enabled: yes/no", markdown)
        self.assertIn("Do not stop after reporting the missing secret", markdown)
        self.assertIn("deploy service account has Secret Manager Viewer metadata access: yes/no", markdown)
        self.assertIn("Cloud deploy credential check triggered: yes/no", markdown)
        self.assertIn("GitHub run URL:", markdown)
        self.assertIn("Final conclusion:", markdown)
        self.assertIn("Do not run operation=preflight or operation=deploy yet", markdown)
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
            [sys.executable, "scripts/launch_provider_input_handoff.py", "--json", "--ref", "codex/test-ref"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(result.stdout)

        self.assertEqual(payload["repo"], "charlie2233/rork-hoopshighlights-ai_Final")
        self.assertEqual(payload["ref"], "codex/test-ref")
        self.assertIn("expectedHeadSha", payload)
        self.assertTrue(any(item["name"] == "APP_STORE_CONNECT_API_KEY_BASE64" for item in payload["githubSecrets"]))
        self.assertTrue(any(item["name"] == "HOOPS_TERMS_OF_SERVICE_URL" for item in payload["githubVariables"]))
        self.assertTrue(any(item["name"] == "HOOPS_OPENAI_API_KEY" for item in payload["gcpSecretManagerSecrets"]))
        self.assertIn("staging / CLOUDFLARE_API_TOKEN", "\n".join(payload["cloudflareTokenRequirements"]))
        self.assertEqual(payload["cloudflareTokenFormGuide"]["tokenName"], "HoopClips staging CI deploy")
        self.assertEqual(payload["cloudflareTokenFormGuide"]["accountId"], "78fb4442e6e37b2c46d7e539c6e79172")
        self.assertIn("Workers Scripts: Edit", payload["cloudflareTokenFormGuide"]["permissions"])
        self.assertIn("TTL start date", payload["atlasAgentPrompt"])
        self.assertIn("Return only this non-secret status", payload["atlasAgentPrompt"])
        self.assertIn("HOOPS_OPENAI_API_KEY present and enabled: yes/no", payload["atlasAgentPrompt"])
        self.assertIn("Do not stop after reporting the missing secret", payload["atlasAgentPrompt"])
        self.assertIn("Cloud deploy credential check triggered: yes/no", payload["atlasAgentPrompt"])
        self.assertIn("GitHub run URL:", payload["atlasAgentPrompt"])
        self.assertIn("Expected workflow head SHA for current-tip proof:", payload["atlasAgentPrompt"])
        self.assertIn("GitHub run head SHA:", payload["atlasAgentPrompt"])
        self.assertIn("GitHub run head SHA matches expected current SHA: yes/no", payload["atlasAgentPrompt"])
        self.assertIn("Do not count an older successful run as current proof", payload["atlasAgentPrompt"])
        self.assertIn("Final conclusion:", payload["atlasAgentPrompt"])
        self.assertIn("Secret Manager Viewer", payload["atlasAgentPrompt"])
        self.assertIn("deploy service account has Secret Manager Viewer metadata access: yes/no", payload["atlasAgentPrompt"])
        self.assertIn(
            "gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref codex/test-ref -f operation=credential-check",
            payload["atlasAgentPrompt"],
        )
        self.assertIn("Do not run operation=preflight or operation=deploy yet", payload["atlasAgentPrompt"])
        self.assertTrue(any("HOOPS_OPENAI_API_KEY" in item for item in payload["gcpSecretRepairPolicy"]))
        self.assertFalse(any("billing/spending-limit" in item for item in payload["manualGates"]))
        self.assertIn("python3 scripts/configure_github_staging_public_variables.py", payload["verificationCommands"])
        self.assertIn(
            "python3 scripts/build_launch_team_accuracy_report.py --manifest artifacts/team_highlight_accuracy_manifest.json --eval-output artifacts/team_highlight_eval.json --report-output artifacts/team_highlight_accuracy_report.json --json",
            payload["verificationCommands"],
        )
        self.assertIn(
            "python3 -m scripts.evaluate_team_highlight_accuracy artifacts/team_highlight_eval.json --json > artifacts/team_highlight_accuracy_report.json",
            payload["verificationCommands"],
        )
        self.assertIn(
            "python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_report.json",
            payload["verificationCommands"],
        )
        self.assertIn("python3 scripts/configure_github_staging_public_variables.py --apply", payload["verificationCommands"])
        self.assertTrue(any(command.startswith("python3 scripts/staging_version_probe.py --expected-git-sha ") for command in payload["verificationCommands"]))
        workflow_commands = "\n".join(command for command in payload["verificationCommands"] if command.startswith("gh workflow run"))
        self.assertIn("cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref codex/test-ref -f operation=credential-check", workflow_commands)
        self.assertIn("cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref codex/test-ref -f operation=preflight", workflow_commands)
        self.assertIn("--ref codex/test-ref", workflow_commands)
        self.assertNotIn("--ref main", workflow_commands)
        self.assertIn("workflow ref codex/test-ref", payload["atlasAgentPrompt"])

    def test_handoff_defaults_to_current_branch_ref(self) -> None:
        current_ref = detect_current_ref()
        handoff = build_handoff()

        self.assertEqual(handoff.ref, current_ref)
        workflow_commands = "\n".join(command for command in handoff.verificationCommands if command.startswith("gh workflow run"))
        self.assertIn(f"--ref {current_ref}", workflow_commands)

    def test_cloudflare_form_guide_uses_beta_ttl_without_secret_values(self) -> None:
        guide = build_cloudflare_token_form_guide(today=date(2026, 5, 29))

        self.assertEqual(guide.tokenName, "HoopClips staging CI deploy")
        self.assertEqual(guide.startDate, "2026-05-29")
        self.assertEqual(guide.endDate, "2026-08-27")
        self.assertIn("D1: Edit", guide.permissions)
        self.assertIn("do not add DNS Edit", guide.zoneResource)
        serialized = json.dumps(guide.__dict__)
        self.assertNotIn("BEGIN PRIVATE KEY", serialized)
        self.assertNotIn("sk-", serialized)


if __name__ == "__main__":
    unittest.main()

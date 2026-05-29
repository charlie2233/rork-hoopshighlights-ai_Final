#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.submission_readiness_preflight import (
    REQUIRED_DEPLOY_SECRET_INPUTS,
    REQUIRED_DEPLOY_VARIABLE_INPUTS,
    REQUIRED_IOS_UPLOAD_SECRET_INPUTS,
    REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS,
)


REPO = "charlie2233/rork-hoopshighlights-ai_Final"
ENVIRONMENT = "staging"
GCP_PROJECT = "hoopsclips-9d38f"
LOCAL_SECRETS_PATH = "ios/HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig"
REQUIRED_SECRET_MANAGER_SECRETS = [
    "HOOPS_EDITING_SERVICE_SECRET",
    "HOOPS_R2_ACCESS_KEY_ID",
    "HOOPS_R2_SECRET_ACCESS_KEY",
    "HOOPS_OPENAI_API_KEY",
]
CLOUDFLARE_TOKEN_REQUIREMENTS = [
    "Store only as GitHub environment secret staging / CLOUDFLARE_API_TOKEN.",
    "Scope to the HoopClips Cloudflare account.",
    "Must authenticate `npx wrangler whoami` in GitHub Actions.",
    "Needs Workers Scripts Edit and Account Settings Read for staging deploy checks.",
    "Needs R2 Edit when deploy preflight verifies bucket bindings or artifacts.",
]
GITHUB_ACTIONS_STARTABILITY_GATE = (
    "Fix GitHub Actions billing/spending-limit state so Cloud Edit Deploy Preflight "
    "and iOS Internal TestFlight Upload runs can start on GitHub-hosted runners."
)


@dataclass(frozen=True)
class HandoffInput:
    name: str
    kind: Literal["secret", "variable", "local", "gcp-secret"]
    scope: str
    command: str
    note: str


@dataclass(frozen=True)
class Handoff:
    repo: str
    environment: str
    githubSecrets: list[HandoffInput]
    githubVariables: list[HandoffInput]
    gcpSecretManagerSecrets: list[HandoffInput]
    cloudflareTokenRequirements: list[str]
    localInputs: list[HandoffInput]
    verificationCommands: list[str]
    manualGates: list[str]
    atlasAgentPrompt: str


def build_handoff() -> Handoff:
    github_secrets = [
        HandoffInput(
            name=name,
            kind="secret",
            scope=f"GitHub environment: {ENVIRONMENT}",
            command=f"gh secret set {name} --repo {REPO} --env {ENVIRONMENT}",
            note="Paste the value only into the command prompt or GitHub UI; do not put it in chat or docs.",
        )
        for name in (*REQUIRED_DEPLOY_SECRET_INPUTS, *REQUIRED_IOS_UPLOAD_SECRET_INPUTS)
    ]
    github_variables = [
        HandoffInput(
            name=name,
            kind="variable",
            scope=f"GitHub environment: {ENVIRONMENT}",
            command=f"gh variable set {name} --repo {REPO} --env {ENVIRONMENT} --body '<value>'",
            note="Replace <value> locally before running; keep provider-specific IDs out of chat transcripts.",
        )
        for name in (*REQUIRED_DEPLOY_VARIABLE_INPUTS, *REQUIRED_IOS_UPLOAD_VARIABLE_INPUTS)
    ]
    local_inputs = [
        HandoffInput(
            name="HOOPS_DEVELOPMENT_TEAM",
            kind="local",
            scope=LOCAL_SECRETS_PATH,
            command=f"printf 'HOOPS_DEVELOPMENT_TEAM = <team-id>\\n' >> {LOCAL_SECRETS_PATH}",
            note="Use the Apple Team ID locally for archive/signing checks. Do not commit LocalSecrets.xcconfig.",
        )
    ]
    gcp_secret_manager_secrets = [
        HandoffInput(
            name=name,
            kind="gcp-secret",
            scope=f"GCP Secret Manager project: {GCP_PROJECT}",
            command=(
                f"(gcloud secrets describe {name} --project={GCP_PROJECT} >/dev/null "
                f"|| gcloud secrets create {name} --project={GCP_PROJECT} --replication-policy=automatic) "
                f"&& (gcloud secrets versions describe latest --secret={name} --project={GCP_PROJECT} "
                f"--format='value(state)' >/dev/null || (printf 'Enter value for {name}: ' >&2; "
                f"read -rs SECRET_VALUE; printf '\\n' >&2; printf '%s' \"$SECRET_VALUE\" "
                f"| gcloud secrets versions add {name} --project={GCP_PROJECT} --data-file=-))"
            ),
            note="Create or repair the Secret Manager secret from an operator-held value; do not paste values into chat, docs, or logs.",
        )
        for name in REQUIRED_SECRET_MANAGER_SECRETS
    ]
    verification_commands = [
        "python3 scripts/configure_github_staging_public_variables.py",
        "python3 -m scripts.evaluate_team_highlight_accuracy artifacts/team_highlight_eval.json --json > artifacts/team_highlight_accuracy_report.json",
        "python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_report.json",
        "python3 scripts/configure_github_staging_public_variables.py --apply",
        "gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight",
        "gh workflow run ios-testflight-upload.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight",
        "gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=deploy",
        "python3 scripts/staging_version_probe.py",
        "python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_report.json",
    ]
    manual_gates = [
        GITHUB_ACTIONS_STARTABILITY_GATE,
        "Unlock and trust the wired iPhone, then confirm `xcrun devicectl list devices` shows an available iPhone.",
        "Repair GCP Secret Manager access for the staging deploy identity before rerunning deploy preflight.",
        "Replace or rescope staging / CLOUDFLARE_API_TOKEN before rerunning deploy preflight.",
        "After staging Worker deploy, verify `GET /v1/editing/version` returns AI Edit feature flags through the Worker.",
        "Create a signed archive/IPA through the iOS internal TestFlight workflow, then run the installed TestFlight smoke.",
        "Do not submit to Apple until upload, processing, installed smoke, cloud render, revision, preview, and share/open-in are all proven.",
    ]
    atlas_prompt = build_atlas_agent_prompt()
    return Handoff(
        repo=REPO,
        environment=ENVIRONMENT,
        githubSecrets=github_secrets,
        githubVariables=github_variables,
        gcpSecretManagerSecrets=gcp_secret_manager_secrets,
        cloudflareTokenRequirements=CLOUDFLARE_TOKEN_REQUIREMENTS,
        localInputs=local_inputs,
        verificationCommands=verification_commands,
        manualGates=manual_gates,
        atlasAgentPrompt=atlas_prompt,
    )


def render_markdown(handoff: Handoff) -> str:
    lines: list[str] = [
        "# HoopClips Provider Input Handoff",
        "",
        f"Repository: `{handoff.repo}`",
        f"GitHub environment: `{handoff.environment}`",
        "",
        "Use these commands locally or in the provider UI. Do not paste secret values into chat, docs, commits, logs, or screenshots.",
        "",
        "## GitHub Environment Secrets",
        "",
    ]
    lines.extend(render_input_rows(handoff.githubSecrets))
    lines.extend(["", "## GitHub Environment Variables", ""])
    lines.extend(render_input_rows(handoff.githubVariables))
    lines.extend(["", "## GCP Secret Manager Secrets", ""])
    lines.extend(render_input_rows(handoff.gcpSecretManagerSecrets))
    lines.extend(["", "## Cloudflare Token Requirements", ""])
    lines.extend(f"- {requirement}" for requirement in handoff.cloudflareTokenRequirements)
    lines.extend(["", "## Local Signing Input", ""])
    lines.extend(render_input_rows(handoff.localInputs))
    lines.extend(["", "## Verification Commands", ""])
    lines.extend(f"- `{command}`" for command in handoff.verificationCommands)
    lines.extend(["", "## Manual Gates", ""])
    lines.extend(f"- {gate}" for gate in handoff.manualGates)
    lines.extend(["", "## Atlas / Browser Agent Prompt", "", "```text", handoff.atlasAgentPrompt.rstrip(), "```"])
    lines.append("")
    return "\n".join(lines)


def render_input_rows(inputs: list[HandoffInput]) -> list[str]:
    rows: list[str] = []
    for item in inputs:
        rows.extend(
            [
                f"- `{item.name}`",
                f"  Command: `{item.command}`",
                f"  Note: {item.note}",
            ]
        )
    return rows


def build_atlas_agent_prompt() -> str:
    secret_list = "\n".join(f"   - {name}" for name in REQUIRED_SECRET_MANAGER_SECRETS)
    cloudflare_requirements = "\n".join(f"   - {item}" for item in CLOUDFLARE_TOKEN_REQUIREMENTS)
    return f"""For repo {REPO}, GitHub environment {ENVIRONMENT}, repair only provider-side launch deploy blockers.

Do not paste, reveal, summarize, screenshot, or return private key material, API tokens, R2 credentials, OpenAI keys, Secret Manager secret values, or full presigned URLs.

1. In GCP project {GCP_PROJECT}, verify these Secret Manager secrets exist and have an enabled latest version:
{secret_list}
2. In GitHub billing/settings for the repo owner, verify Actions GitHub-hosted runners can start and repair any failed-payment or spending-limit blocker.
3. Ensure the GitHub Actions deploy service account configured in staging / GCP_DEPLOY_SERVICE_ACCOUNT has Secret Manager Secret Accessor for those secrets.
4. In Cloudflare, create or replace a scoped API token:
{cloudflare_requirements}
5. Set that token directly as GitHub environment secret staging / CLOUDFLARE_API_TOKEN for {REPO}.
6. Return only this non-secret status:
   - GCP secrets present and enabled: yes/no
   - GitHub Actions billing/spending/startability fixed: yes/no
   - deploy service account has Secret Manager access: yes/no
   - Cloudflare token replaced or rescope completed: yes/no
   - GitHub staging CLOUDFLARE_API_TOKEN updated: yes/no
   - Any provider-side blocker that remains, by name only
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a safe HoopClips provider-input setup handoff.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable handoff data.")
    parser.add_argument("--output", type=Path, help="Optional file path to write the handoff.")
    args = parser.parse_args()

    handoff = build_handoff()
    output = json.dumps(asdict(handoff), indent=2, sort_keys=True) + "\n" if args.json else render_markdown(handoff)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="" if output.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

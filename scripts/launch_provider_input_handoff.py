#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
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
CLOUDFLARE_ACCOUNT_ID = "78fb4442e6e37b2c46d7e539c6e79172"
CLOUDFLARE_TOKEN_TTL_DAYS = 90
LOCAL_SECRETS_PATH = "ios/HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig"
REQUIRED_SECRET_MANAGER_SECRETS = [
    "HOOPS_EDITING_SERVICE_SECRET",
    "HOOPS_R2_ACCESS_KEY_ID",
    "HOOPS_R2_SECRET_ACCESS_KEY",
    "HOOPS_OPENAI_API_KEY",
]
CLOUDFLARE_TOKEN_REQUIREMENTS = [
    "Store only as GitHub environment secret staging / CLOUDFLARE_API_TOKEN.",
    f"Scope to the HoopClips Cloudflare account `{CLOUDFLARE_ACCOUNT_ID}`.",
    "Must authenticate `npx wrangler whoami` in GitHub Actions.",
    "Needs Workers Scripts Edit and Account Settings Read for staging deploy checks.",
    "Needs Workers R2 Storage Edit when deploy preflight verifies bucket bindings or artifacts.",
    "Needs D1 Edit for the staging D1 binding used by Wrangler deploys and migrations.",
]
GCP_SECRET_REPAIR_POLICY = [
    "A missing Secret Manager secret is a repair action, not a terminal failure: create it and add a latest ENABLED version from an operator-held value.",
    "For HOOPS_OPENAI_API_KEY, store the OpenAI key only in GCP Secret Manager; do not mirror it into GitHub secrets, chat, docs, screenshots, or logs.",
    "After repair, verify each required secret's latest version state is exactly ENABLED without printing secret payloads.",
    "After secret versions are enabled, verify the staging deploy service account has Secret Manager Secret Accessor for the required secret names.",
]


@dataclass(frozen=True)
class HandoffInput:
    name: str
    kind: Literal["secret", "variable", "local", "gcp-secret"]
    scope: str
    command: str
    note: str


@dataclass(frozen=True)
class CloudflareTokenFormGuide:
    tokenName: str
    accountId: str
    accountResource: str
    zoneResource: str
    permissions: list[str]
    startDate: str
    endDate: str
    githubSecret: str
    notes: list[str]


@dataclass(frozen=True)
class Handoff:
    repo: str
    environment: str
    ref: str
    githubSecrets: list[HandoffInput]
    githubVariables: list[HandoffInput]
    gcpSecretManagerSecrets: list[HandoffInput]
    gcpSecretRepairPolicy: list[str]
    cloudflareTokenRequirements: list[str]
    cloudflareTokenFormGuide: CloudflareTokenFormGuide
    localInputs: list[HandoffInput]
    verificationCommands: list[str]
    manualGates: list[str]
    atlasAgentPrompt: str


def detect_current_ref() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT_FOR_IMPORTS,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "main"
    ref = result.stdout.strip()
    return ref if ref and ref != "HEAD" else "main"


def detect_current_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT_FOR_IMPORTS,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    sha = result.stdout.strip()
    return sha or None


def build_cloudflare_token_form_guide(today: date | None = None) -> CloudflareTokenFormGuide:
    start = today or date.today()
    end = start + timedelta(days=CLOUDFLARE_TOKEN_TTL_DAYS)
    return CloudflareTokenFormGuide(
        tokenName="HoopClips staging CI deploy",
        accountId=CLOUDFLARE_ACCOUNT_ID,
        accountResource=(
            "Include only the Cloudflare account that owns Worker "
            "`hoopsclips-control-plane-staging` and R2 buckets "
            "`hoopsclips-uploads-staging` / `hoopsclips-results-staging`."
        ),
        zoneResource=(
            "No zone permission is needed for the current workers.dev staging route. "
            "If Cloudflare requires a Zone Resources selection, choose All zones only as a form-required fallback; do not add DNS Edit."
        ),
        permissions=[
            "Account Settings: Read",
            "Workers Scripts: Edit",
            "Workers R2 Storage: Edit",
            "D1: Edit",
            "Workers Tail: Read (optional, only for log-streaming smoke)",
        ],
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        githubSecret=f"{ENVIRONMENT} / CLOUDFLARE_API_TOKEN",
        notes=[
            "Set the start date to the local creation date and the end date to the 90-day internal beta rotation date.",
            "Copy the token once directly into GitHub Actions environment secret staging / CLOUDFLARE_API_TOKEN.",
            "Do not paste, screenshot, summarize, or return the token value.",
            "If the dashboard requires broader account or zone selection, stop and return the blocker by name only.",
        ],
    )


def build_handoff(ref: str | None = None, today: date | None = None) -> Handoff:
    workflow_ref = ref or detect_current_ref()
    workflow_ref_arg = shlex.quote(workflow_ref)
    workflow_sha = detect_current_sha()
    staging_probe_command = "python3 scripts/staging_version_probe.py"
    if workflow_sha:
        staging_probe_command = f"{staging_probe_command} --expected-git-sha {shlex.quote(workflow_sha)}"
    cloudflare_form_guide = build_cloudflare_token_form_guide(today=today)
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
                f"&& (test \"$(gcloud secrets versions describe latest --secret={name} --project={GCP_PROJECT} "
                f"--format='value(state)' 2>/dev/null)\" = \"ENABLED\" || (printf 'Enter value for {name}: ' >&2; "
                f"read -rs SECRET_VALUE; printf '\\n' >&2; printf '%s' \"$SECRET_VALUE\" "
                f"| gcloud secrets versions add {name} --project={GCP_PROJECT} --data-file=-))"
            ),
            note="Create or repair the Secret Manager secret from an operator-held value; do not paste values into chat, docs, or logs.",
        )
        for name in REQUIRED_SECRET_MANAGER_SECRETS
    ]
    verification_commands = [
        "python3 scripts/configure_github_staging_public_variables.py",
        "python3 scripts/build_launch_team_accuracy_report.py --manifest artifacts/team_highlight_accuracy_manifest.json --eval-output artifacts/team_highlight_eval.json --report-output artifacts/team_highlight_accuracy_report.json --json",
        "python3 -m scripts.evaluate_team_highlight_accuracy artifacts/team_highlight_eval.json --json > artifacts/team_highlight_accuracy_report.json",
        "python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_report.json",
        "python3 scripts/configure_github_staging_public_variables.py --apply",
        f"gh workflow run cloud-edit-deploy-preflight.yml --repo {REPO} --ref {workflow_ref_arg} -f operation=preflight",
        f"gh workflow run ios-testflight-upload.yml --repo {REPO} --ref {workflow_ref_arg} -f operation=preflight",
        f"gh workflow run cloud-edit-deploy-preflight.yml --repo {REPO} --ref {workflow_ref_arg} -f operation=deploy",
        staging_probe_command,
        "python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_report.json",
    ]
    manual_gates = [
        "Unlock and trust the wired iPhone, then confirm `xcrun devicectl list devices` shows an available iPhone.",
        "Repair GCP Secret Manager access for the staging deploy identity before rerunning deploy preflight.",
        "Replace or rescope staging / CLOUDFLARE_API_TOKEN before rerunning deploy preflight.",
        "After staging Worker deploy, verify `GET /v1/editing/version` returns AI Edit feature flags through the Worker.",
        "Create a signed archive/IPA through the iOS internal TestFlight workflow, then run the installed TestFlight smoke.",
        "Do not submit to Apple until upload, processing, installed smoke, cloud render, revision, preview, and share/open-in are all proven.",
    ]
    atlas_prompt = build_atlas_agent_prompt(workflow_ref, cloudflare_form_guide)
    return Handoff(
        repo=REPO,
        environment=ENVIRONMENT,
        ref=workflow_ref,
        githubSecrets=github_secrets,
        githubVariables=github_variables,
        gcpSecretManagerSecrets=gcp_secret_manager_secrets,
        gcpSecretRepairPolicy=GCP_SECRET_REPAIR_POLICY,
        cloudflareTokenRequirements=CLOUDFLARE_TOKEN_REQUIREMENTS,
        cloudflareTokenFormGuide=cloudflare_form_guide,
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
        f"GitHub ref for verification workflows: `{handoff.ref}`",
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
    lines.extend(["", "## GCP Secret Repair Policy", ""])
    lines.extend(f"- {policy}" for policy in handoff.gcpSecretRepairPolicy)
    lines.extend(["", "## Cloudflare Token Requirements", ""])
    lines.extend(f"- {requirement}" for requirement in handoff.cloudflareTokenRequirements)
    lines.extend(["", "## Cloudflare Dashboard Form Guide", ""])
    lines.extend(render_cloudflare_form_guide(handoff.cloudflareTokenFormGuide))
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


def render_cloudflare_form_guide(guide: CloudflareTokenFormGuide) -> list[str]:
    rows = [
        f"- Token name: `{guide.tokenName}`",
        f"- Account ID: `{guide.accountId}`",
        f"- Account resources: {guide.accountResource}",
        f"- Zone resources: {guide.zoneResource}",
        f"- TTL start date: `{guide.startDate}`",
        f"- TTL end date: `{guide.endDate}`",
        f"- GitHub secret target: `{guide.githubSecret}`",
        "- Permissions:",
    ]
    rows.extend(f"  - {permission}" for permission in guide.permissions)
    rows.append("- Notes:")
    rows.extend(f"  - {note}" for note in guide.notes)
    return rows


def build_atlas_agent_prompt(ref: str, cloudflare_guide: CloudflareTokenFormGuide) -> str:
    secret_list = "\n".join(f"   - {name}" for name in REQUIRED_SECRET_MANAGER_SECRETS)
    cloudflare_requirements = "\n".join(f"   - {item}" for item in CLOUDFLARE_TOKEN_REQUIREMENTS)
    cloudflare_permissions = "\n".join(f"   - {item}" for item in cloudflare_guide.permissions)
    cloudflare_notes = "\n".join(f"   - {item}" for item in cloudflare_guide.notes)
    return f"""For repo {REPO}, GitHub environment {ENVIRONMENT}, repair only provider-side launch deploy blockers.
Use GitHub Actions workflow ref {ref} for verification/deploy reruns, not stale main, unless the operator explicitly asks to validate main.

Do not paste, reveal, summarize, screenshot, or return private key material, API tokens, R2 credentials, OpenAI keys, Secret Manager secret values, or full presigned URLs.

1. In GCP project {GCP_PROJECT}, verify these Secret Manager secrets exist and have an enabled latest version:
{secret_list}
   If a secret is missing, including HOOPS_OPENAI_API_KEY, create it and add a latest ENABLED version from an operator-held value. Do not stop after reporting the missing secret unless the operator-held value is unavailable.
   Never print or return the secret value. For HOOPS_OPENAI_API_KEY, store it only in GCP Secret Manager.
2. Ensure the GitHub Actions deploy service account configured in staging / GCP_DEPLOY_SERVICE_ACCOUNT has Secret Manager Secret Accessor for those secrets.
3. In Cloudflare, create or replace a scoped API token:
{cloudflare_requirements}
   Dashboard form values:
   - Token name: {cloudflare_guide.tokenName}
   - Account ID/resource: {cloudflare_guide.accountId}
   - Account resources: {cloudflare_guide.accountResource}
   - Zone resources: {cloudflare_guide.zoneResource}
   - TTL start date: {cloudflare_guide.startDate}
   - TTL end date: {cloudflare_guide.endDate}
   Permissions:
{cloudflare_permissions}
   Notes:
{cloudflare_notes}
4. Set that token directly as GitHub environment secret staging / CLOUDFLARE_API_TOKEN for {REPO}.
5. Return only this non-secret status:
   - HOOPS_EDITING_SERVICE_SECRET present and enabled: yes/no
   - HOOPS_R2_ACCESS_KEY_ID present and enabled: yes/no
   - HOOPS_R2_SECRET_ACCESS_KEY present and enabled: yes/no
   - HOOPS_OPENAI_API_KEY present and enabled: yes/no
   - all required GCP secrets present and enabled: yes/no
   - deploy service account has Secret Manager access: yes/no
   - Cloudflare token replaced or rescope completed: yes/no
   - GitHub staging CLOUDFLARE_API_TOKEN updated: yes/no
   - Any provider-side blocker that remains, by name only
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a safe HoopClips provider-input setup handoff.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable handoff data.")
    parser.add_argument("--output", type=Path, help="Optional file path to write the handoff.")
    parser.add_argument("--ref", help="GitHub ref to use in verification workflow commands. Defaults to the current branch.")
    args = parser.parse_args()

    handoff = build_handoff(ref=args.ref)
    output = json.dumps(asdict(handoff), indent=2, sort_keys=True) + "\n" if args.json else render_markdown(handoff)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="" if output.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

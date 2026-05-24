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
LOCAL_SECRETS_PATH = "ios/HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig"


@dataclass(frozen=True)
class HandoffInput:
    name: str
    kind: Literal["secret", "variable", "local"]
    scope: str
    command: str
    note: str


@dataclass(frozen=True)
class Handoff:
    repo: str
    environment: str
    githubSecrets: list[HandoffInput]
    githubVariables: list[HandoffInput]
    localInputs: list[HandoffInput]
    verificationCommands: list[str]
    manualGates: list[str]


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
    verification_commands = [
        "python3 scripts/configure_github_staging_public_variables.py",
        "python3 scripts/submission_readiness_preflight.py",
        "python3 scripts/configure_github_staging_public_variables.py --apply",
        "gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight",
        "gh workflow run ios-testflight-upload.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight",
        "gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=deploy",
        "python3 scripts/staging_version_probe.py",
        "python3 scripts/submission_readiness_preflight.py",
    ]
    manual_gates = [
        "Unlock and trust the wired iPhone, then confirm `xcrun devicectl list devices` shows an available iPhone.",
        "After staging Worker deploy, verify `GET /v1/editing/version` returns AI Edit feature flags through the Worker.",
        "Create a signed archive/IPA through the iOS internal TestFlight workflow, then run the installed TestFlight smoke.",
        "Do not submit to Apple until upload, processing, installed smoke, cloud render, revision, preview, and share/open-in are all proven.",
    ]
    return Handoff(
        repo=REPO,
        environment=ENVIRONMENT,
        githubSecrets=github_secrets,
        githubVariables=github_variables,
        localInputs=local_inputs,
        verificationCommands=verification_commands,
        manualGates=manual_gates,
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
    lines.extend(["", "## Local Signing Input", ""])
    lines.extend(render_input_rows(handoff.localInputs))
    lines.extend(["", "## Verification Commands", ""])
    lines.extend(f"- `{command}`" for command in handoff.verificationCommands)
    lines.extend(["", "## Manual Gates", ""])
    lines.extend(f"- {gate}" for gate in handoff.manualGates)
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

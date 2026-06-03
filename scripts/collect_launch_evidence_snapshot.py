#!/usr/bin/env python3
"""Collect a secret-safe HoopClips launch evidence snapshot.

This helper is intentionally conservative: it records branch state, workflow IDs,
production variable presence, release-preflight status, and label-review counts.
It does not print secrets, token values, private key contents, signing material,
presigned URLs, storage object URLs, private video contents, or rendered MP4s.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BRANCH = "codex/phase-launch-proof-next"
DEFAULT_LABEL_STATUS = Path("artifacts/team_highlight_labeling_bundle/label_status.json")
REQUIRED_PRODUCTION_VARIABLES = [
    "HOOPS_CLOUD_ANALYSIS_BASE_URL",
    "HOOPS_CLOUD_EDIT_BASE_URL",
]
SAFE_SUPPORTING_VARIABLES = [
    "HOOPS_PRIVACY_POLICY_URL",
    "HOOPS_TERMS_OF_SERVICE_URL",
]


def run(args: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def run_text(args: list[str], cwd: Path) -> str | None:
    code, stdout, _ = run(args, cwd)
    return stdout if code == 0 else None


def run_json(args: list[str], cwd: Path) -> Any | None:
    text = run_text(args, cwd)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def git_snapshot(repo_root: Path) -> dict[str, Any]:
    head = run_text(["git", "rev-parse", "HEAD"], repo_root)
    branch = run_text(["git", "branch", "--show-current"], repo_root)
    upstream = run_text(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo_root)
    ahead_behind = run_text(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], repo_root)
    tracked_changes = run_text(["git", "diff", "--name-status"], repo_root) or ""
    staged_changes = run_text(["git", "diff", "--cached", "--name-status"], repo_root) or ""
    untracked = run_text(["git", "ls-files", "-o", "--exclude-standard"], repo_root) or ""
    ahead = behind = None
    if ahead_behind:
        parts = ahead_behind.split()
        if len(parts) == 2:
            ahead, behind = parts

    return {
        "head": head,
        "headShort": head[:7] if head else None,
        "branch": branch,
        "upstream": upstream,
        "ahead": int(ahead) if ahead is not None and ahead.isdigit() else None,
        "behind": int(behind) if behind is not None and behind.isdigit() else None,
        "hasTrackedChanges": bool(tracked_changes.strip()),
        "hasStagedChanges": bool(staged_changes.strip()),
        "untrackedFiles": [line for line in untracked.splitlines() if line],
    }


def branch_workflows(repo_root: Path, branch: str, limit: int) -> list[dict[str, Any]]:
    runs = run_json(
        [
            "gh",
            "run",
            "list",
            "--branch",
            branch,
            "--limit",
            str(limit),
            "--json",
            "databaseId,status,conclusion,headSha,workflowName,createdAt,event",
        ],
        repo_root,
    )
    if isinstance(runs, list):
        return runs
    return []


def release_preflight_runs(repo_root: Path, limit: int) -> list[dict[str, Any]]:
    runs = run_json(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            "release-secrets-preflight.yml",
            "--limit",
            str(limit),
            "--json",
            "databaseId,status,conclusion,headSha,headBranch,createdAt,event",
        ],
        repo_root,
    )
    if isinstance(runs, list):
        return runs
    return []


def production_variable_snapshot(repo_root: Path) -> dict[str, Any]:
    code, stdout, _ = run(["gh", "variable", "list", "--env", "production"], repo_root)
    names: list[str] = []
    if code == 0:
        for line in stdout.splitlines():
            parts = line.split("\t")
            if parts and parts[0]:
                names.append(parts[0])

    return {
        "visibleNames": sorted(names),
        "requiredPresence": {name: name in names for name in REQUIRED_PRODUCTION_VARIABLES},
        "supportingPresence": {name: name in names for name in SAFE_SUPPORTING_VARIABLES},
        "missingRequired": [name for name in REQUIRED_PRODUCTION_VARIABLES if name not in names],
    }


def label_status_snapshot(repo_root: Path, label_status_path: Path) -> dict[str, Any]:
    path = label_status_path if label_status_path.is_absolute() else repo_root / label_status_path
    if not path.exists():
        return {"path": str(label_status_path), "exists": False}
    payload = json.loads(path.read_text())
    return {
        "path": str(label_status_path),
        "exists": True,
        "status": payload.get("status"),
        "clipCount": payload.get("clipCount"),
        "completeClipCount": payload.get("completeClipCount"),
        "incompleteClipCount": payload.get("incompleteClipCount"),
        "launchEvidenceEligible": payload.get("launchEvidenceEligible"),
        "missingFieldCounts": payload.get("missingFieldCounts", {}),
    }


def latest_success_for_head(runs: list[dict[str, Any]], workflow_name: str, head: str | None) -> dict[str, Any] | None:
    if not head:
        return None
    for run_item in runs:
        if run_item.get("workflowName") == workflow_name and run_item.get("headSha") == head:
            if run_item.get("status") == "completed" and run_item.get("conclusion") == "success":
                return run_item
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a secret-safe launch evidence snapshot.")
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Launch branch to inspect.")
    parser.add_argument("--workflow-limit", type=int, default=12, help="Number of branch workflow runs to inspect.")
    parser.add_argument("--label-status", type=Path, default=DEFAULT_LABEL_STATUS, help="Label status JSON path.")
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    git = git_snapshot(repo_root)
    runs = branch_workflows(repo_root, args.branch, args.workflow_limit)
    release_runs = release_preflight_runs(repo_root, 5)
    production_variables = production_variable_snapshot(repo_root)
    labels = label_status_snapshot(repo_root, args.label_status)

    head = git.get("head")
    cloud_run = latest_success_for_head(runs, "Cloud Edit Deploy Preflight", head)
    ios_run = latest_success_for_head(runs, "iOS Internal TestFlight Upload", head)
    latest_release = release_runs[0] if release_runs else None

    snapshot = {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "secretSafe": True,
        "repoRoot": str(repo_root),
        "branch": args.branch,
        "git": git,
        "supportingBranchProof": {
            "cloudEditDeployPreflightSuccessForHead": cloud_run,
            "iosInternalTestFlightCodecheckSuccessForHead": ios_run,
            "currentHeadHasSupportingProof": bool(cloud_run and ios_run),
            "note": "Supporting proof only; not production cutover, signed upload, installed smoke, or human-reviewed accuracy proof.",
        },
        "productionVariables": production_variables,
        "releaseSecretsPreflight": {
            "latest": latest_release,
            "isPassing": bool(latest_release and latest_release.get("status") == "completed" and latest_release.get("conclusion") == "success"),
        },
        "labelStatus": labels,
        "remainingRequiredEvidence": {
            "productionCloudUrls": bool(production_variables.get("missingRequired")),
            "releaseSecretsPreflight": not bool(latest_release and latest_release.get("status") == "completed" and latest_release.get("conclusion") == "success"),
            "humanReviewedLabels": not bool(labels.get("launchEvidenceEligible")),
            "signedArchiveUpload": True,
            "installedTestFlightSmoke": True,
        },
        "redactionReminder": "Do not add secrets, tokens, private keys, base64 values, presigned URLs, private video contents, or rendered MP4 contents to this snapshot.",
    }

    text = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = args.output if args.output.is_absolute() else repo_root / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

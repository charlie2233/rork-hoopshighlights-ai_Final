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
DEFAULT_LABEL_STATUS_SUMMARY = Path("docs/launch_evidence/label_status_summary_2026-06-03.json")
REQUIRED_PRODUCTION_VARIABLES = [
    "HOOPS_CLOUD_ANALYSIS_BASE_URL",
    "HOOPS_CLOUD_EDIT_BASE_URL",
]
CANDIDATE_INTERNAL_TESTFLIGHT_WORKER_URL = "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"
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


def production_cloud_url_handoff(production_variables: dict[str, Any], branch: str) -> dict[str, Any]:
    missing = list(production_variables.get("missingRequired") or [])
    return {
        "status": "blocked" if missing else "configured",
        "missingVariables": missing,
        "variablesToConfirm": REQUIRED_PRODUCTION_VARIABLES,
        "candidateInternalTestFlightWorkerUrl": CANDIDATE_INTERNAL_TESTFLIGHT_WORKER_URL,
        "requiresReleaseOwnerConfirmation": bool(missing),
        "mustConfirmBeforeSetting": True,
        "secretSafe": True,
        "doNotReturn": [
            "secret values",
            "tokens",
            "private keys",
            "base64 values",
            "credential contents",
            "URL query strings",
        ],
        "commandsAfterConfirmation": [
            "gh variable set HOOPS_CLOUD_ANALYSIS_BASE_URL --env production --body '<confirmed-analysis-base-url>'",
            "gh variable set HOOPS_CLOUD_EDIT_BASE_URL --env production --body '<confirmed-edit-base-url>'",
            f"gh workflow run release-secrets-preflight.yml --ref {branch}",
            f"gh workflow run cloud-edit-deploy-preflight.yml --ref {branch}",
        ],
        "proofRequiredAfterSetting": [
            "gh variable list --env production shows both cloud URL variable names",
            "Release Secrets Preflight passes on the current launch branch head",
            "A refreshed launch evidence snapshot reports releaseSecretsPreflight.isPassing=true",
        ],
        "note": (
            "Use the candidate staging Worker URL only if the release owner explicitly confirms "
            "internal TestFlight Release smoke should point at staging for this launch gate."
        ),
    }


def label_status_snapshot(repo_root: Path, label_status_path: Path, summary_path: Path | None) -> dict[str, Any]:
    path = label_status_path if label_status_path.is_absolute() else repo_root / label_status_path
    if not path.exists():
        summary_payload: dict[str, Any] | None = None
        summary_exists = False
        if summary_path is not None:
            resolved_summary = summary_path if summary_path.is_absolute() else repo_root / summary_path
            if resolved_summary.exists():
                summary_exists = True
                summary_payload = json.loads(resolved_summary.read_text())
        if summary_payload is not None:
            return {
                "path": str(label_status_path),
                "exists": False,
                "source": "trackedSummary",
                "summaryPath": str(summary_path),
                "summaryExists": summary_exists,
                "summaryGeneratedAt": summary_payload.get("generatedAt"),
                "status": summary_payload.get("status", "missing"),
                "clipCount": summary_payload.get("clipCount"),
                "completeClipCount": summary_payload.get("completeClipCount"),
                "incompleteClipCount": summary_payload.get("incompleteClipCount"),
                "launchEvidenceEligible": summary_payload.get("launchEvidenceEligible", False),
                "missingFieldCounts": summary_payload.get("missingFieldCounts", {}),
                "notLaunchEvidence": summary_payload.get("notLaunchEvidence", True),
            }
        return {
            "path": str(label_status_path),
            "exists": False,
            "source": "missing",
            "summaryPath": str(summary_path) if summary_path is not None else None,
            "summaryExists": False,
            "status": "missing",
            "clipCount": None,
            "completeClipCount": None,
            "incompleteClipCount": None,
            "launchEvidenceEligible": False,
            "missingFieldCounts": {},
        }
    payload = json.loads(path.read_text())
    return {
        "path": str(label_status_path),
        "exists": True,
        "source": "generatedStatus",
        "summaryPath": str(summary_path) if summary_path is not None else None,
        "summaryExists": False,
        "status": payload.get("status"),
        "clipCount": payload.get("clipCount"),
        "completeClipCount": payload.get("completeClipCount"),
        "incompleteClipCount": payload.get("incompleteClipCount"),
        "launchEvidenceEligible": payload.get("launchEvidenceEligible"),
        "missingFieldCounts": payload.get("missingFieldCounts", {}),
    }


def label_review_guidance(labels: dict[str, Any]) -> dict[str, Any]:
    missing_fields = {
        str(key): value
        for key, value in (labels.get("missingFieldCounts") or {}).items()
        if value
    }
    missing_required_fields = sorted(missing_fields)
    launch_evidence_eligible = bool(labels.get("launchEvidenceEligible"))
    complete = labels.get("completeClipCount")
    total = labels.get("clipCount")
    incomplete = labels.get("incompleteClipCount")
    remaining = incomplete
    if remaining is None and total is not None and complete is not None:
        remaining = max(int(total) - int(complete), 0)

    next_actions: list[str] = []
    if not launch_evidence_eligible:
        next_actions = [
            "Open the generated team highlight labeling bundle.",
            "Complete human review for every launch clip before rebuilding evidence.",
            "Fill expected.eventType, expected.isHighlight, expected.outcome, expected.teamId, needsLabel=false, and reviewedByHuman=true.",
            "Rebuild label_status.json and the launch-grade team accuracy report after review.",
        ]

    return {
        "status": "complete" if launch_evidence_eligible else "human_review_required",
        "source": labels.get("source"),
        "sourceIsLaunchEvidence": labels.get("source") == "generatedStatus" and launch_evidence_eligible,
        "reviewedClipCount": complete,
        "totalClipCount": total,
        "remainingClipCount": remaining,
        "missingRequiredFields": missing_required_fields,
        "missingRequiredFieldCounts": missing_fields,
        "nextActions": next_actions,
    }


def latest_success_for_head(runs: list[dict[str, Any]], workflow_name: str, head: str | None) -> dict[str, Any] | None:
    if not head:
        return None
    for run_item in runs:
        if run_item.get("workflowName") == workflow_name and run_item.get("headSha") == head:
            if run_item.get("status") == "completed" and run_item.get("conclusion") == "success":
                return run_item
    return None


def release_preflight_is_passing(run_item: dict[str, Any] | None) -> bool:
    return bool(run_item and run_item.get("status") == "completed" and run_item.get("conclusion") == "success")


def release_preflight_for_head(runs: list[dict[str, Any]], head: str | None) -> dict[str, Any] | None:
    if not head:
        return None
    for run_item in runs:
        if run_item.get("headSha") == head:
            return run_item
    return None


def short_sha(value: Any) -> str:
    text = str(value or "")
    return text[:7] if text else "unknown"


def launch_blockers(
    production_variables: dict[str, Any],
    latest_release: dict[str, Any] | None,
    labels: dict[str, Any],
    current_head_release: dict[str, Any] | None = None,
    signed_archive_upload_proven: bool = False,
    installed_testflight_smoke_proven: bool = False,
) -> list[str]:
    blockers: list[str] = []
    missing_variables = production_variables.get("missingRequired") or []
    if missing_variables:
        blockers.append("Missing production cloud URL variables: " + ", ".join(missing_variables))
    if not release_preflight_is_passing(current_head_release):
        if current_head_release:
            blockers.append(
                "Release Secrets Preflight is not passing on current head: "
                + str(current_head_release.get("databaseId"))
                + " "
                + str(current_head_release.get("status"))
                + "/"
                + str(current_head_release.get("conclusion"))
            )
        elif latest_release:
            blockers.append(
                "Release Secrets Preflight has no current-head run evidence; latest run "
                + str(latest_release.get("databaseId"))
                + " was "
                + str(latest_release.get("status"))
                + "/"
                + str(latest_release.get("conclusion"))
                + " on "
                + short_sha(latest_release.get("headSha"))
            )
        else:
            blockers.append("Release Secrets Preflight has no current-head run evidence")
    if not labels.get("launchEvidenceEligible"):
        status = labels.get("status") or "unknown"
        complete = labels.get("completeClipCount")
        total = labels.get("clipCount")
        if complete is not None and total is not None:
            blockers.append(f"Human-reviewed accuracy labels incomplete: {complete}/{total}, status={status}")
        else:
            blockers.append(f"Human-reviewed accuracy labels missing or incomplete: status={status}")
    if not signed_archive_upload_proven:
        blockers.append("Signed App Store Connect archive/upload is not proven")
    if not installed_testflight_smoke_proven:
        blockers.append("Installed trusted-device TestFlight smoke is not proven")
    return blockers


def latest_for_head(runs: list[dict[str, Any]], workflow_name: str, head: str | None) -> dict[str, Any] | None:
    if not head:
        return None
    for run_item in runs:
        if run_item.get("workflowName") == workflow_name and run_item.get("headSha") == head:
            return run_item
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a secret-safe launch evidence snapshot.")
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Launch branch to inspect.")
    parser.add_argument("--workflow-limit", type=int, default=12, help="Number of branch workflow runs to inspect.")
    parser.add_argument("--label-status", type=Path, default=DEFAULT_LABEL_STATUS, help="Label status JSON path.")
    parser.add_argument("--label-status-summary", type=Path, default=DEFAULT_LABEL_STATUS_SUMMARY, help="Tracked non-secret label status summary fallback.")
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    git = git_snapshot(repo_root)
    runs = branch_workflows(repo_root, args.branch, args.workflow_limit)
    release_runs = release_preflight_runs(repo_root, 5)
    production_variables = production_variable_snapshot(repo_root)
    production_url_handoff = production_cloud_url_handoff(production_variables, args.branch)
    labels = label_status_snapshot(repo_root, args.label_status, args.label_status_summary)

    head = git.get("head")
    cloud_latest_run = latest_for_head(runs, "Cloud Edit Deploy Preflight", head)
    ios_latest_run = latest_for_head(runs, "iOS Internal TestFlight Upload", head)
    cloud_run = latest_success_for_head(runs, "Cloud Edit Deploy Preflight", head)
    ios_run = latest_success_for_head(runs, "iOS Internal TestFlight Upload", head)
    latest_release = release_runs[0] if release_runs else None
    current_head_release = release_preflight_for_head(release_runs, head)
    release_preflight_passing = release_preflight_is_passing(current_head_release)
    label_review = label_review_guidance(labels)

    open_blockers = launch_blockers(production_variables, latest_release, labels, current_head_release=current_head_release)
    snapshot = {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "secretSafe": True,
        "repoRoot": str(repo_root),
        "branch": args.branch,
        "git": git,
        "supportingBranchProof": {
            "cloudEditDeployPreflightLatestForHead": cloud_latest_run,
            "iosInternalTestFlightCodecheckLatestForHead": ios_latest_run,
            "cloudEditDeployPreflightSuccessForHead": cloud_run,
            "iosInternalTestFlightCodecheckSuccessForHead": ios_run,
            "currentHeadHasSupportingProof": bool(cloud_run and ios_run),
            "note": "Supporting proof only; not production cutover, signed upload, installed smoke, or human-reviewed accuracy proof. If this snapshot runs inside a workflow for the current head, the latest current-head runs may still be in progress and success fields may remain null until a later refresh.",
        },
        "productionVariables": production_variables,
        "productionCloudUrlHandoff": production_url_handoff,
        "releaseSecretsPreflight": {
            "latest": latest_release,
            "currentHead": current_head_release,
            "currentHeadRequired": True,
            "latestIsCurrentHead": bool(latest_release and latest_release.get("headSha") == head),
            "isPassing": release_preflight_passing,
        },
        "labelStatus": labels,
        "labelReview": label_review,
        "launchReadiness": {
            "launchReady": len(open_blockers) == 0,
            "openBlockers": open_blockers,
            "note": "A true value requires external evidence for production URLs/secrets, Release Secrets Preflight, human-reviewed labels, signed upload, and installed TestFlight smoke.",
        },
        "remainingRequiredEvidence": {
            "productionCloudUrls": bool(production_variables.get("missingRequired")),
            "releaseSecretsPreflight": not release_preflight_passing,
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

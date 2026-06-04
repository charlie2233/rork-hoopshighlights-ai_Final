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


def testflight_proof_handoff(
    branch: str,
    *,
    signed_archive_upload_proven: bool = False,
    installed_testflight_smoke_proven: bool = False,
) -> dict[str, Any]:
    signed_status = "proven" if signed_archive_upload_proven else "not_proven"
    installed_status = "proven" if installed_testflight_smoke_proven else "not_proven"
    return {
        "status": "complete" if signed_archive_upload_proven and installed_testflight_smoke_proven else "blocked",
        "signedArchiveUpload": {
            "status": signed_status,
            "requiredProof": [
                "Signed App Store Connect archive job completes successfully on the current launch branch head",
                "Internal TestFlight upload completes successfully for the same build",
                "Proof includes run ID, head SHA, build number, and non-secret job conclusion only",
            ],
            "commandAfterReleaseGatesPass": f"gh workflow run ios-testflight-upload.yml --ref {branch} -f operation=upload",
        },
        "installedTrustedDeviceSmoke": {
            "status": installed_status,
            "requiredProof": [
                "A trusted internal tester installs the uploaded build from TestFlight",
                "Tester imports real basketball footage",
                "Tester starts the cloud-owned AI edit path and verifies preview/download/share without local-only rendering",
                "Proof records device/build/date and non-secret smoke result only",
            ],
        },
        "codecheckIsNotLaunchEvidence": True,
        "doNotClaimFrom": [
            "operation=codecheck",
            "skipped archive job",
            "simulator-only runs",
            "local UI smoke without installed TestFlight build",
        ],
        "doNotReturn": [
            "App Store Connect private key contents",
            "base64 API key values",
            "Apple credentials",
            "private video files",
            "rendered MP4 contents",
            "presigned URLs",
        ],
        "note": "Keep archive/upload and installed smoke blocked until production cloud URLs/secrets and Release Secrets Preflight are proven for the current launch branch head.",
    }


def ios_usability_and_import_handoff(
    *,
    installed_testflight_smoke_proven: bool = False,
    import_history_proven: bool = False,
    readable_controls_proven: bool = False,
    export_share_proven: bool = False,
) -> dict[str, Any]:
    complete = installed_testflight_smoke_proven and import_history_proven and readable_controls_proven and export_share_proven
    next_actions: list[str] = []
    if not installed_testflight_smoke_proven:
        next_actions.append("Run trusted-device installed TestFlight smoke on the uploaded build.")
    if not import_history_proven:
        next_actions.append("Prove Photos/file import, long import recovery, background recovery, and project history actions.")
    if not readable_controls_proven:
        next_actions.append("Prove readable controls on small phones and dynamic type with no hidden text, fake thinking, or vague ETAs.")
    if not export_share_proven:
        next_actions.append("Prove finished MP4 preview, download, share sheet, and open-in-editor handoff.")

    return {
        "status": "complete" if complete else "blocked",
        "installedTestFlightSmokeRequired": True,
        "iosScope": [
            "Photos/file import",
            "team choice",
            "edit intent/options/notes",
            "upload and cloud job status",
            "clip/edit-plan review",
            "finished MP4 preview",
            "download",
            "share sheet",
            "open in common editors",
            "history resume/source/saved reel/share/delete",
        ],
        "cloudBoundary": "iOS must remain the control surface; analysis, GPT selection, edit planning, rendering, storage, revisions, and policy stay backend-owned.",
        "stableAccessibilityIdsToSmoke": [
            "export.aiEdit.planCard.free",
            "export.aiEdit.proValueCard",
            "export.aiEdit.proTemplate.*",
            "export.aiEdit.proInfoSheet",
            "export.aiEdit.workReceipt",
            "export.aiEdit.watermarkUpsell",
        ],
        "requiredProof": {
            "importHistory": {
                "status": "proven" if import_history_proven else "not_proven",
                "requirements": [
                    "import real basketball footage from Photos or Files",
                    "recover from long import/backgrounding",
                    "resume project from history",
                    "watch source and saved reel from history",
                    "share and delete from history with plain copy",
                ],
            },
            "readableControls": {
                "status": "proven" if readable_controls_proven else "not_proven",
                "requirements": [
                    "short visible labels",
                    "small phone layout",
                    "dynamic type layout",
                    "no cramped buttons",
                    "no hidden words",
                    "no fake thinking",
                    "no vague ETAs",
                ],
            },
            "exportShare": {
                "status": "proven" if export_share_proven else "not_proven",
                "requirements": [
                    "finished MP4 preview",
                    "download",
                    "share sheet",
                    "open in CapCut/iMovie/Adobe/Files/Photos or available editors",
                    "no unsupported local iOS rendering dependency",
                ],
            },
        },
        "doNotClaimFrom": [
            "iOS codecheck alone",
            "simulator-only UI smoke",
            "unit tests without installed build",
            "local-only rendering fallback",
            "docs without trusted-device evidence",
        ],
        "nextActions": next_actions,
    }


def cloud_backend_readiness_handoff(
    production_variables: dict[str, Any],
    release_preflight_passing: bool,
    cloud_latest_run: dict[str, Any] | None,
    cloud_success_run: dict[str, Any] | None,
    *,
    live_backend_status_proven: bool = False,
    render_reliability_proven: bool = False,
    job_state_reporting_proven: bool = False,
) -> dict[str, Any]:
    missing_variables = list(production_variables.get("missingRequired") or [])
    deploy_preflight_status = "proven_current_head" if cloud_success_run else "pending_or_unproven"
    complete = (
        not missing_variables
        and release_preflight_passing
        and bool(cloud_success_run)
        and live_backend_status_proven
        and render_reliability_proven
        and job_state_reporting_proven
    )
    next_actions: list[str] = []
    if missing_variables:
        next_actions.append("Confirm and set production cloud URL variables before Release smoke.")
    if not release_preflight_passing:
        next_actions.append("Rerun Release Secrets Preflight on the current launch branch head after production URLs are set.")
    if not cloud_success_run:
        next_actions.append("Rerun Cloud Edit Deploy Preflight and require current-head success.")
    if not live_backend_status_proven:
        next_actions.append("Record secret-safe live backend status for analysis, editing, rendering, storage, and policy routes.")
    if not render_reliability_proven:
        next_actions.append("Record cloud render reliability proof with finished MP4, preview, download, and share/open evidence.")
    if not job_state_reporting_proven:
        next_actions.append("Record job-state reporting proof for upload, analysis, edit planning, rendering, revision, and download states.")

    return {
        "status": "complete" if complete else "blocked",
        "cloudOwnedPathRequired": True,
        "backendOwns": [
            "analysis",
            "GPT selection",
            "edit planning",
            "rendering",
            "storage",
            "revisions",
            "policy",
            "job-state reporting",
        ],
        "iosScope": [
            "upload",
            "style and target-length selection",
            "generated clip/edit-plan review",
            "job status",
            "finished MP4 preview",
            "download",
            "share/open in editors",
        ],
        "productionCloudUrls": {
            "status": "configured" if not missing_variables else "blocked",
            "missingVariables": missing_variables,
        },
        "releaseSecretsPreflight": {
            "status": "passing" if release_preflight_passing else "blocked",
            "currentHeadRequired": True,
        },
        "cloudDeployPreflight": {
            "status": deploy_preflight_status,
            "latestForHead": cloud_latest_run,
            "successForHead": cloud_success_run,
        },
        "liveBackendStatus": {
            "status": "proven" if live_backend_status_proven else "not_proven",
            "requiredProof": "Secret-safe live backend status for production cloud analysis/edit/render/storage routes.",
        },
        "renderReliability": {
            "status": "proven" if render_reliability_proven else "not_proven",
            "requiredProof": "Cloud-rendered finished MP4 can be previewed, downloaded, and shared/opened without local-only rendering.",
        },
        "jobStateReporting": {
            "status": "proven" if job_state_reporting_proven else "not_proven",
            "requiredProof": "Upload, analysis, edit planning, rendering, revision, and download states are observable and not fake/vague.",
        },
        "doNotClaimFrom": [
            "green iOS codecheck alone",
            "simulator-only UI smoke",
            "staging-only endpoint without release-owner confirmation",
            "local AVFoundation rendering",
            "docs without live backend evidence",
        ],
        "nextActions": next_actions,
    }


def gpt_clipping_accuracy_handoff(labels: dict[str, Any]) -> dict[str, Any]:
    launch_evidence_eligible = bool(labels.get("launchEvidenceEligible"))
    complete = labels.get("completeClipCount")
    total = labels.get("clipCount")
    incomplete = labels.get("incompleteClipCount")
    missing_fields = labels.get("missingFieldCounts") if isinstance(labels.get("missingFieldCounts"), dict) else {}
    next_actions: list[str] = []
    if not launch_evidence_eligible:
        next_actions = [
            "Complete human review for every GPT-selected launch clip.",
            "Rebuild the launch-grade team accuracy report from real cloud analysis with manual labels.",
            "Prove team-aware selection quality with selected-team and opponent clips.",
            "Prove offensive and defensive event context, including blocks, steals, forced turnovers, and defensive stops.",
            "Prove crowd/audio reaction recall and shot outcome correctness on real clips.",
            "Keep uncertain clips review-safe instead of silently promoting them into the finished edit.",
        ]

    return {
        "status": "complete" if launch_evidence_eligible else "blocked",
        "launchEvidenceEligible": launch_evidence_eligible,
        "humanReviewedClipCount": complete,
        "totalClipCount": total,
        "remainingClipCount": incomplete,
        "missingFieldCounts": missing_fields,
        "requiredProof": [
            "team-aware selected-team highlight precision and recall",
            "opponent and negative clip coverage",
            "offensive context",
            "defensive context",
            "crowd/audio reaction recall",
            "shot outcome correctness",
            "review-safe uncertain clips",
            "real cloud analysis evidence, not synthetic or draft-only labels",
        ],
        "doNotClaimFrom": [
            "GPT draft labels without human review",
            "0/54 label coverage",
            "unit tests alone",
            "synthetic fixtures alone",
            "candidate-only reranker output without launch-grade report",
        ],
        "nextActions": next_actions,
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
    import_history_proven: bool = False,
    readable_controls_proven: bool = False,
    export_share_proven: bool = False,
    live_backend_status_proven: bool = False,
    render_reliability_proven: bool = False,
    job_state_reporting_proven: bool = False,
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
    if not live_backend_status_proven:
        blockers.append("Live production backend status is not proven")
    if not render_reliability_proven:
        blockers.append("Cloud render reliability is not proven with finished MP4 evidence")
    if not job_state_reporting_proven:
        blockers.append("Cloud job-state reporting is not proven end to end")
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
    if not import_history_proven:
        blockers.append("Import/history reliability proof is not proven on an installed TestFlight build")
    if not readable_controls_proven:
        blockers.append("Small-phone and dynamic-type readable controls proof is not proven")
    if not export_share_proven:
        blockers.append("Finished MP4 preview/download/share/open-in-editor proof is not proven")
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
    parser.add_argument("--signed-archive-upload-proven", action="store_true", help="Mark signed App Store Connect archive/upload proof as externally verified.")
    parser.add_argument("--installed-testflight-smoke-proven", action="store_true", help="Mark trusted-device installed TestFlight smoke proof as externally verified.")
    parser.add_argument("--import-history-proven", action="store_true", help="Mark Photos/File import, recovery, and history actions as externally verified.")
    parser.add_argument("--readable-controls-proven", action="store_true", help="Mark small-phone and dynamic-type readable controls as externally verified.")
    parser.add_argument("--export-share-proven", action="store_true", help="Mark finished MP4 preview/download/share/open-in-editor proof as externally verified.")
    parser.add_argument("--live-backend-status-proven", action="store_true", help="Mark live production backend status proof as externally verified.")
    parser.add_argument("--render-reliability-proven", action="store_true", help="Mark cloud render reliability with finished MP4 evidence as externally verified.")
    parser.add_argument("--job-state-reporting-proven", action="store_true", help="Mark end-to-end cloud job-state reporting proof as externally verified.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    git = git_snapshot(repo_root)
    runs = branch_workflows(repo_root, args.branch, args.workflow_limit)
    release_runs = release_preflight_runs(repo_root, 5)
    production_variables = production_variable_snapshot(repo_root)
    production_url_handoff = production_cloud_url_handoff(production_variables, args.branch)
    testflight_handoff = testflight_proof_handoff(
        args.branch,
        signed_archive_upload_proven=args.signed_archive_upload_proven,
        installed_testflight_smoke_proven=args.installed_testflight_smoke_proven,
    )
    ios_usability_handoff = ios_usability_and_import_handoff(
        installed_testflight_smoke_proven=args.installed_testflight_smoke_proven,
        import_history_proven=args.import_history_proven,
        readable_controls_proven=args.readable_controls_proven,
        export_share_proven=args.export_share_proven,
    )
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
    gpt_accuracy_handoff = gpt_clipping_accuracy_handoff(labels)
    cloud_backend_handoff = cloud_backend_readiness_handoff(
        production_variables,
        release_preflight_passing,
        cloud_latest_run,
        cloud_run,
        live_backend_status_proven=args.live_backend_status_proven,
        render_reliability_proven=args.render_reliability_proven,
        job_state_reporting_proven=args.job_state_reporting_proven,
    )

    open_blockers = launch_blockers(
        production_variables,
        latest_release,
        labels,
        current_head_release=current_head_release,
        signed_archive_upload_proven=args.signed_archive_upload_proven,
        installed_testflight_smoke_proven=args.installed_testflight_smoke_proven,
        import_history_proven=args.import_history_proven,
        readable_controls_proven=args.readable_controls_proven,
        export_share_proven=args.export_share_proven,
        live_backend_status_proven=args.live_backend_status_proven,
        render_reliability_proven=args.render_reliability_proven,
        job_state_reporting_proven=args.job_state_reporting_proven,
    )
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
        "cloudBackendReadinessHandoff": cloud_backend_handoff,
        "testFlightProofHandoff": testflight_handoff,
        "iosUsabilityAndImportHandoff": ios_usability_handoff,
        "gptClippingAccuracyHandoff": gpt_accuracy_handoff,
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
            "note": "A true value requires external evidence for production URLs/secrets, Release Secrets Preflight, human-reviewed labels, signed upload, installed TestFlight smoke, import/history recovery, readable controls, and export/share/open-in-editor.",
        },
        "remainingRequiredEvidence": {
            "productionCloudUrls": bool(production_variables.get("missingRequired")),
            "releaseSecretsPreflight": not release_preflight_passing,
            "humanReviewedLabels": not bool(labels.get("launchEvidenceEligible")),
            "signedArchiveUpload": not args.signed_archive_upload_proven,
            "installedTestFlightSmoke": not args.installed_testflight_smoke_proven,
            "importHistoryReliability": not args.import_history_proven,
            "readableControls": not args.readable_controls_proven,
            "exportShare": not args.export_share_proven,
            "liveBackendStatus": not args.live_backend_status_proven,
            "renderReliability": not args.render_reliability_proven,
            "jobStateReporting": not args.job_state_reporting_proven,
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

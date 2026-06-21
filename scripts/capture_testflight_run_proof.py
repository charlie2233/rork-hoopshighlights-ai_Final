#!/usr/bin/env python3
"""Capture sanitized proof for an existing iOS TestFlight GitHub Actions run.

This script is read-only. It uses `gh run view` or `gh run list`; it never
triggers workflows, reruns jobs, uploads builds, or prints secrets.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_WORKFLOW = "iOS Internal TestFlight Upload"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture sanitized TestFlight workflow proof for HoopClips."
    )
    parser.add_argument("--run-id", help="Existing GitHub Actions run id to inspect.")
    parser.add_argument(
        "--workflow",
        default=DEFAULT_WORKFLOW,
        help=f"Workflow name for latest-run lookup. Default: {DEFAULT_WORKFLOW}",
    )
    parser.add_argument("--branch", default="main", help="Branch for latest-run lookup.")
    parser.add_argument("--require-commit", help="Require the run head SHA to match.")
    parser.add_argument("--require-build", help="Expected TestFlight build number to record.")
    parser.add_argument("--out", help="Write sanitized JSON proof here. Defaults to stdout.")
    parser.add_argument(
        "--allow-in-progress",
        action="store_true",
        help="Do not fail when the run is still queued/in_progress.",
    )
    return parser.parse_args()


def gh_json(command: list[str]) -> Any:
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "gh command failed")
    return json.loads(completed.stdout)


def latest_run_id(workflow: str, branch: str) -> str:
    runs = gh_json(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            workflow,
            "--branch",
            branch,
            "--limit",
            "1",
            "--json",
            "databaseId",
        ]
    )
    if not runs:
        raise RuntimeError(f"No runs found for workflow={workflow!r} branch={branch!r}")
    return str(runs[0]["databaseId"])


def view_run(run_id: str) -> dict[str, Any]:
    data = gh_json(
        [
            "gh",
            "run",
            "view",
            run_id,
            "--json",
            "attempt,conclusion,createdAt,databaseId,displayTitle,event,headBranch,headSha,jobs,name,number,status,updatedAt,url,workflowName",
        ]
    )
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected gh run view output.")
    return data


def summarize_jobs(jobs: Any) -> list[dict[str, Any]]:
    if not isinstance(jobs, list):
        return []
    summarized: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        summarized.append(
            {
                "name": job.get("name"),
                "status": job.get("status"),
                "conclusion": job.get("conclusion"),
                "startedAt": job.get("startedAt"),
                "completedAt": job.get("completedAt"),
            }
        )
    return summarized


def build_proof(args: argparse.Namespace, run: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    status = run.get("status")
    conclusion = run.get("conclusion")
    head_sha = run.get("headSha")

    if args.require_commit and head_sha != args.require_commit:
        blockers.append(f"headSha mismatch: expected {args.require_commit}, got {head_sha}")
    if status != "completed":
        message = f"workflow status is {status}, not completed"
        if args.allow_in_progress and status in {"queued", "in_progress", "waiting", "requested"}:
            warnings.append(message)
        else:
            blockers.append(message)
    if status == "completed" and conclusion != "success":
        blockers.append(f"workflow conclusion is {conclusion}, not success")
    if run.get("workflowName") not in {args.workflow, None} and run.get("name") not in {args.workflow, None}:
        warnings.append(f"workflow name differs from requested workflow: {run.get('workflowName') or run.get('name')}")

    ready = not blockers
    return {
        "label": "testflight-run-proof",
        "capturedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "testFlightRunProofReady": ready,
        "requestedWorkflow": args.workflow,
        "requiredCommit": args.require_commit,
        "expectedTestFlightBuild": args.require_build,
        "run": {
            "databaseId": run.get("databaseId"),
            "number": run.get("number"),
            "attempt": run.get("attempt"),
            "workflowName": run.get("workflowName") or run.get("name"),
            "displayTitle": run.get("displayTitle"),
            "event": run.get("event"),
            "headBranch": run.get("headBranch"),
            "headSha": head_sha,
            "status": status,
            "conclusion": conclusion,
            "createdAt": run.get("createdAt"),
            "updatedAt": run.get("updatedAt"),
            "url": run.get("url"),
            "jobs": summarize_jobs(run.get("jobs")),
        },
        "blockers": blockers,
        "warnings": warnings,
        "safetyNote": "Read-only gh inspection. No workflow was triggered, rerun, uploaded, or modified.",
    }


def main() -> int:
    args = parse_args()
    try:
        run_id = args.run_id or latest_run_id(args.workflow, args.branch)
        proof = build_proof(args, view_run(run_id))
    except Exception as exc:
        proof = {
            "label": "testflight-run-proof",
            "capturedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "testFlightRunProofReady": False,
            "blockers": [str(exc)],
            "warnings": [],
            "safetyNote": "Read-only gh inspection failed before producing run proof.",
        }

    output = json.dumps(proof, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if proof.get("testFlightRunProofReady") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

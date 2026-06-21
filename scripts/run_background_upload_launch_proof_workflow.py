#!/usr/bin/env python3
"""Run the full read-only HoopClips background-upload launch proof workflow.

This coordinator does not trigger GitHub Actions, deploy services, upload
TestFlight builds, or mutate remote state. It only combines existing evidence:

1. Capture proof from an existing TestFlight workflow run.
2. Build backend+phone background-upload evidence.
3. Assemble final launch evidence linking the uploaded build to the phone proof.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WORKFLOW = "iOS Internal TestFlight Upload"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create final background-upload launch evidence from existing proof inputs."
    )
    parser.add_argument("--commit", required=True, help="Exact git commit expected.")
    parser.add_argument("--build", required=True, help="Exact TestFlight build expected.")
    parser.add_argument("--out-dir", required=True, help="Directory for generated proof files.")
    parser.add_argument("--phone-proof", required=True, help="Final copied phone proof text/JSON.")
    parser.add_argument(
        "--backend-evidence",
        required=True,
        help="Sanitized backend resumable upload smoke evidence JSON.",
    )
    parser.add_argument("--before-proof", help="Proof copied before switching apps.")
    parser.add_argument("--after-proof", help="Proof copied after returning to HoopClips.")
    parser.add_argument("--final-proof", help="Optional final proof after analysis/review continuation.")
    parser.add_argument("--file-size-bytes", help="Optional source file size in bytes.")
    parser.add_argument("--run-id", help="Existing TestFlight GitHub Actions run id.")
    parser.add_argument(
        "--workflow",
        default=DEFAULT_WORKFLOW,
        help=f"Workflow name for latest-run lookup. Default: {DEFAULT_WORKFLOW}",
    )
    parser.add_argument("--branch", default="main", help="Branch for latest-run lookup.")
    parser.add_argument(
        "--allow-in-progress",
        action="store_true",
        help="Allow TestFlight proof capture to record an in-progress run.",
    )
    parser.add_argument(
        "--label",
        default="background-upload-launch-proof",
        help="Short label used in generated evidence files.",
    )
    return parser.parse_args()


def run(command: list[str]) -> int:
    print("+ " + " ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    testflight_proof_path = out_dir / "testflight-run-proof.json"
    background_bundle_path = out_dir / "background-upload-evidence-bundle.json"
    launch_evidence_path = out_dir / "background-upload-launch-evidence.json"

    testflight_command = [
        sys.executable,
        str(SCRIPT_DIR / "capture_testflight_run_proof.py"),
        "--workflow",
        args.workflow,
        "--branch",
        args.branch,
        "--require-commit",
        args.commit,
        "--require-build",
        args.build,
        "--out",
        str(testflight_proof_path),
    ]
    if args.run_id:
        testflight_command.extend(["--run-id", args.run_id])
    if args.allow_in_progress:
        testflight_command.append("--allow-in-progress")
    testflight_status = run(testflight_command)

    evidence_command = [
        sys.executable,
        str(SCRIPT_DIR / "run_background_upload_evidence_workflow.py"),
        "--commit",
        args.commit,
        "--build",
        args.build,
        "--out-dir",
        str(out_dir),
        "--phone-proof",
        args.phone_proof,
        "--backend-evidence",
        args.backend_evidence,
        "--label",
        args.label,
    ]
    if args.before_proof:
        evidence_command.extend(["--before-proof", args.before_proof])
    if args.after_proof:
        evidence_command.extend(["--after-proof", args.after_proof])
    if args.final_proof:
        evidence_command.extend(["--final-proof", args.final_proof])
    if args.file_size_bytes:
        evidence_command.extend(["--file-size-bytes", args.file_size_bytes])
    evidence_status = run(evidence_command)

    launch_command = [
        sys.executable,
        str(SCRIPT_DIR / "assemble_background_upload_launch_evidence.py"),
        "--testflight-proof",
        str(testflight_proof_path),
        "--background-upload-bundle",
        str(background_bundle_path),
        "--require-commit",
        args.commit,
        "--require-build",
        args.build,
        "--out",
        str(launch_evidence_path),
    ]
    launch_status = run(launch_command)

    print(f"testFlightProof: {testflight_proof_path}")
    print(f"backgroundUploadBundle: {background_bundle_path}")
    print(f"launchEvidence: {launch_evidence_path}")
    print("safetyNote: read-only proof workflow; no TestFlight upload, workflow trigger, deploy, or rerun was performed.")

    return 0 if testflight_status == 0 and evidence_status == 0 and launch_status == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

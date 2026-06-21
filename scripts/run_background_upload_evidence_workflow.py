#!/usr/bin/env python3
"""Run the HoopClips background-upload evidence workflow.

This is a small coordinator around the existing proof helpers. It keeps the
real-device proof path in one command sequence:

1. Optionally create a safe phone-proof template.
2. Check copied phone proof.
3. Build a sanitized phone-proof markdown packet.
4. Optionally assemble backend + phone evidence into one JSON bundle.
5. Optionally compare before/after app-switch snapshots for progress and ETA.

The script never embeds raw proof in generated bundle summaries. The lower-level
helpers still own privacy scanning and pass/blocker decisions.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coordinate HoopClips background-upload evidence commands."
    )
    parser.add_argument("--commit", required=True, help="Git commit tested.")
    parser.add_argument("--build", required=True, help="TestFlight build number tested.")
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory for generated template/packet/bundle files.",
    )
    parser.add_argument(
        "--phone-proof",
        help="Copied real-device phone proof. If omitted, only a template is created.",
    )
    parser.add_argument(
        "--backend-evidence",
        help="Sanitized backend resumable upload smoke evidence JSON.",
    )
    parser.add_argument(
        "--before-proof",
        help="Proof copied before switching apps, for progress/ETA evidence.",
    )
    parser.add_argument(
        "--after-proof",
        help="Proof copied after returning to HoopClips, for progress/ETA evidence.",
    )
    parser.add_argument(
        "--final-proof",
        help="Optional final proof after upload/analysis continuation.",
    )
    parser.add_argument(
        "--file-size-bytes",
        help="Optional source file size in bytes for ETA/Mbps estimation.",
    )
    parser.add_argument(
        "--label",
        default="background-upload-e2e",
        help="Short label used in generated evidence files.",
    )
    return parser.parse_args()


def run(command: list[str]) -> int:
    print("+ " + " ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


def run_to_file(command: list[str], out_path: Path) -> int:
    print("+ " + " ".join(command) + f" > {out_path}")
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    out_path.write_text(completed.stdout, encoding="utf-8")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    return completed.returncode


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    template_path = out_dir / "background-upload-phone-proof-template.txt"
    packet_path = out_dir / "background-upload-phone-proof-packet.md"
    bundle_path = out_dir / "background-upload-evidence-bundle.json"
    progress_path = out_dir / "background-upload-progress-snapshots.json"
    eta_path = out_dir / "background-upload-eta.json"

    template_command = [
        sys.executable,
        str(SCRIPT_DIR / "create_background_upload_phone_proof_template.py"),
        "--commit",
        args.commit,
        "--build",
        args.build,
        "--label",
        args.label,
        "--out",
        str(template_path),
    ]
    if run(template_command) != 0:
        return 1

    if not args.phone_proof:
        print(f"template: {template_path}")
        print("next: fill the template from the TestFlight phone proof, then rerun with --phone-proof.")
        return 0

    check_command = [
        sys.executable,
        str(SCRIPT_DIR / "verify_background_upload_phone_proof.py"),
        args.phone_proof,
    ]
    check_status = run(check_command)

    packet_command = [
        sys.executable,
        str(SCRIPT_DIR / "build_background_upload_phone_packet.py"),
        args.phone_proof,
        "--commit",
        args.commit,
        "--build",
        args.build,
        "--label",
        args.label,
        "--out",
        str(packet_path),
    ]
    packet_status = run(packet_command)

    bundle_status = 0
    if args.backend_evidence:
        bundle_command = [
            sys.executable,
            str(SCRIPT_DIR / "assemble_background_upload_evidence_bundle.py"),
            "--backend-evidence",
            args.backend_evidence,
            "--phone-proof",
            args.phone_proof,
            "--commit",
            args.commit,
            "--build",
            args.build,
            "--label",
            args.label,
            "--out",
            str(bundle_path),
        ]
        bundle_status = run(bundle_command)

    progress_status = 0
    eta_status = 0
    if args.before_proof or args.after_proof:
        if not args.before_proof or not args.after_proof:
            print("--before-proof and --after-proof must be provided together.", file=sys.stderr)
            progress_status = 1
            eta_status = 1
        else:
            progress_command = [
                sys.executable,
                str(SCRIPT_DIR / "check_background_upload_progress_snapshots.py"),
                "--before",
                args.before_proof,
                "--after",
                args.after_proof,
                "--json",
            ]
            if args.final_proof:
                progress_command.extend(["--final", args.final_proof])
            progress_status = run_to_file(progress_command, progress_path)

            eta_command = [
                sys.executable,
                str(SCRIPT_DIR / "estimate_background_upload_eta.py"),
                "--before",
                args.before_proof,
                "--after",
                args.after_proof,
                "--json",
            ]
            if args.file_size_bytes:
                eta_command.extend(["--file-size-bytes", args.file_size_bytes])
            eta_status = run_to_file(eta_command, eta_path)

    print(f"template: {template_path}")
    print(f"phonePacket: {packet_path}")
    if args.backend_evidence:
        print(f"evidenceBundle: {bundle_path}")
    else:
        print("evidenceBundle: skipped because --backend-evidence was not provided")
    if args.before_proof and args.after_proof:
        print(f"progressSnapshots: {progress_path}")
        print(f"uploadEta: {eta_path}")
    else:
        print("progressSnapshots: skipped because --before-proof/--after-proof were not provided")

    return 0 if check_status == 0 and packet_status == 0 and bundle_status == 0 and progress_status == 0 and eta_status == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

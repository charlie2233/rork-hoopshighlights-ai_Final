#!/usr/bin/env python3
"""Prepare copied HoopClips phone proof for safe background-upload evidence.

This helper chains the existing redactor and verifier:

1. Redact unsafe values from raw copied proof.
2. Write a redaction report.
3. Verify the redacted proof is safe and evidence-ready.

It does not upload, deploy, trigger workflows, or mutate remote state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Redact and verify HoopClips background-upload phone proof."
    )
    parser.add_argument("raw_proof", help="Raw copied phone proof text/JSON.")
    parser.add_argument("--out-dir", required=True, help="Directory for prepared proof files.")
    parser.add_argument(
        "--name",
        default="background-upload-phone-proof",
        help="Base filename for generated files.",
    )
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command))
    return subprocess.run(command, check=False, text=True, capture_output=True)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    redacted_path = out_dir / f"{args.name}.redacted.txt"
    redaction_report_path = out_dir / f"{args.name}.redaction-report.json"
    verification_path = out_dir / f"{args.name}.verification.json"

    redact = run(
        [
            sys.executable,
            str(SCRIPT_DIR / "redact_background_upload_phone_proof.py"),
            args.raw_proof,
            "--out",
            str(redacted_path),
            "--report",
            str(redaction_report_path),
        ]
    )
    if redact.stdout:
        print(redact.stdout, end="")
    if redact.stderr:
        print(redact.stderr, file=sys.stderr, end="")

    verify = run(
        [
            sys.executable,
            str(SCRIPT_DIR / "verify_background_upload_phone_proof.py"),
            str(redacted_path),
            "--json",
        ]
    )
    verification_path.write_text(verify.stdout, encoding="utf-8")
    if verify.stderr:
        print(verify.stderr, file=sys.stderr, end="")

    try:
        verification = json.loads(verify.stdout)
    except json.JSONDecodeError:
        verification = {
            "status": "blocked",
            "blockers": ["Proof verification did not return valid JSON."],
        }

    summary = {
        "preparedPhoneProofReady": verify.returncode == 0
        and verification.get("backgroundUploadPhoneProofReady") is True,
        "redactedProof": str(redacted_path),
        "redactionReport": str(redaction_report_path),
        "verification": str(verification_path),
        "verificationStatus": verification.get("status", "blocked"),
        "blockers": verification.get("blockers", []),
        "safetyNote": "Use the redacted proof path, not the raw proof path, in launch evidence commands.",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    return 0 if summary["preparedPhoneProofReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

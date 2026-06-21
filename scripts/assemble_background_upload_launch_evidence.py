#!/usr/bin/env python3
"""Assemble final HoopClips background-upload launch evidence.

Inputs:
- TestFlight run proof from scripts/capture_testflight_run_proof.py
- Background upload evidence bundle from scripts/assemble_background_upload_evidence_bundle.py

The output links the uploaded TestFlight build to the backend+phone proof and
fails closed when commit/build/sample evidence does not line up.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble final HoopClips background-upload launch evidence."
    )
    parser.add_argument("--testflight-proof", required=True, help="TestFlight run proof JSON.")
    parser.add_argument(
        "--background-upload-bundle",
        required=True,
        help="Backend+phone background-upload evidence bundle JSON.",
    )
    parser.add_argument("--require-commit", required=True, help="Exact git commit expected.")
    parser.add_argument("--require-build", required=True, help="Exact TestFlight build expected.")
    parser.add_argument("--out", help="Write final launch evidence JSON here. Defaults to stdout.")
    parser.add_argument(
        "--allow-sample",
        action="store_true",
        help="Allow sample/rehearsal markers. Never use this for launch proof.",
    )
    return parser.parse_args()


def read_json(path: str) -> dict[str, Any]:
    parsed = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return parsed


def has_sample_marker(value: Any) -> bool:
    return "sample" in str(value or "").lower()


def list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def build(args: argparse.Namespace) -> dict[str, Any]:
    testflight = read_json(args.testflight_proof)
    background = read_json(args.background_upload_bundle)

    blockers: list[str] = []
    warnings: list[str] = []

    blockers.extend(f"testflight: {item}" for item in list_values(testflight.get("blockers")))
    blockers.extend(f"backgroundUpload: {item}" for item in list_values(background.get("blockers")))
    warnings.extend(f"testflight: {item}" for item in list_values(testflight.get("warnings")))

    testflight_commit = testflight.get("run", {}).get("headSha")
    testflight_build = testflight.get("expectedTestFlightBuild")
    background_commit = background.get("commit")
    background_build = background.get("testFlightBuild")

    if testflight.get("testFlightRunProofReady") is not True:
        blockers.append("TestFlight run proof is not ready.")
    if background.get("backgroundUploadEvidenceReady") is not True:
        blockers.append("Background upload evidence bundle is not ready.")
    if background.get("privacyScanPassed") is not True:
        blockers.append("Background upload privacy scan did not pass.")

    if testflight_commit != args.require_commit:
        blockers.append(
            f"TestFlight commit mismatch: expected {args.require_commit}, got {testflight_commit}"
        )
    if background_commit != args.require_commit:
        blockers.append(
            f"Background upload commit mismatch: expected {args.require_commit}, got {background_commit}"
        )
    if testflight_build != args.require_build:
        blockers.append(
            f"TestFlight build mismatch: expected {args.require_build}, got {testflight_build}"
        )
    if background_build != args.require_build:
        blockers.append(
            f"Background upload build mismatch: expected {args.require_build}, got {background_build}"
        )

    if not args.allow_sample and any(
        has_sample_marker(value)
        for value in (
            testflight.get("label"),
            background.get("label"),
            testflight_commit,
            background_commit,
            testflight_build,
            background_build,
        )
    ):
        blockers.append("Evidence contains sample/rehearsal markers.")

    unique_blockers = list(dict.fromkeys(blockers))
    ready = not unique_blockers

    return {
        "label": "background-upload-launch-evidence",
        "createdAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "backgroundUploadLaunchEvidenceReady": ready,
        "requiredCommit": args.require_commit,
        "requiredTestFlightBuild": args.require_build,
        "testFlight": {
            "proofReady": testflight.get("testFlightRunProofReady"),
            "runId": testflight.get("run", {}).get("databaseId"),
            "runUrl": testflight.get("run", {}).get("url"),
            "headSha": testflight_commit,
            "status": testflight.get("run", {}).get("status"),
            "conclusion": testflight.get("run", {}).get("conclusion"),
            "expectedBuild": testflight_build,
        },
        "backgroundUpload": {
            "evidenceReady": background.get("backgroundUploadEvidenceReady"),
            "privacyScanPassed": background.get("privacyScanPassed"),
            "commit": background_commit,
            "testFlightBuild": background_build,
            "phoneProofReady": background.get("phoneEvidence", {}).get("backgroundUploadPhoneProofReady"),
            "appSwitchEvidence": background.get("phoneEvidence", {}).get("appSwitchEvidence"),
            "continuationReady": background.get("phoneEvidence", {}).get("continuationReady"),
            "backendUploadComplete": background.get("backendEvidence", {}).get("uploadComplete"),
            "backendDuplicateCompleteOk": background.get("backendEvidence", {}).get("duplicateCompleteOk"),
        },
        "blockers": unique_blockers,
        "warnings": warnings,
        "safetyNote": "Final bundle links sanitized proof outputs only. It does not embed raw phone proof, presigned URLs, local paths, upload IDs, job IDs, object keys, or upload headers.",
    }


def main() -> int:
    args = parse_args()
    try:
        result = build(args)
    except Exception as exc:
        result = {
            "label": "background-upload-launch-evidence",
            "createdAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "backgroundUploadLaunchEvidenceReady": False,
            "blockers": [str(exc)],
            "warnings": [],
            "safetyNote": "Final launch evidence assembly failed before producing a ready packet.",
        }

    output = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if result.get("backgroundUploadLaunchEvidenceReady") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

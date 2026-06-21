#!/usr/bin/env python3
"""Summarize remaining blockers for HoopClips background-upload proof.

This is a local evidence snapshot helper. It does not deploy, upload TestFlight,
trigger GitHub Actions, inspect secrets, or mutate remote state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_FILES = {
    "testFlightRunProof": "testflight-run-proof.json",
    "backendSmokeEvidence": "backend-smoke-evidence.json",
    "beforeSwitchProof": "before-switch-proof.txt",
    "afterSwitchProof": "after-switch-proof.txt",
    "finalPhoneProof": "final-proof.txt",
    "backgroundUploadBundle": "background-upload-evidence-bundle.json",
    "launchEvidence": "background-upload-launch-evidence.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report current background-upload launch proof blockers."
    )
    parser.add_argument(
        "--proof-dir",
        required=True,
        help="Directory where background-upload proof files are collected.",
    )
    parser.add_argument("--commit", help="Expected git commit for the proof packet.")
    parser.add_argument("--build", help="Expected TestFlight build for the proof packet.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    proof_dir = Path(args.proof_dir)
    paths = {name: proof_dir / filename for name, filename in EXPECTED_FILES.items()}
    files = {
        name: {
            "path": str(path),
            "exists": path.exists(),
            "sizeBytes": path.stat().st_size if path.exists() else 0,
        }
        for name, path in paths.items()
    }

    blockers: list[str] = []
    for name, info in files.items():
        if not info["exists"]:
            blockers.append(f"missing {name}: {info['path']}")

    testflight = read_json(paths["testFlightRunProof"]) if paths["testFlightRunProof"].exists() else {}
    background = read_json(paths["backgroundUploadBundle"]) if paths["backgroundUploadBundle"].exists() else {}
    launch = read_json(paths["launchEvidence"]) if paths["launchEvidence"].exists() else {}

    if testflight:
        if testflight.get("testFlightRunProofReady") is not True:
            blockers.append("TestFlight run proof is present but not ready.")
        if args.commit and nested(testflight, "run", "headSha") != args.commit:
            blockers.append("TestFlight run proof commit does not match expected commit.")
        if args.build and testflight.get("expectedTestFlightBuild") != args.build:
            blockers.append("TestFlight run proof build does not match expected build.")

    if background:
        if background.get("backgroundUploadEvidenceReady") is not True:
            blockers.append("Background-upload evidence bundle is present but not ready.")
        if background.get("privacyScanPassed") is not True:
            blockers.append("Background-upload evidence privacy scan did not pass.")
        if args.commit and background.get("commit") != args.commit:
            blockers.append("Background-upload evidence commit does not match expected commit.")
        if args.build and background.get("testFlightBuild") != args.build:
            blockers.append("Background-upload evidence build does not match expected build.")

    if launch:
        if launch.get("backgroundUploadLaunchEvidenceReady") is not True:
            blockers.append("Final launch evidence is present but not ready.")
        if args.commit and launch.get("requiredCommit") != args.commit:
            blockers.append("Final launch evidence commit does not match expected commit.")
        if args.build and launch.get("requiredTestFlightBuild") != args.build:
            blockers.append("Final launch evidence build does not match expected build.")

    ready = (
        bool(launch)
        and launch.get("backgroundUploadLaunchEvidenceReady") is True
        and not blockers
    )

    return {
        "backgroundUploadGoalProofReady": ready,
        "proofDir": str(proof_dir),
        "expectedCommit": args.commit,
        "expectedBuild": args.build,
        "files": files,
        "readySignals": {
            "testFlightRunProofReady": testflight.get("testFlightRunProofReady"),
            "backgroundUploadEvidenceReady": background.get("backgroundUploadEvidenceReady"),
            "backgroundUploadLaunchEvidenceReady": launch.get("backgroundUploadLaunchEvidenceReady"),
            "privacyScanPassed": background.get("privacyScanPassed"),
            "phoneProofReady": nested(background, "phoneEvidence", "backgroundUploadPhoneProofReady"),
            "appSwitchEvidence": nested(background, "phoneEvidence", "appSwitchEvidence"),
            "continuationReady": nested(background, "phoneEvidence", "continuationReady"),
            "backendUploadComplete": nested(background, "backendEvidence", "uploadComplete"),
            "backendDuplicateCompleteOk": nested(background, "backendEvidence", "duplicateCompleteOk"),
        },
        "blockers": list(dict.fromkeys(blockers)),
    }


def print_human(result: dict[str, Any]) -> None:
    print(f"backgroundUploadGoalProofReady: {str(result['backgroundUploadGoalProofReady']).lower()}")
    print(f"proofDir: {result['proofDir']}")
    signals = result["readySignals"]
    print("readySignals:")
    for key, value in signals.items():
        print(f"- {key}: {value if value is not None else 'missing'}")
    blockers = result.get("blockers") or []
    if blockers:
        print("blockers:")
        for blocker in blockers:
            print(f"- {blocker}")


def main() -> int:
    args = parse_args()
    result = evaluate(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)
    return 0 if result["backgroundUploadGoalProofReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

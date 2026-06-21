#!/usr/bin/env python3
"""Report whether a background-upload evidence bundle is launch-credible."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check a HoopClips background-upload evidence bundle."
    )
    parser.add_argument("bundle_path", help="Path to background-upload evidence bundle JSON.")
    parser.add_argument("--require-commit", help="Require this exact tested git commit.")
    parser.add_argument("--require-build", help="Require this exact TestFlight build.")
    parser.add_argument(
        "--allow-sample",
        action="store_true",
        help="Allow sample/rehearsal labels. Never use this for launch proof.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def read_bundle(path: str) -> dict[str, Any]:
    parsed = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Evidence bundle must be a JSON object.")
    return parsed


def nested(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def has_sample_marker(value: Any) -> bool:
    return "sample" in str(value or "").lower()


def evaluate(bundle: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    bundle_blockers = bundle.get("blockers") or []
    if not isinstance(bundle_blockers, list):
        blockers.append("Bundle blockers field is not a list.")
        bundle_blockers = []
    blockers.extend(str(item) for item in bundle_blockers)

    if bundle.get("backgroundUploadEvidenceReady") is not True:
        blockers.append("backgroundUploadEvidenceReady is not true.")
    if bundle.get("privacyScanPassed") is not True:
        blockers.append("privacyScanPassed is not true.")

    commit = bundle.get("commit")
    build = bundle.get("testFlightBuild")
    label = bundle.get("label")

    if args.require_commit and commit != args.require_commit:
        blockers.append(f"commit mismatch: expected {args.require_commit}, got {commit}")
    if args.require_build and build != args.require_build:
        blockers.append(f"TestFlight build mismatch: expected {args.require_build}, got {build}")

    if not args.allow_sample and any(
        has_sample_marker(value) for value in (label, commit, build)
    ):
        blockers.append("Bundle looks like sample/rehearsal evidence, not real launch proof.")

    if nested(bundle, "backendEvidence", "uploadComplete") is not True:
        blockers.append("Backend evidence does not prove uploadComplete=true.")
    if nested(bundle, "backendEvidence", "duplicateCompleteOk") is not True:
        blockers.append("Backend evidence does not prove duplicateCompleteOk=true.")
    if nested(bundle, "backendEvidence", "privacyScanPassed") is not True:
        blockers.append("Backend evidence privacy scan did not pass.")

    if nested(bundle, "phoneEvidence", "backgroundUploadPhoneProofReady") is not True:
        blockers.append("Phone evidence is not backgroundUploadPhoneProofReady=true.")
    if nested(bundle, "phoneEvidence", "appSwitchEvidence") is not True:
        blockers.append("Phone evidence does not prove app-switch/background activity.")
    if nested(bundle, "phoneEvidence", "continuationReady") is not True:
        blockers.append("Phone evidence does not prove continuation into analysis/review.")
    if nested(bundle, "phoneEvidence", "privacyScanPassed") is not True:
        blockers.append("Phone evidence privacy scan did not pass.")

    if not commit:
        blockers.append("Bundle is missing tested commit.")
    if not build:
        blockers.append("Bundle is missing TestFlight build.")

    parsed_fields = nested(bundle, "phoneEvidence", "parsedFieldCount")
    if isinstance(parsed_fields, int) and parsed_fields < 8:
        warnings.append("Phone proof parsed very few fields; inspect evidence quality manually.")

    unique_blockers = list(dict.fromkeys(blockers))
    status = "ready" if not unique_blockers else "blocked"
    return {
        "status": status,
        "backgroundUploadLaunchCredible": status == "ready",
        "commit": commit,
        "testFlightBuild": build,
        "label": label,
        "blockers": unique_blockers,
        "warnings": warnings,
    }


def print_human(result: dict[str, Any]) -> None:
    print(f"status: {result['status']}")
    print(f"backgroundUploadLaunchCredible: {str(result['backgroundUploadLaunchCredible']).lower()}")
    print(f"commit: {result.get('commit') or 'missing'}")
    print(f"testFlightBuild: {result.get('testFlightBuild') or 'missing'}")
    blockers = result.get("blockers") or []
    warnings = result.get("warnings") or []
    if blockers:
        print("blockers:")
        for blocker in blockers:
            print(f"- {blocker}")
    if warnings:
        print("warnings:")
        for warning in warnings:
            print(f"- {warning}")


def main() -> int:
    args = parse_args()
    try:
        bundle = read_bundle(args.bundle_path)
        result = evaluate(bundle, args)
    except Exception as exc:
        result = {
            "status": "blocked",
            "backgroundUploadLaunchCredible": False,
            "blockers": [str(exc)],
            "warnings": [],
        }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

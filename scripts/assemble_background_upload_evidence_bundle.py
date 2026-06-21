#!/usr/bin/env python3
"""Assemble sanitized HoopClips background-upload evidence.

The output is a compact JSON bundle that links:
- backend resumable/chunked upload smoke evidence
- real-device/TestFlight phone proof
- tested commit/build metadata

Raw proof contents are intentionally not embedded in the bundle.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def load_checker() -> Any:
    checker_path = Path(__file__).with_name("verify_background_upload_phone_proof.py")
    spec = importlib.util.spec_from_file_location(
        "verify_background_upload_phone_proof", checker_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load proof checker from {checker_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a sanitized end-to-end background upload evidence bundle."
    )
    parser.add_argument(
        "--backend-evidence",
        required=True,
        help="Sanitized backend resumable upload smoke evidence JSON/text.",
    )
    parser.add_argument(
        "--phone-proof",
        required=True,
        help="Copied real-device/TestFlight phone proof text/JSON.",
    )
    parser.add_argument("--commit", required=True, help="Git commit tested end-to-end.")
    parser.add_argument("--build", required=True, help="TestFlight build number tested.")
    parser.add_argument(
        "--out",
        help="Where to write the JSON bundle. Defaults to stdout.",
    )
    parser.add_argument(
        "--label",
        default="background-upload-e2e",
        help="Short label for this evidence bundle.",
    )
    return parser.parse_args()


def parse_json_or_empty(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def bool_from_any(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value != 0
    lowered = str(value).strip().lower()
    if lowered in {"true", "yes", "1", "pass", "passed", "ok", "ready"}:
        return True
    if lowered in {"false", "no", "0", "fail", "failed", "blocked"}:
        return False
    return None


def lookup_nested(data: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in data:
            return data[name]
        current: Any = data
        found = True
        for part in name.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found:
            return current
    return None


def summarize_backend_evidence(text: str, checker: Any) -> dict[str, Any]:
    data = parse_json_or_empty(text)
    sensitive_hits = checker.scan_sensitive(text)
    started_fresh = bool_from_any(
        lookup_nested(data, "startedFromFreshState", "sequence.startedFromFreshState")
    )
    upload_complete = bool_from_any(
        lookup_nested(data, "uploadComplete", "final.uploadComplete", "sequence.uploadComplete")
    )
    duplicate_complete = bool_from_any(
        lookup_nested(
            data,
            "duplicateCompleteOk",
            "duplicateCompleteIdempotent",
            "serverMultipartCompleteIdempotent",
            "final.duplicateCompleteOk",
        )
    )
    privacy_check = bool_from_any(
        lookup_nested(
            data,
            "sanitizedEvidencePrivacyCheck",
            "privacyScanPassed",
            "privacy.passed",
        )
    )

    blockers: list[str] = []
    if sensitive_hits:
        blockers.append("Backend evidence contains sensitive-looking values.")
    if not data:
        blockers.append("Backend evidence was not parseable JSON.")
    if started_fresh is not True:
        blockers.append("Backend evidence does not prove a fresh resumable smoke sequence.")
    if upload_complete is not True:
        blockers.append("Backend evidence does not prove upload completion.")
    if duplicate_complete is not True:
        blockers.append("Backend evidence does not prove duplicate-safe multipart completion.")
    if privacy_check is not True and sensitive_hits:
        blockers.append("Backend evidence privacy check did not pass.")

    return {
        "provided": True,
        "parseableJson": bool(data),
        "privacyScanPassed": not sensitive_hits,
        "sensitiveHitKinds": sensitive_hits,
        "startedFromFreshState": started_fresh,
        "uploadComplete": upload_complete,
        "duplicateCompleteOk": duplicate_complete,
        "sanitizedEvidencePrivacyCheck": privacy_check,
        "blockers": blockers,
    }


def assemble(args: argparse.Namespace) -> dict[str, Any]:
    checker = load_checker()
    backend_text = Path(args.backend_evidence).read_text(encoding="utf-8")
    phone_text = Path(args.phone_proof).read_text(encoding="utf-8")

    backend = summarize_backend_evidence(backend_text, checker)
    phone = checker.evaluate(phone_text)
    created_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    blockers: list[str] = []
    blockers.extend(f"backend: {item}" for item in backend["blockers"])
    blockers.extend(f"phone: {item}" for item in phone.get("blockers", []))

    privacy_passed = (
        backend["privacyScanPassed"] is True
        and phone.get("privacyScanPassed") is True
    )
    ready = (
        not blockers
        and backend["uploadComplete"] is True
        and backend["duplicateCompleteOk"] is True
        and phone.get("backgroundUploadPhoneProofReady") is True
        and privacy_passed
    )

    return {
        "label": args.label,
        "createdAt": created_at,
        "commit": args.commit,
        "testFlightBuild": args.build,
        "backgroundUploadEvidenceReady": ready,
        "privacyScanPassed": privacy_passed,
        "backendEvidence": backend,
        "phoneEvidence": {
            "status": phone.get("status"),
            "backgroundUploadPhoneProofReady": phone.get("backgroundUploadPhoneProofReady"),
            "privacyScanPassed": phone.get("privacyScanPassed"),
            "pipelineStage": phone.get("pipelineStage"),
            "uploadComplete": phone.get("uploadComplete"),
            "activeUploadSessions": phone.get("activeUploadSessions"),
            "nextAction": phone.get("nextAction"),
            "staleWithoutActiveSession": phone.get("staleWithoutActiveSession"),
            "appSwitchEvidence": phone.get("appSwitchEvidence"),
            "continuationReady": phone.get("continuationReady"),
            "parsedFieldCount": phone.get("parsedFieldCount"),
        },
        "blockers": blockers,
        "safetyNote": "Raw proof contents are not embedded. Do not attach presigned URLs, local paths, upload IDs, job IDs, object keys, or upload headers.",
    }


def main() -> int:
    args = parse_args()
    bundle = assemble(args)
    output = json.dumps(bundle, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if bundle["backgroundUploadEvidenceReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

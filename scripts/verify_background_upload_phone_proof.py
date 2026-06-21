#!/usr/bin/env python3
"""Check sanitized real-device background upload proof.

This script is intentionally conservative. It does not prove the upload by
itself; it checks whether copied iPhone/TestFlight proof contains the evidence
we need to say a large upload survived app switching/backgrounding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("url", re.compile(r"https?://", re.IGNORECASE)),
    ("local_path", re.compile(r"(^|[\\s\"'=:/])/(Users|var|private|tmp)/", re.IGNORECASE)),
    (
        "sensitive_field",
        re.compile(
            r"\\b(uploadUrl|sourceObjectKey|sourcePath|uploadHeaders|uploadId|jobId)\\b\\s*[:=]",
            re.IGNORECASE,
        ),
    ),
    ("presigned_fragment", re.compile(r"X-Amz-|AWSAccessKeyId|Signature=|Expires=", re.IGNORECASE)),
    ("r2_object_reference", re.compile(r"r2\\.cloudflarestorage|source-object|object-key", re.IGNORECASE)),
]

SAFE_NEXT_ACTIONS = {
    "wait_for_background_session",
    "resume_upload",
    "start_cloud_analysis",
    "run_team_scan",
}

ANALYSIS_OR_REVIEW_STAGES = {
    "analyzing",
    "analysis",
    "review_ready",
    "review ready",
    "ready",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify sanitized HoopClips background upload phone proof."
    )
    parser.add_argument(
        "proof_path",
        nargs="?",
        help="Path to copied proof JSON/text. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of the short human report.",
    )
    return parser.parse_args()


def read_input(proof_path: str | None) -> str:
    if proof_path:
        return Path(proof_path).read_text(encoding="utf-8")
    return sys.stdin.read()


def parse_scalar(value: str) -> Any:
    normalized = value.strip().strip(",")
    lowered = normalized.lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    if lowered in {"null", "nil", "none"}:
        return None
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized.strip('"').strip("'")


def parse_loose_key_value(text: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip().strip(",")
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
        elif "=" in line:
            key, value = line.split("=", 1)
        else:
            continue
        key = key.strip().strip('"').strip("'")
        if not key:
            continue
        values[key] = parse_scalar(value)
    return values


def parse_proof(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return parse_loose_key_value(text)
    if isinstance(parsed, dict):
        return parsed
    return {"proof": parsed}


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten(child, child_prefix))
        return flattened
    return {prefix: value}


def lookup(flat: dict[str, Any], *keys: str) -> Any:
    lowered = {key.lower(): value for key, value in flat.items()}
    for key in keys:
        if key in flat:
            return flat[key]
        lowered_key = key.lower()
        if lowered_key in lowered:
            return lowered[lowered_key]
    return None


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value != 0
    lowered = str(value).strip().lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    return None


def as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def scan_sensitive(text: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            hits.append(label)
    return sorted(set(hits))


def evaluate(text: str) -> dict[str, Any]:
    proof = parse_proof(text)
    flat = flatten(proof)

    pipeline_stage = as_text(
        lookup(flat, "pipelineStage", "pipeline.stage", "stage", "pipeline")
    )
    stage_lower = pipeline_stage.lower().replace("_", " ")
    next_action = as_text(
        lookup(
            flat,
            "nextAction",
            "pendingBackgroundUploadManifest.nextAction",
            "backgroundUpload.nextAction",
        )
    )

    upload_complete = as_bool(
        lookup(
            flat,
            "uploadComplete",
            "pendingBackgroundUploadManifest.uploadComplete",
            "backgroundUpload.uploadComplete",
        )
    )
    active_sessions = as_bool(
        lookup(
            flat,
            "activeUploadSessions",
            "pendingBackgroundUploadManifest.activeUploadSessions",
        )
    )
    stale_without_session = as_bool(
        lookup(
            flat,
            "staleWithoutActiveSession",
            "pendingBackgroundUploadManifest.staleWithoutActiveSession",
        )
    )

    completed_while_away = as_bool(
        lookup(
            flat,
            "completedWhileAway",
            "backgroundUploadCompletionProof.completedWhileAway",
        )
    )
    wake_received = as_bool(
        lookup(flat, "wakeReceived", "backgroundUploadCompletionProof.wakeReceived")
    )
    relaunch_completion = as_bool(
        lookup(
            flat,
            "relaunchCompletion",
            "backgroundUploadCompletionProof.relaunchCompletion",
        )
    )
    inferred_source_completion = as_bool(
        lookup(
            flat,
            "inferredSourceCompletion",
            "backgroundUploadCompletionProof.inferredSourceCompletion",
        )
    )
    backgrounded_during_upload = as_bool(
        lookup(flat, "backgroundedDuringUpload", "appSwitchDuringUpload")
    )

    sensitive_hits = scan_sensitive(text)
    upload_terminal = upload_complete is True or any(
        stage in stage_lower for stage in ANALYSIS_OR_REVIEW_STAGES
    )
    app_switch_evidence = any(
        flag is True
        for flag in (
            completed_while_away,
            wake_received,
            relaunch_completion,
            inferred_source_completion,
            backgrounded_during_upload,
        )
    )
    safe_next_action = not next_action or next_action in SAFE_NEXT_ACTIONS
    stale_dead_session = (
        stale_without_session is True
        and active_sessions is False
        and upload_complete is not True
    )
    continuation_ready = upload_complete is True or next_action in {
        "start_cloud_analysis",
        "run_team_scan",
    } or any(stage in stage_lower for stage in ANALYSIS_OR_REVIEW_STAGES)

    blockers: list[str] = []
    if not proof:
        blockers.append("No proof fields were parsed.")
    if sensitive_hits:
        blockers.append(
            "Proof is not sanitized. Remove URLs, local paths, raw upload IDs, job IDs, object keys, and presigned fragments."
        )
    if not upload_terminal:
        blockers.append("Upload completion or analysis/review continuation is not proven.")
    if not app_switch_evidence:
        blockers.append("No app-switch/background evidence flag is present.")
    if not safe_next_action:
        blockers.append(f"Unexpected nextAction: {next_action}")
    if stale_dead_session:
        blockers.append(
            "Upload handoff is stale with no active background session and no completed upload."
        )
    if not continuation_ready:
        blockers.append("Proof does not show a safe continuation into analysis or review.")

    status = "pass" if not blockers else "blocked"
    return {
        "status": status,
        "backgroundUploadPhoneProofReady": status == "pass",
        "privacyScanPassed": not sensitive_hits,
        "sensitiveHitKinds": sensitive_hits,
        "parsedFieldCount": len(flat),
        "pipelineStage": pipeline_stage or None,
        "uploadComplete": upload_complete,
        "activeUploadSessions": active_sessions,
        "nextAction": next_action or None,
        "staleWithoutActiveSession": stale_without_session,
        "appSwitchEvidence": app_switch_evidence,
        "continuationReady": continuation_ready,
        "blockers": blockers,
    }


def print_human(result: dict[str, Any]) -> None:
    print(f"status: {result['status']}")
    print(f"backgroundUploadPhoneProofReady: {str(result['backgroundUploadPhoneProofReady']).lower()}")
    print(f"privacyScanPassed: {str(result['privacyScanPassed']).lower()}")
    print(f"parsedFieldCount: {result['parsedFieldCount']}")
    if result.get("pipelineStage"):
        print(f"pipelineStage: {result['pipelineStage']}")
    if result.get("nextAction"):
        print(f"nextAction: {result['nextAction']}")
    blockers = result.get("blockers") or []
    if blockers:
        print("blockers:")
        for blocker in blockers:
            print(f"- {blocker}")


def main() -> int:
    args = parse_args()
    text = read_input(args.proof_path)
    result = evaluate(text)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

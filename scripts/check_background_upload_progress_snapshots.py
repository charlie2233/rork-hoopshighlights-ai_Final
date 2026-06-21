#!/usr/bin/env python3
"""Compare HoopClips upload proof snapshots around app switching.

This checker answers a narrow question for real-device testing:

Did upload progress survive app switching, continue, complete, or move into
analysis/review after the app returned?
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

CONTINUATION_STAGES = {"analyzing", "analysis", "review ready", "review_ready", "ready"}
SAFE_NEXT_ACTIONS = {"start_cloud_analysis", "run_team_scan", "resume_upload", "wait_for_background_session"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare before/after HoopClips background-upload proof snapshots."
    )
    parser.add_argument("--before", required=True, help="Proof copied before switching apps.")
    parser.add_argument("--after", required=True, help="Proof copied after returning to HoopClips.")
    parser.add_argument("--final", help="Optional final proof after upload/analysis continuation.")
    parser.add_argument(
        "--min-progress-delta",
        type=float,
        default=0.01,
        help="Minimum progress increase that counts as movement. Default: 0.01.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def scan_sensitive(text: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            hits.append(label)
    return sorted(set(hits))


def parse_scalar(value: str) -> Any:
    normalized = value.strip().strip(",")
    lowered = normalized.lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    if lowered in {"null", "nil", "none", "missing"}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return normalized.strip('"').strip("'")


def parse_proof(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return flatten(parsed)

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
        if key:
            values[key] = parse_scalar(value)
    return values


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten(child, child_prefix))
        return flattened
    return {prefix: value}


def lookup(values: dict[str, Any], *names: str) -> Any:
    lowered = {key.lower(): value for key, value in values.items()}
    for name in names:
        if name in values:
            return values[name]
        lowered_name = name.lower()
        if lowered_name in lowered:
            return lowered[lowered_name]
    return None


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in {"true", "yes", "1"}:
        return True
    if lowered in {"false", "no", "0"}:
        return False
    return None


def stage_text(values: dict[str, Any]) -> str:
    return str(lookup(values, "pipelineStage", "pipeline.stage", "stage") or "").strip()


def upload_progress(values: dict[str, Any], fallback_names: tuple[str, ...] = ()) -> float | None:
    return as_float(lookup(values, "uploadProgress", "upload.progress", *fallback_names))


def summarize_file(path: str) -> tuple[str, dict[str, Any], list[str]]:
    text = Path(path).read_text(encoding="utf-8")
    return text, parse_proof(text), scan_sensitive(text)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    before_text, before, before_sensitive = summarize_file(args.before)
    after_text, after, after_sensitive = summarize_file(args.after)
    final: dict[str, Any] = {}
    final_sensitive: list[str] = []
    if args.final:
        _final_text, final, final_sensitive = summarize_file(args.final)

    before_progress = upload_progress(before, ("beforeSwitch.uploadProgress",))
    after_progress = upload_progress(after, ("afterSwitch.uploadProgress",))
    final_progress = upload_progress(final) if final else None

    after_stage = stage_text(after).lower().replace("_", " ")
    final_stage = stage_text(final).lower().replace("_", " ") if final else ""
    after_upload_complete = as_bool(lookup(after, "uploadComplete", "afterSwitch.uploadComplete"))
    final_upload_complete = as_bool(lookup(final, "uploadComplete")) if final else None
    after_next_action = str(lookup(after, "nextAction", "afterSwitch.nextAction") or "")
    final_next_action = str(lookup(final, "nextAction") or "")

    progress_delta = None
    if before_progress is not None and after_progress is not None:
        progress_delta = after_progress - before_progress

    moved = progress_delta is not None and progress_delta >= args.min_progress_delta
    completed = after_upload_complete is True or final_upload_complete is True
    continued = any(stage in after_stage for stage in CONTINUATION_STAGES) or any(
        stage in final_stage for stage in CONTINUATION_STAGES
    )
    safe_action = after_next_action in SAFE_NEXT_ACTIONS or final_next_action in SAFE_NEXT_ACTIONS
    stale_dead_session = (
        as_bool(lookup(after, "staleWithoutActiveSession", "afterSwitch.staleWithoutActiveSession")) is True
        and after_upload_complete is not True
    )

    blockers: list[str] = []
    warnings: list[str] = []
    sensitive_hits = sorted(set(before_sensitive + after_sensitive + final_sensitive))
    if sensitive_hits:
        blockers.append("Proof snapshots contain sensitive-looking values.")
    if before_progress is None:
        blockers.append("Before-switch uploadProgress is missing or not numeric.")
    if after_progress is None and not completed and not continued:
        blockers.append("After-switch proof lacks numeric uploadProgress, completion, or continuation.")
    if stale_dead_session:
        blockers.append("After-switch proof shows stale upload handoff without completion.")
    if not moved and not completed and not continued and not safe_action:
        blockers.append("No progress movement, completion, continuation, or safe resume action is proven.")
    if progress_delta is not None and progress_delta < 0:
        warnings.append("Upload progress decreased; check whether this came from a different project/run.")
    if progress_delta is not None and 0 <= progress_delta < args.min_progress_delta and not completed and not continued:
        warnings.append("Upload progress did not move enough to prove forward motion.")

    status = "pass" if not blockers else "blocked"
    return {
        "status": status,
        "backgroundUploadProgressSurvived": status == "pass",
        "privacyScanPassed": not sensitive_hits,
        "sensitiveHitKinds": sensitive_hits,
        "beforeProgress": before_progress,
        "afterProgress": after_progress,
        "finalProgress": final_progress,
        "progressDelta": progress_delta,
        "moved": moved,
        "completed": completed,
        "continuedIntoAnalysisOrReview": continued,
        "safeNextAction": safe_action,
        "blockers": blockers,
        "warnings": warnings,
    }


def print_human(result: dict[str, Any]) -> None:
    print(f"status: {result['status']}")
    print(f"backgroundUploadProgressSurvived: {str(result['backgroundUploadProgressSurvived']).lower()}")
    print(f"privacyScanPassed: {str(result['privacyScanPassed']).lower()}")
    print(f"beforeProgress: {result.get('beforeProgress')}")
    print(f"afterProgress: {result.get('afterProgress')}")
    print(f"progressDelta: {result.get('progressDelta')}")
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
    result = evaluate(args)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_human(result)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

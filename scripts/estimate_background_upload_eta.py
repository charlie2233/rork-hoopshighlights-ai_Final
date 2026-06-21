#!/usr/bin/env python3
"""Estimate HoopClips upload speed/ETA from real-device proof snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
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

SIZE_PATTERN = re.compile(r"(?P<num>\\d+(?:\\.\\d+)?)\\s*(?P<unit>kb|mb|gb|kib|mib|gib|bytes?|b)\\b", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate upload speed and ETA from HoopClips proof snapshots."
    )
    parser.add_argument("--before", required=True, help="Proof copied before switching apps.")
    parser.add_argument("--after", required=True, help="Proof copied after returning to HoopClips.")
    parser.add_argument(
        "--file-size-bytes",
        type=float,
        help="Optional source file size in bytes. Overrides size parsed from proof.",
    )
    parser.add_argument(
        "--min-progress-delta",
        type=float,
        default=0.005,
        help="Minimum progress delta that counts as movement. Default: 0.005.",
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


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten(child, child_prefix))
        return flattened
    return {prefix: value}


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


def parse_time(value: Any) -> dt.datetime | None:
    if value in (None, ""):
        return None
    raw = str(value).strip().strip('"').strip("'")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def parse_size_bytes(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value)
    match = SIZE_PATTERN.search(text)
    if not match:
        return None
    number = float(match.group("num"))
    unit = match.group("unit").lower()
    multipliers = {
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
    }
    return number * multipliers[unit]


def proof_time(values: dict[str, Any]) -> dt.datetime | None:
    return parse_time(
        lookup(
            values,
            "savedAt",
            "createdAt",
            "capturedAt",
            "lastUpdatedAt",
            "queuedAt",
            "proofSavedAt",
            "backgroundUploadProofSavedAt",
        )
    )


def upload_progress(values: dict[str, Any]) -> float | None:
    return as_float(
        lookup(
            values,
            "uploadProgress",
            "upload.progress",
            "beforeSwitch.uploadProgress",
            "afterSwitch.uploadProgress",
            "progress",
        )
    )


def source_size(values: dict[str, Any], override: float | None) -> float | None:
    if override is not None:
        return override
    for name in (
        "sourceVideoApproxSize",
        "sourceFileSizeBytes",
        "fileSizeBytes",
        "uploadTotalBytes",
        "totalBytes",
    ):
        parsed = parse_size_bytes(lookup(values, name))
        if parsed is not None:
            return parsed
    return None


def seconds_to_label(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    if seconds < 0:
        return None
    minutes, sec = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    before_text = Path(args.before).read_text(encoding="utf-8")
    after_text = Path(args.after).read_text(encoding="utf-8")
    before = parse_proof(before_text)
    after = parse_proof(after_text)

    sensitive_hits = sorted(set(scan_sensitive(before_text) + scan_sensitive(after_text)))
    before_progress = upload_progress(before)
    after_progress = upload_progress(after)
    before_time = proof_time(before)
    after_time = proof_time(after)
    size_bytes = source_size(after, args.file_size_bytes) or source_size(before, args.file_size_bytes)

    blockers: list[str] = []
    warnings: list[str] = []
    if sensitive_hits:
        blockers.append("Proof snapshots contain sensitive-looking values.")
    if before_progress is None:
        blockers.append("Before snapshot is missing numeric uploadProgress.")
    if after_progress is None:
        blockers.append("After snapshot is missing numeric uploadProgress.")
    if before_time is None:
        blockers.append("Before snapshot is missing an ISO timestamp.")
    if after_time is None:
        blockers.append("After snapshot is missing an ISO timestamp.")

    elapsed_seconds: float | None = None
    progress_delta: float | None = None
    progress_per_second: float | None = None
    estimated_remaining_seconds: float | None = None
    bytes_per_second: float | None = None
    moved = False

    if before_time and after_time:
        elapsed_seconds = (after_time - before_time).total_seconds()
        if elapsed_seconds <= 0:
            blockers.append("After snapshot timestamp is not later than before snapshot.")

    if before_progress is not None and after_progress is not None:
        progress_delta = after_progress - before_progress
        moved = progress_delta >= args.min_progress_delta
        if progress_delta < 0:
            warnings.append("Upload progress decreased; snapshots may be from different runs.")
        if progress_delta >= 0 and not moved:
            warnings.append("Upload progress moved less than the minimum delta.")

    if elapsed_seconds and elapsed_seconds > 0 and progress_delta is not None and progress_delta > 0:
        progress_per_second = progress_delta / elapsed_seconds
        remaining = max(0.0, 1.0 - max(after_progress or 0.0, 0.0))
        estimated_remaining_seconds = remaining / progress_per_second if progress_per_second > 0 else None
        if size_bytes:
            bytes_per_second = (progress_delta * size_bytes) / elapsed_seconds

    if not moved and (after_progress or 0) < 1:
        blockers.append("Snapshots do not prove meaningful upload movement.")

    status = "pass" if not blockers else "blocked"
    return {
        "status": status,
        "uploadEtaEvidenceReady": status == "pass",
        "privacyScanPassed": not sensitive_hits,
        "sensitiveHitKinds": sensitive_hits,
        "beforeProgress": before_progress,
        "afterProgress": after_progress,
        "progressDelta": progress_delta,
        "elapsedSeconds": elapsed_seconds,
        "progressPerSecond": progress_per_second,
        "estimatedRemainingSeconds": estimated_remaining_seconds,
        "estimatedRemainingLabel": seconds_to_label(estimated_remaining_seconds),
        "sourceSizeBytes": size_bytes,
        "estimatedBytesPerSecond": bytes_per_second,
        "estimatedMbps": (bytes_per_second * 8 / 1_000_000) if bytes_per_second else None,
        "blockers": blockers,
        "warnings": warnings,
    }


def print_human(result: dict[str, Any]) -> None:
    print(f"status: {result['status']}")
    print(f"uploadEtaEvidenceReady: {str(result['uploadEtaEvidenceReady']).lower()}")
    print(f"privacyScanPassed: {str(result['privacyScanPassed']).lower()}")
    print(f"progressDelta: {result.get('progressDelta')}")
    print(f"elapsedSeconds: {result.get('elapsedSeconds')}")
    print(f"estimatedRemaining: {result.get('estimatedRemainingLabel') or 'unknown'}")
    if result.get("estimatedMbps") is not None:
        print(f"estimatedMbps: {result['estimatedMbps']:.2f}")
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

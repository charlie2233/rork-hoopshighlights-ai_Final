#!/usr/bin/env python3
"""Redact unsafe values from copied HoopClips background-upload phone proof.

Use this before sharing proof in chat or attaching it to a launch packet if the
raw copy accidentally includes URLs, local paths, upload IDs, job IDs, object
keys, headers, or presigned fragments.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


FIELD_REDACTIONS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "upload_url",
        re.compile(r"(?im)^(\s*(?:uploadUrl|url)\s*[:=]\s*)(.+)$"),
        "[REDACTED_URL]",
    ),
    (
        "source_object_key",
        re.compile(r"(?im)^(\s*(?:sourceObjectKey|objectKey|r2ObjectKey)\s*[:=]\s*)(.+)$"),
        "[REDACTED_OBJECT_KEY]",
    ),
    (
        "local_path",
        re.compile(r"(?im)^(\s*(?:sourcePath|localPath|filePath|videoPath)\s*[:=]\s*)(.+)$"),
        "[REDACTED_LOCAL_PATH]",
    ),
    (
        "upload_headers",
        re.compile(r"(?im)^(\s*(?:uploadHeaders|headers|authorization)\s*[:=]\s*)(.+)$"),
        "[REDACTED_HEADERS]",
    ),
    (
        "upload_id",
        re.compile(r"(?im)^(\s*(?:uploadId|multipartUploadId)\s*[:=]\s*)(.+)$"),
        "[REDACTED_UPLOAD_ID]",
    ),
    (
        "job_id",
        re.compile(r"(?im)^(\s*(?:jobId|renderJobId|analysisJobId)\s*[:=]\s*)(.+)$"),
        "[REDACTED_JOB_ID]",
    ),
]

INLINE_REDACTIONS: list[tuple[str, re.Pattern[str], str]] = [
    ("url", re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE), "[REDACTED_URL]"),
    (
        "local_path",
        re.compile(r"(?<![A-Za-z0-9_])/(?:Users|var|private|tmp)/[^\s\"'<>]+", re.IGNORECASE),
        "[REDACTED_LOCAL_PATH]",
    ),
    (
        "presigned_fragment",
        re.compile(r"(?:X-Amz-[A-Za-z0-9_-]+|AWSAccessKeyId|Signature|Expires)=[^\s&\"'<>]+", re.IGNORECASE),
        "[REDACTED_PRESIGNED_FRAGMENT]",
    ),
    (
        "r2_reference",
        re.compile(r"\b[^\s\"'<>]*(?:r2\.cloudflarestorage|source-object|object-key)[^\s\"'<>]*", re.IGNORECASE),
        "[REDACTED_OBJECT_REFERENCE]",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Redact unsafe HoopClips background-upload phone proof."
    )
    parser.add_argument("proof_path", help="Raw copied proof text/JSON.")
    parser.add_argument("--out", help="Write redacted proof here. Defaults to stdout.")
    parser.add_argument(
        "--report",
        help="Write JSON redaction report here.",
    )
    parser.add_argument(
        "--fail-if-changed",
        action="store_true",
        help="Exit non-zero if any redaction was needed.",
    )
    return parser.parse_args()


def apply_redactions(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    redacted = text

    for label, pattern, replacement in FIELD_REDACTIONS:
        def replace_field(match: re.Match[str]) -> str:
            counts[label] = counts.get(label, 0) + 1
            return match.group(1) + replacement

        redacted = pattern.sub(replace_field, redacted)

    for label, pattern, replacement in INLINE_REDACTIONS:
        redacted, changed = pattern.subn(replacement, redacted)
        if changed:
            counts[label] = counts.get(label, 0) + changed

    return redacted, counts


def main() -> int:
    args = parse_args()
    original = Path(args.proof_path).read_text(encoding="utf-8")
    redacted, counts = apply_redactions(original)
    changed = redacted != original

    if args.out:
        Path(args.out).write_text(redacted, encoding="utf-8")
    else:
        print(redacted, end="")

    report = {
        "redacted": changed,
        "redactionCounts": counts,
        "safeToShareCandidate": True,
        "note": "Run verify_background_upload_phone_proof.py on the redacted proof before using it as evidence.",
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)

    return 1 if args.fail_if_changed and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())

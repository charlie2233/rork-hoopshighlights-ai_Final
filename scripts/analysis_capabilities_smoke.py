#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


REQUIRED_FIELDS = {
    "maxFileSizeBytes": int,
    "maxDurationSeconds": (int, float),
    "resumableUploadThresholdBytes": int,
    "supportsResumableUpload": bool,
    "recommendedUploadPreference": str,
    "signedUploadTtlSeconds": int,
    "defaultPollAfterSeconds": int,
    "analysisMode": str,
}


class CapabilitySmokeError(Exception):
    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


def main() -> int:
    args = parse_args()
    try:
        result = run_smoke(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except CapabilitySmokeError as error:
        payload = {
            "status": "fail",
            "error": str(error),
            **error.payload,
            "privacy": "no_secrets_no_presigned_urls_no_object_keys",
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe the public HoopClips Worker analysis capabilities endpoint. "
            "Output is sanitized and does not include full URLs, secrets, presigned URLs, or object keys."
        )
    )
    parser.add_argument("--worker-url", default=os.getenv("WORKER_BASE_URL"))
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("HOOPS_CAPABILITIES_SMOKE_TIMEOUT_SECONDS", "15")))
    args = parser.parse_args()
    if not args.worker_url:
        raise CapabilitySmokeError("WORKER_BASE_URL or --worker-url is required.")
    if args.timeout_seconds <= 0:
        raise CapabilitySmokeError("Timeout must be positive.", {"timeoutSeconds": args.timeout_seconds})
    return args


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.worker_url.rstrip("/") + "/"
    url = urljoin(base_url, "v1/analysis/capabilities")
    payload = request_json(url, timeout_seconds=args.timeout_seconds)
    findings = validate_capabilities(payload)
    split = urlsplit(base_url)
    return {
        "status": "pass" if all(finding["status"] == "pass" for finding in findings) else "fail",
        "worker": {
            "scheme": split.scheme or "unknown",
            "hostHash": stable_hash(split.netloc.lower()),
            "pathDepth": len([part for part in split.path.split("/") if part]),
        },
        "capabilities": sanitize_capabilities(payload),
        "findings": findings,
        "privacy": "no_secrets_no_presigned_urls_no_object_keys",
    }


def request_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, method="GET", headers={"accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            data = response.read()
            status = getattr(response, "status", 200)
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:500]
        raise CapabilitySmokeError(
            "Capabilities endpoint returned HTTP error.",
            {"httpStatus": error.code, "bodyPreview": body},
        ) from error
    except URLError as error:
        raise CapabilitySmokeError("Capabilities endpoint was unreachable.", {"reason": str(error.reason)}) from error

    if status < 200 or status >= 300:
        raise CapabilitySmokeError("Capabilities endpoint returned non-success status.", {"httpStatus": status})

    try:
        decoded = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise CapabilitySmokeError("Capabilities endpoint returned invalid JSON.") from error

    if not isinstance(decoded, dict):
        raise CapabilitySmokeError("Capabilities endpoint returned non-object JSON.")
    return decoded


def validate_capabilities(payload: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for field, expected_type in REQUIRED_FIELDS.items():
        value = payload.get(field)
        if isinstance(value, expected_type):
            findings.append({"status": "pass", "check": field, "detail": "present"})
        else:
            findings.append({"status": "fail", "check": field, "detail": f"missing_or_wrong_type:{type(value).__name__}"})

    if payload.get("supportsResumableUpload") is True:
        findings.append({"status": "pass", "check": "supports_resumable", "detail": "true"})
    else:
        findings.append({"status": "fail", "check": "supports_resumable", "detail": "expected_true"})

    if payload.get("recommendedUploadPreference") == "resumable":
        findings.append({"status": "pass", "check": "recommended_upload_preference", "detail": "resumable"})
    else:
        findings.append({
            "status": "fail",
            "check": "recommended_upload_preference",
            "detail": str(payload.get("recommendedUploadPreference")),
        })

    max_file_size = payload.get("maxFileSizeBytes")
    threshold = payload.get("resumableUploadThresholdBytes")
    if isinstance(max_file_size, int) and isinstance(threshold, int) and 0 < threshold <= max_file_size:
        findings.append({"status": "pass", "check": "resumable_threshold_range", "detail": "within_upload_limit"})
    else:
        findings.append({"status": "fail", "check": "resumable_threshold_range", "detail": "invalid"})

    return findings


def sanitize_capabilities(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "maxFileSizeBytes": payload.get("maxFileSizeBytes"),
        "maxDurationSeconds": payload.get("maxDurationSeconds"),
        "resumableUploadThresholdBytes": payload.get("resumableUploadThresholdBytes"),
        "supportsResumableUpload": payload.get("supportsResumableUpload"),
        "recommendedUploadPreference": payload.get("recommendedUploadPreference"),
        "signedUploadTtlSeconds": payload.get("signedUploadTtlSeconds"),
        "defaultPollAfterSeconds": payload.get("defaultPollAfterSeconds"),
        "analysisMode": payload.get("analysisMode"),
    }


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


if __name__ == "__main__":
    raise SystemExit(main())

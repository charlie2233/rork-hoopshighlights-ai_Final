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
SMOKE_USER_AGENT = "HoopClips-Capabilities-Smoke/1.0"


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
    parser.add_argument(
        "--check-policy-errors",
        action="store_true",
        help=(
            "Also POST synthetic over-limit analysis job requests and require structured policy errors. "
            "No upload is attempted; the check should fail before any presigned upload is issued."
        ),
    )
    parser.add_argument("--install-id", default=os.getenv("HOOPS_CAPABILITIES_SMOKE_INSTALL_ID", "capabilities-smoke-install"))
    parser.add_argument("--app-version", default=os.getenv("HOOPS_CAPABILITIES_SMOKE_APP_VERSION", "capabilities-smoke"))
    parser.add_argument("--analysis-version", default=os.getenv("HOOPS_CAPABILITIES_SMOKE_ANALYSIS_VERSION", "capabilities-smoke"))
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
    if args.check_policy_errors:
        findings.extend(validate_policy_errors(base_url, args, payload))
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
    status, decoded = request_json_response("GET", url, timeout_seconds=timeout_seconds)
    if status < 200 or status >= 300:
        raise CapabilitySmokeError("Endpoint returned non-success status.", {"httpStatus": status})
    return decoded


def request_json_response(
    method: str,
    url: str,
    timeout_seconds: float,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "accept": "application/json",
        "user-agent": SMOKE_USER_AGENT,
    }
    if body is not None:
        headers["content-type"] = "application/json"
    request = Request(url, method=method, data=body, headers=headers)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            data = response.read()
            status = getattr(response, "status", 200)
    except HTTPError as error:
        data = error.read()
        status = error.code
    except URLError as error:
        raise CapabilitySmokeError("Endpoint was unreachable.", {"reason": str(error.reason)}) from error

    try:
        decoded = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise CapabilitySmokeError("Endpoint returned invalid JSON.", {"httpStatus": status}) from error

    if not isinstance(decoded, dict):
        raise CapabilitySmokeError("Endpoint returned non-object JSON.", {"httpStatus": status})
    return status, decoded


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


def validate_policy_errors(base_url: str, args: argparse.Namespace, capabilities: dict[str, Any]) -> list[dict[str, str]]:
    max_file_size = capabilities.get("maxFileSizeBytes")
    max_duration = capabilities.get("maxDurationSeconds")
    findings: list[dict[str, str]] = []

    if isinstance(max_file_size, int):
        findings.append(
            validate_single_policy_error(
                base_url,
                args,
                check="policy_file_too_large",
                expected_error_code="file_too_large",
                file_size_bytes=max_file_size + 1,
                duration_seconds=safe_duration(max_duration),
            )
        )
    else:
        findings.append({"status": "fail", "check": "policy_file_too_large", "detail": "missing_max_file_size"})

    if isinstance(max_duration, (int, float)):
        findings.append(
            validate_single_policy_error(
                base_url,
                args,
                check="policy_unsupported_duration",
                expected_error_code="unsupported_duration",
                file_size_bytes=safe_file_size(max_file_size),
                duration_seconds=float(max_duration) + 1,
            )
        )
    else:
        findings.append({"status": "fail", "check": "policy_unsupported_duration", "detail": "missing_max_duration"})

    return findings


def validate_single_policy_error(
    base_url: str,
    args: argparse.Namespace,
    check: str,
    expected_error_code: str,
    file_size_bytes: int,
    duration_seconds: float,
) -> dict[str, str]:
    job_url = urljoin(base_url, "v1/analysis/jobs")
    payload = {
        "filename": "capabilities-policy-smoke.mp4",
        "contentType": "video/mp4",
        "fileSizeBytes": file_size_bytes,
        "durationSeconds": duration_seconds,
        "installId": args.install_id,
        "appVersion": args.app_version,
        "analysisVersion": args.analysis_version,
        "uploadPreference": "resumable",
    }
    try:
        status, response = request_json_response("POST", job_url, timeout_seconds=args.timeout_seconds, payload=payload)
    except CapabilitySmokeError as error:
        return {"status": "fail", "check": check, "detail": f"request_failed:{error}"}

    error_code = response.get("errorCode")
    if 400 <= status < 500 and error_code == expected_error_code:
        return {"status": "pass", "check": check, "detail": expected_error_code}
    if 200 <= status < 300:
        returned_upload_url = isinstance(response.get("uploadUrl"), str) or isinstance(response.get("sourceUploadUrl"), str)
        returned_job_id = isinstance(response.get("jobId"), str)
        return {
            "status": "fail",
            "check": check,
            "detail": f"unexpected_success:jobId={returned_job_id}:uploadUrl={returned_upload_url}",
        }
    return {
        "status": "fail",
        "check": check,
        "detail": f"http_{status}:errorCode={error_code}",
    }


def safe_file_size(max_file_size: Any) -> int:
    if isinstance(max_file_size, int) and max_file_size > 1:
        return max_file_size - 1
    return 1_000_000


def safe_duration(max_duration: Any) -> float:
    if isinstance(max_duration, (int, float)) and max_duration > 1:
        return float(max_duration) - 1
    return 10.0


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

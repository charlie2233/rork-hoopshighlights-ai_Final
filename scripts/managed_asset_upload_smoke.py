#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class ManagedAssetUploadSmokeError(Exception):
    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


def main() -> int:
    args = parse_args()
    try:
        result = run(args)
        assert_shareable_evidence(result)
        if args.evidence_path:
            write_evidence(args.evidence_path, result)
            result["evidenceWritten"] = True
            result["evidencePathHash"] = stable_hash(str(args.evidence_path))
            assert_shareable_evidence(result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except ManagedAssetUploadSmokeError as error:
        payload = sanitize_for_shareable_evidence(
            {
                "status": "fail",
                "error": str(error),
                **error.payload,
                "privacy": "no_secrets_no_presigned_urls_no_object_keys",
            }
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise the HoopClips asset-first upload path against a managed backend or Worker. "
            "Stdout is sanitized and never prints presigned URLs, upload IDs, object keys, or local file paths."
        )
    )
    parser.add_argument("--base-url", default=os.getenv("HOOPS_MANAGED_ASSET_UPLOAD_BASE_URL") or os.getenv("WORKER_BASE_URL"))
    parser.add_argument("--file", dest="file_path", type=Path)
    parser.add_argument("--generated-size-bytes", type=int, default=int(os.getenv("HOOPS_UPLOAD_SMOKE_BYTES", str(8 * 1024 * 1024))))
    parser.add_argument("--content-type")
    parser.add_argument("--duration-seconds", type=float, default=float(os.getenv("HOOPS_UPLOAD_SMOKE_DURATION_SECONDS", "60")))
    parser.add_argument("--install-id", default=os.getenv("HOOPS_UPLOAD_SMOKE_INSTALL_ID", "managed-asset-upload-smoke"))
    parser.add_argument("--app-version", default=os.getenv("HOOPS_UPLOAD_SMOKE_APP_VERSION", "managed-asset-upload-smoke"))
    parser.add_argument("--analysis-version", default=os.getenv("HOOPS_UPLOAD_SMOKE_ANALYSIS_VERSION", "managed-asset-upload-smoke"))
    parser.add_argument("--upload-preference", choices=["auto", "single", "multipart"], default=os.getenv("HOOPS_UPLOAD_SMOKE_PREFERENCE", "multipart"))
    parser.add_argument("--part-size-bytes", type=int, default=int(os.getenv("HOOPS_UPLOAD_SMOKE_PART_BYTES", str(4 * 1024 * 1024))))
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("HOOPS_UPLOAD_SMOKE_TIMEOUT_SECONDS", "90")))
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    parser.add_argument("--expect-multipart", action="store_true", default=os.getenv("HOOPS_UPLOAD_SMOKE_EXPECT_MULTIPART", "").lower() in {"1", "true", "yes"})
    parser.add_argument("--verify-duplicate-complete", action="store_true", default=True)
    parser.add_argument("--no-verify-duplicate-complete", dest="verify_duplicate_complete", action="store_false")
    parser.add_argument("--require-proxy-ready", action="store_true", default=True)
    parser.add_argument("--allow-processing", dest="require_proxy_ready", action="store_false")
    parser.add_argument("--evidence-path", type=Path)
    args = parser.parse_args()

    if not args.base_url:
        raise ManagedAssetUploadSmokeError("HOOPS_MANAGED_ASSET_UPLOAD_BASE_URL, WORKER_BASE_URL, or --base-url is required.")
    if args.generated_size_bytes <= 0:
        raise ManagedAssetUploadSmokeError("--generated-size-bytes must be positive.")
    if args.part_size_bytes <= 0:
        raise ManagedAssetUploadSmokeError("--part-size-bytes must be positive.")
    if args.timeout_seconds <= 0:
        raise ManagedAssetUploadSmokeError("--timeout-seconds must be positive.")
    if args.poll_interval_seconds <= 0:
        raise ManagedAssetUploadSmokeError("--poll-interval-seconds must be positive.")
    if args.file_path and not args.file_path.is_file():
        raise ManagedAssetUploadSmokeError("Upload source file does not exist.", {"filePathHash": stable_hash(str(args.file_path))})
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.base_url.rstrip("/")
    payload = load_payload(args.file_path, args.generated_size_bytes)
    filename = args.file_path.name if args.file_path else "managed-asset-upload-smoke.mp4"
    content_type = args.content_type or mimetypes.guess_type(filename)[0] or "video/mp4"
    started = time.perf_counter()

    capabilities = fetch_capabilities(base_url)
    init = json_request(
        "POST",
        f"{base_url}/v1/uploads/init",
        {
            "filename": filename,
            "contentType": content_type,
            "fileSizeBytes": len(payload),
            "durationSeconds": args.duration_seconds,
            "installId": args.install_id,
            "appVersion": args.app_version,
            "analysisVersion": args.analysis_version,
            "uploadPreference": args.upload_preference,
            "partSizeBytes": args.part_size_bytes,
        },
    )
    asset_id = require_str(init, "assetId")
    upload_mode = require_str(init, "uploadMode")
    if args.expect_multipart and upload_mode != "multipart":
        raise ManagedAssetUploadSmokeError(
            "Managed upload smoke expected multipart mode.",
            {"uploadMode": upload_mode, "assetIdHash": stable_hash(asset_id)},
        )

    upload_started = time.perf_counter()
    completed_parts: list[dict[str, Any]] = []
    upload_id: str | None = None
    part_count = 1
    if upload_mode == "multipart":
        multipart = require_dict(init, "multipart")
        upload_id = require_str(multipart, "uploadId")
        part_size = require_int(multipart, "partSizeBytes")
        part_count = require_int(multipart, "partCount")
        targets = require_list(multipart, "parts")
        for target in targets:
            target_payload = require_dict_value(target, "part")
            part_number = require_int(target_payload, "partNumber")
            start = (part_number - 1) * part_size
            chunk = payload[start : start + part_size]
            headers = put_bytes(
                require_str(target_payload, "uploadUrl"),
                chunk,
                target_payload.get("uploadHeaders") if isinstance(target_payload.get("uploadHeaders"), dict) else {},
            )
            etag = headers.get("ETag") or headers.get("etag")
            if not etag:
                raise ManagedAssetUploadSmokeError(
                    "Multipart upload part response did not include an ETag.",
                    {"assetIdHash": stable_hash(asset_id), "partNumber": part_number},
                )
            completed_parts.append({"partNumber": part_number, "etag": etag, "sizeBytes": len(chunk)})
        complete_payload = {"installId": args.install_id, "uploadId": upload_id, "parts": completed_parts}
    else:
        put_bytes(
            require_str(init, "uploadUrl"),
            payload,
            init.get("uploadHeaders") if isinstance(init.get("uploadHeaders"), dict) else {},
        )
        complete_payload = {"installId": args.install_id}
    upload_finished = time.perf_counter()

    complete = json_request("POST", f"{base_url}/v1/uploads/{asset_id}/complete", complete_payload)
    duplicate_complete: dict[str, Any] | None = None
    if args.verify_duplicate_complete:
        duplicate_complete = json_request(
            "POST",
            f"{base_url}/v1/uploads/{asset_id}/complete",
            {"installId": args.install_id, "uploadId": upload_id, "parts": []} if upload_id else {"installId": args.install_id},
        )

    final_asset = poll_asset(
        base_url,
        asset_id,
        args.install_id,
        args.timeout_seconds,
        args.poll_interval_seconds,
        initial=complete,
    )
    finished = time.perf_counter()
    final_status = str(final_asset.get("status") or complete.get("status") or "unknown")
    proxy_ready = final_status in {"proxy_ready", "ready"}
    allowed_processing = not args.require_proxy_ready and final_status == "processing"
    status = "pass" if proxy_ready or allowed_processing else "fail"

    result = sanitize_for_shareable_evidence(
        {
            "status": status,
            "mode": "managed_asset_upload_smoke",
            "baseUrl": base_url,
            "assetId": asset_id,
            "storageKey": init.get("storageKey"),
            "sourceObjectKey": final_asset.get("sourceObjectKey") or complete.get("sourceObjectKey"),
            "proxyKey": final_asset.get("proxyKey") or complete.get("proxyKey"),
            "uploadMode": upload_mode,
            "bytes": len(payload),
            "partCount": part_count,
            "completedParts": len(completed_parts) if completed_parts else (1 if upload_mode == "single" else 0),
            "capabilities": {
                "supportsMultipartUpload": capabilities.get("supportsMultipartUpload"),
                "supportsChecksumSha256": capabilities.get("supportsChecksumSha256"),
                "supportsCancellation": capabilities.get("supportsCancellation"),
                "supportsIdempotentComplete": capabilities.get("supportsIdempotentComplete"),
                "maxConcurrentPartUploads": capabilities.get("maxConcurrentPartUploads"),
            },
            "finalAssetStatus": final_status,
            "integrityStatus": final_asset.get("integrityStatus") or complete.get("integrityStatus"),
            "checksumSha256Present": bool(final_asset.get("checksumSha256") or complete.get("checksumSha256")),
            "duplicateCompleteProven": duplicate_complete is not None and duplicate_complete.get("assetId") == asset_id,
            "proxyReadyProven": proxy_ready,
            "uploadSeconds": round(upload_finished - upload_started, 4),
            "timeToFirstPreviewSeconds": round(finished - started, 4) if proxy_ready else None,
            "roundTripSeconds": round(finished - started, 4),
            "privacy": "no_secrets_no_presigned_urls_no_object_keys_no_raw_local_paths",
        }
    )
    if status != "pass":
        raise ManagedAssetUploadSmokeError(
            "Managed asset upload smoke did not reach the required asset state.",
            result,
        )
    return result


def fetch_capabilities(base_url: str) -> dict[str, Any]:
    for path in ("v1/uploads/capabilities", "v1/analysis/capabilities"):
        try:
            return json_request("GET", f"{base_url}/{path}")
        except ManagedAssetUploadSmokeError:
            continue
    return {}


def poll_asset(
    base_url: str,
    asset_id: str,
    install_id: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    initial: dict[str, Any],
) -> dict[str, Any]:
    latest = initial
    if str(latest.get("status") or "") in {"proxy_ready", "ready", "failed", "cancelled"}:
        return latest
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        latest = json_request("GET", f"{base_url}/v1/assets/{asset_id}?installId={install_id}")
        if str(latest.get("status") or "") in {"proxy_ready", "ready", "failed", "cancelled"}:
            return latest
        time.sleep(poll_interval_seconds)
    return latest


def json_request(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json"} if payload is not None else {}
    req = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=120) as response:
            raw = response.read()
    except HTTPError as error:
        raise http_error("JSON request failed.", error) from error
    except URLError as error:
        raise ManagedAssetUploadSmokeError("Network request failed.", {"reason": type(error.reason).__name__}) from error
    if not raw:
        return {}
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ManagedAssetUploadSmokeError("JSON request returned a non-object response.")
    return decoded


def put_bytes(url: str, payload: bytes, headers: dict[str, str] | None = None) -> dict[str, str]:
    req = Request(url, data=payload, method="PUT", headers=headers or {})
    try:
        with urlopen(req, timeout=180) as response:
            return dict(response.headers.items())
    except HTTPError as error:
        raise http_error("Upload request failed.", error) from error
    except URLError as error:
        raise ManagedAssetUploadSmokeError("Upload network request failed.", {"reason": type(error.reason).__name__}) from error


def http_error(message: str, error: HTTPError) -> ManagedAssetUploadSmokeError:
    payload: dict[str, Any] = {"httpStatus": error.code}
    raw = error.read().decode("utf-8", errors="replace")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        decoded = {}
    if isinstance(decoded, dict):
        payload["errorCode"] = decoded.get("errorCode") or decoded.get("code") or "unknown"
    return ManagedAssetUploadSmokeError(message, payload)


def load_payload(path: Path | None, generated_size_bytes: int) -> bytes:
    if path is not None:
        return path.read_bytes()
    return bytes(index % 251 for index in range(generated_size_bytes))


def write_evidence(evidence_path: Path, result: dict[str, Any]) -> None:
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence = sanitize_for_shareable_evidence(result)
    assert_shareable_evidence(evidence)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")


def sanitize_for_shareable_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"baseUrl", "assetId", "storageKey", "sourceObjectKey", "proxyKey", "uploadId", "uploadUrl", "filePath"}:
                sanitized[f"{key}Hash"] = stable_hash(str(item))
            elif key in {"uploadHeaders", "etag"}:
                sanitized[f"{key}Redacted"] = True
            else:
                sanitized[key] = sanitize_for_shareable_evidence(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_shareable_evidence(item) for item in value]
    return value


def assert_shareable_evidence(value: Any) -> None:
    leaks = find_shareable_evidence_leaks(value)
    if leaks:
        raise ManagedAssetUploadSmokeError(
            "Sanitized evidence failed privacy checks.",
            {
                "leakCount": len(leaks),
                "firstLeak": leaks[0],
                "privacy": "leak_paths_only_no_secret_values",
            },
        )


def find_shareable_evidence_leaks(value: Any, path: str = "$") -> list[dict[str, str]]:
    leaks: list[dict[str, str]] = []
    forbidden_keys = {"baseUrl", "assetId", "storageKey", "sourceObjectKey", "proxyKey", "uploadId", "uploadUrl", "filePath", "uploadHeaders"}
    forbidden_fragments = (
        "X-Amz-",
        "Signature=",
        "Credential=",
        "assets/",
        "uploads/",
        "renders/",
        "http://",
        "https://",
        "/Users/",
        "/private/",
        "/var/folders/",
        "file://",
    )
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in forbidden_keys:
                leaks.append({"path": child_path, "reason": "forbidden_key"})
            leaks.extend(find_shareable_evidence_leaks(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            leaks.extend(find_shareable_evidence_leaks(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        for fragment in forbidden_fragments:
            if fragment in value:
                leaks.append({"path": path, "reason": f"forbidden_fragment:{fragment}"})
                break
    return leaks


def require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ManagedAssetUploadSmokeError("Expected string field was missing.", {"field": key})
    return value


def require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ManagedAssetUploadSmokeError("Expected integer field was missing.", {"field": key})
    return value


def require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ManagedAssetUploadSmokeError("Expected object field was missing.", {"field": key})
    return value


def require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ManagedAssetUploadSmokeError("Expected array field was missing.", {"field": key})
    return value


def require_dict_value(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManagedAssetUploadSmokeError("Expected object item was missing.", {"field": field_name})
    return value


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def sanitized_origin(url: str) -> str:
    parsed = urlsplit(url)
    return stable_hash(f"{parsed.scheme}://{parsed.netloc}")


if __name__ == "__main__":
    raise SystemExit(main())

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
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


class ResumableUploadSmokeError(Exception):
    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


def main() -> int:
    args = parse_args()
    try:
        result = run(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except ResumableUploadSmokeError as error:
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
            "Exercise HoopClips resumable upload interruption and resume behavior. "
            "Stdout is sanitized and does not print presigned URLs, object keys, or secrets. "
            "The local state file contains job/upload identifiers and a local source path needed for resume."
        )
    )
    parser.add_argument("--worker-url", default=os.getenv("WORKER_BASE_URL"))
    parser.add_argument("--file", dest="file_path", type=Path)
    parser.add_argument("--state-path", type=Path, default=Path("artifacts/resumable_upload_interrupt_state.json"))
    parser.add_argument(
        "--generate-test-file-mb",
        type=int,
        default=0,
        help=(
            "Create a local sparse synthetic file of this size when --file is omitted or missing. "
            "Use only for transport/resume proof, not analysis quality proof."
        ),
    )
    parser.add_argument(
        "--auto-generate-test-file",
        action="store_true",
        help=(
            "When --file is omitted, query Worker capabilities and create a sparse synthetic file "
            "large enough to request resumable upload."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["interrupt-after-first", "resume", "roundtrip"],
        required=True,
        help=(
            "interrupt-after-first uploads part 1 and writes state, resume continues from that state, "
            "roundtrip uploads part 1, reloads state, then completes in the same process."
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("HOOPS_UPLOAD_SMOKE_TIMEOUT_SECONDS", "60")))
    parser.add_argument("--install-id", default=os.getenv("HOOPS_UPLOAD_SMOKE_INSTALL_ID", "resumable-upload-smoke-install"))
    parser.add_argument("--app-version", default=os.getenv("HOOPS_UPLOAD_SMOKE_APP_VERSION", "resumable-upload-smoke"))
    parser.add_argument("--analysis-version", default=os.getenv("HOOPS_UPLOAD_SMOKE_ANALYSIS_VERSION", "resumable-upload-smoke"))
    parser.add_argument("--duration-seconds", type=float, default=float(os.getenv("HOOPS_UPLOAD_SMOKE_DURATION_SECONDS", "60")))
    parser.add_argument("--content-type", default=None)
    parser.add_argument(
        "--stop-after-new-parts",
        type=int,
        default=0,
        help=(
            "In resume mode, intentionally stop after this many newly uploaded parts. "
            "Use this to prove repeated interruptions keep durable completedParts state."
        ),
    )
    args = parser.parse_args()

    if not args.worker_url:
        raise ResumableUploadSmokeError("WORKER_BASE_URL or --worker-url is required.")
    if args.timeout_seconds <= 0:
        raise ResumableUploadSmokeError("Timeout must be positive.", {"timeoutSeconds": args.timeout_seconds})
    if args.generate_test_file_mb < 0:
        raise ResumableUploadSmokeError("--generate-test-file-mb must be zero or positive.")
    if (
        args.mode in {"interrupt-after-first", "roundtrip"}
        and not args.file_path
        and args.generate_test_file_mb <= 0
        and not args.auto_generate_test_file
    ):
        raise ResumableUploadSmokeError("--file, --generate-test-file-mb, or --auto-generate-test-file is required for this mode.")
    if args.mode in {"interrupt-after-first", "roundtrip"} and not args.file_path:
        args.file_path = args.state_path.parent / "resumable_upload_synthetic.mp4"
    if args.file_path and not args.file_path.is_file() and args.generate_test_file_mb <= 0:
        raise ResumableUploadSmokeError("Upload source file does not exist.", {"file": str(args.file_path)})
    if args.stop_after_new_parts < 0:
        raise ResumableUploadSmokeError("--stop-after-new-parts must be zero or positive.")
    return args


def run(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.worker_url.rstrip("/") + "/"
    if args.mode == "resume":
        state = load_state(args.state_path)
        result = resume_from_state(base_url, args, state)
    elif args.mode == "interrupt-after-first":
        result = interrupt_after_first_part(base_url, args)
    else:
        first = interrupt_after_first_part(base_url, args)
        state = load_state(args.state_path)
        resumed = resume_from_state(base_url, args, state)
        result = {
            "status": "pass" if first.get("status") == "interrupted" and resumed.get("status") == "pass" else resumed.get("status", "fail"),
            "mode": "roundtrip",
            "worker": sanitized_worker(base_url),
            "firstPhase": first,
            "resumePhase": resumed,
            "privacy": "no_secrets_no_presigned_urls_no_object_keys",
        }
    return result


def interrupt_after_first_part(base_url: str, args: argparse.Namespace) -> dict[str, Any]:
    source_path = args.file_path
    assert source_path is not None
    ensure_source_file_for_interrupt(base_url, args, source_path)
    source_size = source_path.stat().st_size
    content_type = args.content_type or mimetypes.guess_type(source_path.name)[0] or "video/mp4"
    job = create_analysis_job(base_url, args, source_path.name, content_type, source_size)
    resumable = job.get("resumableUpload")
    if not isinstance(resumable, dict):
        raise ResumableUploadSmokeError("Worker did not return a resumable upload plan.", {
            "jobIdHash": stable_hash(str(job.get("jobId"))),
            "returnedResumableUpload": False,
        })

    chunk_size = require_int(resumable, "chunkSizeBytes")
    part_count = require_int(resumable, "partCount")
    if part_count < 2:
        raise ResumableUploadSmokeError("Smoke requires at least two parts to prove resume.", {
            "partCount": part_count,
            "chunkSizeBytes": chunk_size,
        })

    job_id = require_str(job, "jobId")
    upload_id = require_str(resumable, "uploadId")
    first_part = upload_part(base_url, args, source_path, job_id, upload_id, chunk_size, 1)
    state = {
        "schemaVersion": 1,
        "createdAt": int(time.time()),
        "worker": sanitized_worker(base_url),
        "sourcePath": str(source_path.resolve()),
        "sourcePathHash": stable_hash(str(source_path.resolve())),
        "sourceSizeBytes": source_size,
        "filename": source_path.name,
        "contentType": content_type,
        "jobId": job_id,
        "installId": args.install_id,
        "uploadId": upload_id,
        "chunkSizeBytes": chunk_size,
        "partCount": part_count,
        "completedParts": [first_part],
        "status": "interrupted_after_first_part",
        "updatedAt": int(time.time()),
        "privacy": "state_file_contains_job_upload_identifiers_and_local_source_path_but_no_presigned_urls_or_object_keys",
    }
    args.state_path.parent.mkdir(parents=True, exist_ok=True)
    args.state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "status": "interrupted",
        "mode": "interrupt-after-first",
        "worker": sanitized_worker(base_url),
        "statePath": str(args.state_path),
        "jobIdHash": stable_hash(job_id),
        "uploadIdHash": stable_hash(upload_id),
        "chunkSizeBytes": chunk_size,
        "partCount": part_count,
        "completedParts": 1,
        "nextAction": "rerun_with_mode_resume",
        "privacy": "no_secrets_no_presigned_urls_no_object_keys",
    }


def ensure_source_file_for_interrupt(base_url: str, args: argparse.Namespace, source_path: Path) -> None:
    if source_path.is_file():
        return
    if args.generate_test_file_mb <= 0 and not args.auto_generate_test_file:
        raise ResumableUploadSmokeError("Upload source file does not exist.", {"sourcePathHash": stable_hash(str(source_path))})

    source_path.parent.mkdir(parents=True, exist_ok=True)
    size_bytes = synthetic_test_file_size_bytes(base_url, args)
    if size_bytes <= 0:
        raise ResumableUploadSmokeError("Synthetic file size must be positive.")
    with source_path.open("wb") as handle:
        handle.truncate(size_bytes)


def synthetic_test_file_size_bytes(base_url: str, args: argparse.Namespace) -> int:
    if args.generate_test_file_mb > 0:
        return args.generate_test_file_mb * 1024 * 1024

    status, capabilities = request_json_get(urljoin(base_url, "v1/analysis/capabilities"), args.timeout_seconds)
    if status < 200 or status >= 300:
        raise ResumableUploadSmokeError("Could not fetch capabilities for synthetic payload sizing.", {"httpStatus": status})

    threshold = capabilities.get("resumableUploadThresholdBytes")
    max_size = capabilities.get("maxFileSizeBytes")
    if not isinstance(threshold, int) or threshold <= 0:
        raise ResumableUploadSmokeError("Capabilities response did not include a valid resumable threshold.")
    if not isinstance(max_size, int) or max_size <= threshold:
        raise ResumableUploadSmokeError("Capabilities response did not include a valid max file size.")

    target_bytes = max(threshold + (8 * 1024 * 1024), 160 * 1024 * 1024)
    return min(target_bytes, max_size)


def resume_from_state(base_url: str, args: argparse.Namespace, state: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(require_str(state, "sourcePath"))
    if not source_path.is_file():
        raise ResumableUploadSmokeError("State source file is missing.", {"sourcePathHash": stable_hash(str(source_path))})
    job_id = require_str(state, "jobId")
    upload_id = require_str(state, "uploadId")
    install_id = require_str(state, "installId")
    chunk_size = require_int(state, "chunkSizeBytes")
    part_count = require_int(state, "partCount")
    completed_parts = normalize_completed_parts(state.get("completedParts"))
    completed_numbers = {part["partNumber"] for part in completed_parts}
    newly_completed_count = 0

    for part_number in range(1, part_count + 1):
        if part_number in completed_numbers:
            continue
        completed_part = upload_part(base_url, args, source_path, job_id, upload_id, chunk_size, part_number, install_id=install_id)
        completed_parts.append(completed_part)
        completed_numbers.add(part_number)
        newly_completed_count += 1
        persist_resume_state(
            args.state_path,
            state,
            completed_parts,
            status="resuming",
        )
        if args.stop_after_new_parts > 0 and newly_completed_count >= args.stop_after_new_parts:
            return {
                "status": "interrupted",
                "mode": "resume",
                "worker": sanitized_worker(base_url),
                "jobIdHash": stable_hash(job_id),
                "uploadIdHash": stable_hash(upload_id),
                "chunkSizeBytes": chunk_size,
                "partCount": part_count,
                "completedParts": len(completed_parts),
                "newlyCompletedParts": newly_completed_count,
                "stateUpdated": True,
                "nextAction": "rerun_with_mode_resume",
                "privacy": "no_secrets_no_presigned_urls_no_object_keys",
            }

    complete_multipart_upload(base_url, args, job_id, install_id, upload_id, completed_parts)
    persist_resume_state(
        args.state_path,
        state,
        completed_parts,
        status="completed",
    )
    return {
        "status": "pass",
        "mode": "resume",
        "worker": sanitized_worker(base_url),
        "jobIdHash": stable_hash(job_id),
        "uploadIdHash": stable_hash(upload_id),
        "chunkSizeBytes": chunk_size,
        "partCount": part_count,
        "completedParts": len(completed_parts),
        "newlyCompletedParts": newly_completed_count,
        "stateUpdated": True,
        "interruptionProven": True,
        "privacy": "no_secrets_no_presigned_urls_no_object_keys",
    }


def persist_resume_state(
    state_path: Path,
    state: dict[str, Any],
    completed_parts: list[dict[str, Any]],
    status: str,
) -> None:
    updated_state = {
        **state,
        "completedParts": sorted(completed_parts, key=lambda part: int(part["partNumber"])),
        "status": status,
        "updatedAt": int(time.time()),
        "privacy": "state_file_contains_job_upload_identifiers_and_local_source_path_but_no_presigned_urls_or_object_keys",
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(updated_state, indent=2, sort_keys=True), encoding="utf-8")


def create_analysis_job(
    base_url: str,
    args: argparse.Namespace,
    filename: str,
    content_type: str,
    file_size_bytes: int,
) -> dict[str, Any]:
    payload = {
        "filename": filename,
        "contentType": content_type,
        "fileSizeBytes": file_size_bytes,
        "durationSeconds": args.duration_seconds,
        "installId": args.install_id,
        "appVersion": args.app_version,
        "analysisVersion": args.analysis_version,
        "uploadPreference": "resumable",
    }
    status, decoded = request_json_response("POST", urljoin(base_url, "v1/analysis/jobs"), args.timeout_seconds, payload)
    if status < 200 or status >= 300:
        raise ResumableUploadSmokeError("Could not create resumable upload job.", {
            "httpStatus": status,
            "errorCode": decoded.get("errorCode"),
            "failureReason": decoded.get("failureReason"),
        })
    return decoded


def upload_part(
    base_url: str,
    args: argparse.Namespace,
    source_path: Path,
    job_id: str,
    upload_id: str,
    chunk_size: int,
    part_number: int,
    install_id: str | None = None,
) -> dict[str, Any]:
    part_payload = {
        "jobId": job_id,
        "installId": install_id or args.install_id,
        "uploadId": upload_id,
        "partNumber": part_number,
    }
    status, part = request_json_response(
        "POST",
        urljoin(base_url, "v1/analysis/uploads/multipart/part"),
        args.timeout_seconds,
        part_payload,
    )
    if status < 200 or status >= 300:
        raise ResumableUploadSmokeError("Could not create multipart part target.", {
            "httpStatus": status,
            "partNumber": part_number,
            "errorCode": part.get("errorCode"),
        })

    upload_url = require_str(part, "uploadUrl")
    upload_method = part.get("uploadMethod", "PUT")
    upload_headers = part.get("uploadHeaders") if isinstance(part.get("uploadHeaders"), dict) else {}
    chunk = read_chunk(source_path, chunk_size, part_number)
    etag = put_presigned_part(upload_url, upload_method, upload_headers, chunk, args.timeout_seconds)
    return {"partNumber": part_number, "etag": etag}


def complete_multipart_upload(
    base_url: str,
    args: argparse.Namespace,
    job_id: str,
    install_id: str,
    upload_id: str,
    completed_parts: list[dict[str, Any]],
) -> None:
    payload = {
        "jobId": job_id,
        "installId": install_id,
        "uploadId": upload_id,
        "parts": sorted(completed_parts, key=lambda part: int(part["partNumber"])),
    }
    status, decoded = request_json_response(
        "POST",
        urljoin(base_url, "v1/analysis/uploads/multipart/complete"),
        args.timeout_seconds,
        payload,
    )
    if status < 200 or status >= 300:
        raise ResumableUploadSmokeError("Could not complete multipart upload.", {
            "httpStatus": status,
            "errorCode": decoded.get("errorCode"),
            "failureReason": decoded.get("failureReason"),
        })


def request_json_get(url: str, timeout_seconds: float) -> tuple[int, dict[str, Any]]:
    request = Request(url, method="GET", headers={"accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            data = response.read()
            status = getattr(response, "status", 200)
    except HTTPError as error:
        data = error.read()
        status = error.code
    except URLError as error:
        raise ResumableUploadSmokeError("Endpoint was unreachable.", {"reason": str(error.reason)}) from error
    try:
        decoded = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ResumableUploadSmokeError("Endpoint returned invalid JSON.", {"httpStatus": status}) from error
    if not isinstance(decoded, dict):
        raise ResumableUploadSmokeError("Endpoint returned non-object JSON.", {"httpStatus": status})
    return status, decoded


def request_json_response(
    method: str,
    url: str,
    timeout_seconds: float,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, method=method, data=body, headers={"accept": "application/json", "content-type": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            data = response.read()
            status = getattr(response, "status", 200)
    except HTTPError as error:
        data = error.read()
        status = error.code
    except URLError as error:
        raise ResumableUploadSmokeError("Endpoint was unreachable.", {"reason": str(error.reason)}) from error
    try:
        decoded = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ResumableUploadSmokeError("Endpoint returned invalid JSON.", {"httpStatus": status}) from error
    if not isinstance(decoded, dict):
        raise ResumableUploadSmokeError("Endpoint returned non-object JSON.", {"httpStatus": status})
    return status, decoded


def put_presigned_part(
    upload_url: str,
    upload_method: str,
    upload_headers: dict[str, Any],
    body: bytes,
    timeout_seconds: float,
) -> str:
    headers = {str(key): str(value) for key, value in upload_headers.items()}
    request = Request(upload_url, method=upload_method, data=body, headers=headers)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            etag = response.headers.get("ETag")
            response.read()
    except HTTPError as error:
        raise ResumableUploadSmokeError("Presigned part upload failed.", {"httpStatus": error.code}) from error
    except URLError as error:
        raise ResumableUploadSmokeError("Presigned part upload was unreachable.", {"reason": str(error.reason)}) from error
    if status < 200 or status >= 300:
        raise ResumableUploadSmokeError("Presigned part upload returned non-success status.", {"httpStatus": status})
    if not etag:
        raise ResumableUploadSmokeError("Presigned part upload response was missing ETag.", {"httpStatus": status})
    return etag


def read_chunk(source_path: Path, chunk_size: int, part_number: int) -> bytes:
    offset = (part_number - 1) * chunk_size
    with source_path.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read(chunk_size)
    if not chunk:
        raise ResumableUploadSmokeError("Requested chunk was empty.", {"partNumber": part_number})
    return chunk


def load_state(path: Path) -> dict[str, Any]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ResumableUploadSmokeError("Resume state file does not exist.", {"statePath": str(path)}) from error
    except json.JSONDecodeError as error:
        raise ResumableUploadSmokeError("Resume state file is invalid JSON.", {"statePath": str(path)}) from error
    if not isinstance(decoded, dict):
        raise ResumableUploadSmokeError("Resume state file must contain an object.", {"statePath": str(path)})
    return decoded


def normalize_completed_parts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ResumableUploadSmokeError("Resume state completedParts must be a list.")
    parts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ResumableUploadSmokeError("Each completed part must be an object.")
        part_number = require_int(item, "partNumber")
        etag = require_str(item, "etag")
        parts.append({"partNumber": part_number, "etag": etag})
    return parts


def require_str(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ResumableUploadSmokeError(f"Missing string field: {field}")
    return value


def require_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or value <= 0:
        raise ResumableUploadSmokeError(f"Missing positive integer field: {field}")
    return value


def sanitized_worker(base_url: str) -> dict[str, Any]:
    split = urlsplit(base_url)
    return {
        "scheme": split.scheme or "unknown",
        "hostHash": stable_hash(split.netloc.lower()),
        "pathDepth": len([part for part in split.path.split("/") if part]),
    }


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


if __name__ == "__main__":
    raise SystemExit(main())

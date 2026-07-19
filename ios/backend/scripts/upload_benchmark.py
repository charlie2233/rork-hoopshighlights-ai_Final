#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError


USER_AGENT = "HoopClipsUploadBenchmark/1.0"


def _json_request(method: str, url: str, payload: Optional[dict] = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "accept": "application/json",
        "user-agent": USER_AGENT,
    }
    if payload is not None:
        headers["content-type"] = "application/json"
    req = urlrequest.Request(url, data=body, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=120) as response:
            raw = response.read()
    except HTTPError as error:
        raise RuntimeError(error.read().decode("utf-8", errors="replace")) from error
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _put_bytes(url: str, payload: bytes, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    request_headers = {"user-agent": USER_AGENT}
    request_headers.update(headers or {})
    req = urlrequest.Request(url, data=payload, method="PUT", headers=request_headers)
    try:
        with urlrequest.urlopen(req, timeout=180) as response:
            return dict(response.headers.items())
    except HTTPError as error:
        raise RuntimeError(error.read().decode("utf-8", errors="replace")) from error


def _load_payload(path: Optional[Path], generated_size_bytes: int) -> bytes:
    if path is not None:
        return path.read_bytes()
    return bytes((index % 251 for index in range(generated_size_bytes)))


def _poll_asset(base_url: str, asset_id: str, install_id: str, timeout_seconds: float) -> dict:
    deadline = time.perf_counter() + timeout_seconds
    latest: dict = {}
    while time.perf_counter() < deadline:
        latest = _json_request("GET", f"{base_url}/v1/assets/{asset_id}?installId={install_id}")
        if latest.get("status") in {"proxy_ready", "ready", "failed"}:
            return latest
        time.sleep(0.25)
    return latest


def run(args: argparse.Namespace) -> dict:
    base_url = args.base_url.rstrip("/")
    payload = _load_payload(args.file, args.generated_size_bytes)
    filename = args.file.name if args.file else "benchmark.mp4"
    install_id = args.install_id
    started = time.perf_counter()
    init = _json_request(
        "POST",
        f"{base_url}/v1/uploads/init",
        {
            "filename": filename,
            "contentType": args.content_type,
            "fileSizeBytes": len(payload),
            "durationSeconds": args.duration_seconds,
            "installId": install_id,
            "appVersion": "benchmark",
            "analysisVersion": "cloud-v1",
            "uploadPreference": args.upload_preference,
            "partSizeBytes": args.part_size_bytes,
        },
    )

    retry_resume_success = False
    upload_started = time.perf_counter()
    if init["uploadMode"] == "multipart":
        parts = []
        part_size = int(init["multipart"]["partSizeBytes"])
        for index, part in enumerate(init["multipart"]["parts"]):
            start = (int(part["partNumber"]) - 1) * part_size
            chunk = payload[start : start + part_size]
            headers = part.get("uploadHeaders") or {}
            first_headers = _put_bytes(part["uploadUrl"], chunk, headers)
            if index == 0 and args.retry_first_part:
                retry_headers = _put_bytes(part["uploadUrl"], chunk, headers)
                retry_resume_success = bool(retry_headers.get("ETag") or retry_headers.get("etag"))
            etag = first_headers.get("ETag") or first_headers.get("etag") or f"part-{part['partNumber']}"
            parts.append({"partNumber": part["partNumber"], "etag": etag, "sizeBytes": len(chunk)})
        upload_finished = time.perf_counter()
        complete = _json_request(
            "POST",
            f"{base_url}/v1/uploads/{init['assetId']}/complete",
            {"installId": install_id, "uploadId": init["multipart"]["uploadId"], "parts": parts},
        )
    else:
        _put_bytes(init["uploadUrl"], payload, init.get("uploadHeaders") or {})
        upload_finished = time.perf_counter()
        complete = _json_request(
            "POST",
            f"{base_url}/v1/uploads/{init['assetId']}/complete",
            {"installId": install_id},
        )
        retry_resume_success = True

    preview = complete if complete.get("status") in {"proxy_ready", "ready", "failed"} else _poll_asset(
        base_url,
        init["assetId"],
        install_id,
        args.preview_timeout_seconds,
    )
    preview_ready_at = time.perf_counter()

    return {
        "assetId": init["assetId"],
        "storageKey": init["storageKey"],
        "uploadMode": init["uploadMode"],
        "bytes": len(payload),
        "timeToFirstPreviewSeconds": round(preview_ready_at - started, 4),
        "fullUploadSeconds": round(upload_finished - upload_started, 4),
        "retryResumeSuccess": retry_resume_success,
        "finalAssetStatus": preview.get("status"),
        "proxyStorageKey": (preview.get("artifacts") or {}).get("proxyStorageKey"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark HoopClips asset upload pipeline.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--generated-size-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--content-type", default="video/mp4")
    parser.add_argument("--duration-seconds", type=float, default=12.0)
    parser.add_argument("--install-id", default="benchmark-install")
    parser.add_argument("--upload-preference", choices=["single", "multipart", "auto"], default="auto")
    parser.add_argument("--part-size-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--preview-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--retry-first-part", action="store_true")
    args = parser.parse_args()

    if args.file is None:
        with tempfile.TemporaryDirectory(prefix="hoops-upload-benchmark-"):
            print(json.dumps(run(args), indent=2, sort_keys=True))
    else:
        print(json.dumps(run(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

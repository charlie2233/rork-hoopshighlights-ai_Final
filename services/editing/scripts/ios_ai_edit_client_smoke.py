#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from live_render_smoke import SmokeError, create_source, download_file, probe_media


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir or tempfile.mkdtemp(prefix="hoopclips-ios-ai-edit-smoke-")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "source.mp4"
    final_path = output_dir / "final.mp4"

    create_source(source_path)
    source_key = upload_source_to_worker(args, source_path)
    clips = [
        clip("c1", 0.0, "Fast Break", 0.95),
        clip("c2", 8.0, "Made Shot", 0.90),
    ]
    edit_job = request_json(
        "POST",
        args.worker_url,
        "v1/edit-jobs",
        {
            "videoId": "ios_ai_edit_smoke_video",
            "analysisJobId": "ios_ai_edit_smoke_analysis",
            "installId": args.install_id,
            "sourceObjectKey": source_key,
            "preset": "personal_highlight",
            "targetDurationSeconds": 15,
            "aspectRatio": "9:16",
            "planTier": "free",
            "clips": clips,
        },
        trace_id=args.trace_id,
    )
    edit_job_id = str(edit_job["editJobId"])
    plan_response = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/plan?{urlencode({'installId': args.install_id})}",
        trace_id=args.trace_id,
    )
    render_status = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/render",
        {
            "installId": args.install_id,
            "sourceObjectKey": source_key,
            "planTier": "free",
            "editPlan": plan_response["plan"],
            "sourceClips": clips,
        },
        trace_id=args.trace_id,
    )

    deadline = time.time() + args.timeout_seconds
    while time.time() < deadline and render_status.get("status") not in {"rendered", "failed", "cancelled"}:
        time.sleep(args.poll_seconds)
        render_status = request_json(
            "GET",
            args.worker_url,
            f"v1/edit-jobs/{edit_job_id}/render-status?{urlencode({'installId': args.install_id})}",
            trace_id=args.trace_id,
        )

    if render_status.get("status") != "rendered":
        raise SmokeError("Worker render did not reach rendered", {"editJobId": edit_job_id, "renderStatus": render_status})

    download = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/download-url?{urlencode({'installId': args.install_id})}",
        trace_id=args.trace_id,
    )
    download_file(str(download["downloadUrl"]), final_path)
    media = probe_media(
        final_path,
        expected_aspect_ratio=str(plan_response["plan"].get("aspectRatio", "9:16")),
        expected_duration_seconds=_float_or_none(render_status.get("durationSeconds")),
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "workerUrl": args.worker_url,
                "editJobId": edit_job_id,
                "renderJobId": render_status.get("renderJobId"),
                "sourceObjectKey": source_key,
                "outputObjectKey": download.get("outputObjectKey"),
                "renderLogObjectKey": render_status.get("renderLogObjectKey"),
                "downloadedPath": str(final_path),
                "media": media,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke the iOS-facing Worker AI edit flow end to end.")
    parser.add_argument("--worker-url", default=os.getenv("WORKER_BASE_URL", "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"))
    parser.add_argument("--install-id", default=os.getenv("HOOPS_SMOKE_INSTALL_ID", "smoke-install-ios-ai-edit"))
    parser.add_argument("--app-version", default=os.getenv("HOOPS_SMOKE_APP_VERSION", "phase-edit3b-smoke"))
    parser.add_argument("--analysis-version", default=os.getenv("HOOPS_SMOKE_ANALYSIS_VERSION", "phase-edit3b-smoke"))
    parser.add_argument("--output-dir", default=os.getenv("HOOPS_SMOKE_OUTPUT_DIR"))
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("HOOPS_SMOKE_TIMEOUT_SECONDS", "300")))
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("HOOPS_SMOKE_POLL_SECONDS", "2")))
    parser.add_argument("--trace-id", default=os.getenv("HOOPS_SMOKE_TRACE_ID", "phase-edit3b-ios-ai-edit-smoke"))
    return parser.parse_args()


def upload_source_to_worker(args: argparse.Namespace, source_path: Path) -> str:
    response = request_json(
        "POST",
        args.worker_url,
        "v1/analysis/jobs",
        {
            "filename": source_path.name,
            "contentType": "video/mp4",
            "fileSizeBytes": source_path.stat().st_size,
            "durationSeconds": 18,
            "installId": args.install_id,
            "appVersion": args.app_version,
            "analysisVersion": args.analysis_version,
        },
        trace_id=args.trace_id,
    )
    upload_headers = {str(key): str(value) for key, value in response.get("uploadHeaders", {}).items()}
    if "Content-Type" not in upload_headers and "content-type" not in {key.lower() for key in upload_headers}:
        upload_headers["Content-Type"] = "video/mp4"
    upload_method = str(response.get("uploadMethod", "PUT"))
    with urlopen(Request(str(response["uploadUrl"]), data=source_path.read_bytes(), headers=upload_headers, method=upload_method), timeout=120) as upload_response:
        if upload_response.status >= 400:
            raise SmokeError("signed source upload failed", {"status": upload_response.status})
    return str(response["sourceObjectKey"])


def clip(clip_id: str, start: float, label: str, score: float) -> Dict[str, Any]:
    return {
        "id": clip_id,
        "start": start,
        "end": start + 5.0,
        "eventCenter": start + 2.4,
        "label": label,
        "confidence": score,
        "excitement": score,
        "watchability": score,
        "motionScore": score,
        "audioPeak": score / 2.0,
        "combinedScore": score,
    }


def request_json(
    method: str,
    base_url: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    trace_id: str = "",
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "HoopClipsIOSAIEditSmoke/1.0", "x-trace-id": trace_id}
    try:
        with urlopen(Request(urljoin(base_url.rstrip("/") + "/", path), data=data, headers=headers, method=method), timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            parsed_body: object = json.loads(body)
        except json.JSONDecodeError:
            parsed_body = body[:1000]
        raise SmokeError(
            f"{method} {path} failed with HTTP {error.code}",
            {"status": error.code, "body": parsed_body},
        ) from error
    except URLError as error:
        raise SmokeError(f"{method} {path} failed", {"reason": str(error)}) from error


def _float_or_none(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as error:
        print(json.dumps({"status": "fail", "error": str(error), "details": error.payload}, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)

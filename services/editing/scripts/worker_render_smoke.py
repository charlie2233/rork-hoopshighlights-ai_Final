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
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from live_render_smoke import SmokeError, clip, download_file, probe_media


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "ios" / "backend"))
    from app.editing import CreateEditJobRequest, build_edit_job

    args = parse_args()
    source_key = args.source_object_key
    if not source_key:
        raise SmokeError("HOOPS_SMOKE_SOURCE_OBJECT_KEY is required for Worker smoke", {})

    output_dir = Path(args.output_dir or tempfile.mkdtemp(prefix="hoopclips-worker-render-smoke-")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / "final.mp4"

    edit_request = CreateEditJobRequest(
        videoId="worker_smoke_video",
        analysisJobId="worker_smoke_analysis",
        installId=args.install_id,
        sourceObjectKey=source_key,
        preset="personal_highlight",
        targetDurationSeconds=15,
        aspectRatio="9:16",
        planTier="free",
        clips=[
            clip("c1", 0.0, "Fast Break", 0.95),
            clip("c2", 8.0, "Made Shot", 0.90),
        ],
    )
    edit_job = build_edit_job(edit_request, args.edit_job_id or "edit_worker_smoke_" + str(int(time.time())))
    if edit_job.validation_errors:
        raise SmokeError("edit plan generation failed", {"validationErrors": [error.model_dump() for error in edit_job.validation_errors]})

    base_url = args.worker_url.rstrip("/") + "/"
    payload = {
        "installId": args.install_id,
        "sourceObjectKey": source_key,
        "planTier": "free",
        "editPlan": edit_job.plan.model_dump(),
        "sourceClips": [clip.model_dump() for clip in edit_request.clips],
    }
    status = request_json(
        "POST",
        base_url,
        f"v1/edit-jobs/{edit_job.edit_job_id}/render",
        payload,
        trace_id=edit_job.edit_job_id,
    )
    deadline = time.time() + args.timeout_seconds
    while time.time() < deadline and status.get("status") not in {"rendered", "failed", "cancelled"}:
        time.sleep(args.poll_seconds)
        status = request_json(
            "GET",
            base_url,
            f"v1/edit-jobs/{edit_job.edit_job_id}/render-status?{urlencode({'installId': args.install_id})}",
            trace_id=edit_job.edit_job_id,
        )
    if status.get("status") != "rendered":
        raise SmokeError("Worker render did not reach rendered", {"editJobId": edit_job.edit_job_id, "renderStatus": status})

    download = request_json(
        "GET",
        base_url,
        f"v1/edit-jobs/{edit_job.edit_job_id}/download-url?{urlencode({'installId': args.install_id})}",
        trace_id=edit_job.edit_job_id,
    )
    download_file(str(download["downloadUrl"]), final_path)
    media = probe_media(final_path, expected_aspect_ratio=edit_job.plan.aspectRatio, expected_duration_seconds=_float_or_none(status.get("durationSeconds")))
    print(
        json.dumps(
            {
                "status": "pass",
                "workerUrl": args.worker_url,
                "editJobId": edit_job.edit_job_id,
                "renderJobId": status.get("renderJobId"),
                "sourceObjectKey": source_key,
                "outputObjectKey": download.get("outputObjectKey"),
                "downloadedPath": str(final_path),
                "media": media,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke the active Worker -> editing service render path.")
    parser.add_argument("--worker-url", default=os.getenv("WORKER_BASE_URL"))
    parser.add_argument("--install-id", default=os.getenv("HOOPS_SMOKE_INSTALL_ID", "smoke-install-001"))
    parser.add_argument("--source-object-key", default=os.getenv("HOOPS_SMOKE_SOURCE_OBJECT_KEY"))
    parser.add_argument("--edit-job-id", default=os.getenv("HOOPS_SMOKE_EDIT_JOB_ID"))
    parser.add_argument("--output-dir", default=os.getenv("HOOPS_SMOKE_OUTPUT_DIR"))
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("HOOPS_SMOKE_TIMEOUT_SECONDS", "300")))
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("HOOPS_SMOKE_POLL_SECONDS", "2")))
    args = parser.parse_args()
    if not args.worker_url:
        raise SmokeError("WORKER_BASE_URL is required for Worker smoke", {})
    return args


def request_json(method: str, base_url: str, path: str, payload: Optional[Dict[str, Any]] = None, trace_id: str = "") -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "x-trace-id": trace_id}
    with urlopen(Request(urljoin(base_url, path), data=data, headers=headers, method=method), timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


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

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
    initial_path = output_dir / "initial.mp4"
    revised_path = output_dir / "revised-more-hype.mp4"

    create_source(source_path)
    version = request_json("GET", args.worker_url, "v1/editing/version", trace_id=args.trace_id)
    flags = version.get("featureFlags") if isinstance(version.get("featureFlags"), dict) else {}
    if flags.get("aiEditEnabled") is False:
        raise SmokeError("AI Edit planning is disabled by the staging backend", {"featureFlags": safe_feature_flags(flags)})
    if flags.get("aiEditLiveRenderEnabled") is False:
        raise SmokeError("AI Edit live rendering is disabled by the staging backend", {"featureFlags": safe_feature_flags(flags)})

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
    render_status = wait_for_render(args, edit_job_id, render_status)

    if render_status.get("status") != "rendered":
        raise SmokeError("Worker render did not reach rendered", {"editJobId": edit_job_id, "renderStatus": sanitize_for_log(render_status)})

    download = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/download-url?{urlencode({'installId': args.install_id})}",
        trace_id=args.trace_id,
    )
    download_file(str(download["downloadUrl"]), initial_path)
    initial_media = probe_media(
        initial_path,
        expected_aspect_ratio=str(plan_response["plan"].get("aspectRatio", "9:16")),
        expected_duration_seconds=_float_or_none(render_status.get("durationSeconds")),
    )

    revision = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/revise",
        {
            "installId": args.install_id,
            "command": "make_more_hype",
        },
        trace_id=args.trace_id,
    )
    revision_id = str(revision["revisionId"])
    revision_render_status = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/revisions/{revision_id}/render",
        {
            "installId": args.install_id,
            "idempotencyKey": f"ios-smoke-revision-{revision_id}",
        },
        trace_id=args.trace_id,
    )
    expected_revision_render_id = _string_or_none(revision_render_status.get("renderJobId"))
    revision_render_status = wait_for_render(
        args,
        edit_job_id,
        revision_render_status,
        expected_render_job_id=expected_revision_render_id,
        expected_revision_id=revision_id,
    )
    if revision_render_status.get("status") != "rendered" or not render_status_matches(
        revision_render_status,
        expected_revision_render_id,
        revision_id,
    ):
        raise SmokeError(
            "Worker revision render did not reach rendered",
            {
                "editJobId": edit_job_id,
                "revisionId": revision_id,
                "renderStatus": sanitize_for_log(revision_render_status),
            },
        )

    revised_download = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/download-url?{urlencode({'installId': args.install_id})}",
        trace_id=args.trace_id,
    )
    expected_revision_render_id = _string_or_none(revision_render_status.get("renderJobId"))
    if expected_revision_render_id and revised_download.get("renderJobId") != expected_revision_render_id:
        raise SmokeError(
            "Worker latest download did not point at the revised render",
            {
                "editJobId": edit_job_id,
                "revisionId": revision_id,
                "expectedRenderJobId": expected_revision_render_id,
                "downloadRenderJobId": revised_download.get("renderJobId"),
            },
        )
    revised_plan = revision.get("revisedPlan") if isinstance(revision.get("revisedPlan"), dict) else {}
    download_file(str(revised_download["downloadUrl"]), revised_path)
    revised_media = probe_media(
        revised_path,
        expected_aspect_ratio=str(revised_plan.get("aspectRatio") or plan_response["plan"].get("aspectRatio", "9:16")),
        expected_duration_seconds=_float_or_none(revision_render_status.get("durationSeconds")),
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "workerUrl": args.worker_url,
                "editJobId": edit_job_id,
                "featureFlags": safe_feature_flags(flags),
                "initialRender": summarize_render(render_status, download, initial_path, initial_media),
                "moreHypeRevision": {
                    "revisionId": revision_id,
                    "command": revision.get("command"),
                    "status": revision.get("status"),
                    "requiresRerender": revision.get("requiresRerender"),
                    "render": summarize_render(revision_render_status, revised_download, revised_path, revised_media),
                    "revisedPlan": summarize_plan(revised_plan),
                },
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


def wait_for_render(
    args: argparse.Namespace,
    edit_job_id: str,
    render_status: Dict[str, Any],
    expected_render_job_id: Optional[str] = None,
    expected_revision_id: Optional[str] = None,
) -> Dict[str, Any]:
    deadline = time.time() + args.timeout_seconds
    while time.time() < deadline:
        if render_status_matches(render_status, expected_render_job_id, expected_revision_id) and render_status.get("status") in {
            "rendered",
            "failed",
            "failed_timeout",
            "cancelled",
        }:
            return render_status
        time.sleep(args.poll_seconds)
        render_status = request_json(
            "GET",
            args.worker_url,
            f"v1/edit-jobs/{edit_job_id}/render-status?{urlencode({'installId': args.install_id})}",
            trace_id=args.trace_id,
        )
    return render_status


def render_status_matches(render_status: Dict[str, Any], expected_render_job_id: Optional[str], expected_revision_id: Optional[str]) -> bool:
    if expected_render_job_id and render_status.get("renderJobId") != expected_render_job_id:
        return False
    if expected_revision_id and render_status.get("revisionId") != expected_revision_id:
        return False
    return True


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
            {"status": error.code, "body": sanitize_for_log(parsed_body)},
        ) from error
    except URLError as error:
        raise SmokeError(f"{method} {path} failed", {"reason": str(error)}) from error


def _float_or_none(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: object) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def summarize_render(render_status: Dict[str, Any], download: Dict[str, Any], path: Path, media: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "renderJobId": render_status.get("renderJobId"),
        "revisionId": render_status.get("revisionId"),
        "status": render_status.get("status"),
        "durationSeconds": render_status.get("durationSeconds"),
        "downloadRenderJobId": download.get("renderJobId"),
        "downloadedPath": str(path),
        "media": media,
    }


def summarize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    timeline = plan.get("timeline") if isinstance(plan.get("timeline"), list) else []
    return {
        "planId": plan.get("planId"),
        "templateId": plan.get("templateId"),
        "aspectRatio": plan.get("aspectRatio"),
        "targetDurationSeconds": plan.get("targetDurationSeconds"),
        "selectedClipCount": len(timeline),
    }


def sanitize_for_log(value: object) -> object:
    if isinstance(value, dict):
        sanitized: Dict[str, object] = {}
        for key, nested in value.items():
            key_text = str(key)
            lower_key = key_text.lower()
            if "url" in lower_key or "objectkey" in lower_key or "secret" in lower_key or "credential" in lower_key:
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = sanitize_for_log(nested)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_log(item) for item in value]
    if isinstance(value, str) and value.startswith("http") and ("X-Amz-" in value or "Signature=" in value):
        return "[redacted]"
    return value


def safe_feature_flags(flags: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "aiEditEnabled",
        "aiEditLiveRenderEnabled",
        "aiEditRevisionEnabled",
        "aiEditTemplatePackEnabled",
        "aiEditMaxDailyRenders",
        "aiEditFreeWatermarkRequired",
        "aiEditProExportsEnabled",
        "gptHighlightRerankerEnabled",
    }
    return {key: flags[key] for key in sorted(allowed) if key in flags}


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as error:
        print(json.dumps({"status": "fail", "error": str(error), "details": sanitize_for_log(error.payload)}, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)

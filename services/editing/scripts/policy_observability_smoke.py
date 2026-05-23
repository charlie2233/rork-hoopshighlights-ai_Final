#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode

from live_render_smoke import SmokeError, create_source, download_file, probe_media, sanitize_for_log
from template_pack_smoke import (
    TEMPLATE_CASES,
    assert_equal,
    compact_media_summary,
    request_json,
    smoke_clips,
    upload_source_to_worker,
    wait_for_render,
)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir or tempfile.mkdtemp(prefix="hoopclips-policy-smoke-")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = output_dir / "source.mp4"
    create_source(source_path)
    source_key = upload_source_to_worker(args, source_path)

    result = run_policy_smoke(args, output_dir, source_key)
    result["policyRejection"] = run_policy_rejection_smoke(args, source_key)

    summary = {
        "status": "pass",
        "workerUrl": args.worker_url,
        "editingUrl": args.editing_url,
        "sourceObjectKey": source_key,
        "outputDir": str(output_dir),
        **result,
    }
    summary_path = output_dir / "policy_observability_smoke_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({**summary, "summaryPath": str(summary_path)}, indent=2, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke HoopClips AI Edit Phase6 policy and observability guardrails.")
    parser.add_argument("--worker-url", default=os.getenv("WORKER_BASE_URL", "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"))
    parser.add_argument("--editing-url", default=os.getenv("HOOPS_EDITING_BASE_URL", "https://hoopclips-editing-staging-npya43jiia-uc.a.run.app"))
    parser.add_argument("--install-id", default=os.getenv("HOOPS_SMOKE_INSTALL_ID", f"smoke-policy-{int(time.time())}"))
    parser.add_argument("--app-version", default=os.getenv("HOOPS_SMOKE_APP_VERSION", "phase-edit6b-policy-smoke"))
    parser.add_argument("--analysis-version", default=os.getenv("HOOPS_SMOKE_ANALYSIS_VERSION", "phase-edit6b-policy-smoke"))
    parser.add_argument("--output-dir", default=os.getenv("HOOPS_SMOKE_OUTPUT_DIR"))
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("HOOPS_SMOKE_TIMEOUT_SECONDS", "420")))
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("HOOPS_SMOKE_POLL_SECONDS", "2")))
    parser.add_argument("--trace-id-prefix", default=os.getenv("HOOPS_SMOKE_TRACE_ID", "phase-edit6b-policy-smoke"))
    parser.add_argument("--r2-output-bucket", default=os.getenv("HOOPS_R2_OUTPUT_BUCKET") or os.getenv("HOOPS_R2_BUCKET") or "hoopsclips-results-staging")
    parser.add_argument("--wrangler-cwd", default=os.getenv("HOOPS_WRANGLER_CWD", "services/control-plane"))
    parser.add_argument("--r2-endpoint-url", default=os.getenv("HOOPS_R2_ENDPOINT_URL"))
    parser.add_argument("--r2-access-key-id", default=os.getenv("HOOPS_R2_ACCESS_KEY_ID"))
    parser.add_argument("--r2-secret-access-key", default=os.getenv("HOOPS_R2_SECRET_ACCESS_KEY"))
    return parser.parse_args()


def run_policy_smoke(args: argparse.Namespace, output_dir: Path, source_key: str) -> Dict[str, Any]:
    trace_id = f"{args.trace_id_prefix}-personal-free"
    clips = smoke_clips()
    edit_job = request_json(
        "POST",
        args.worker_url,
        "v1/edit-jobs",
        {
            "videoId": "phase_edit6b_personal_highlight",
            "analysisJobId": "phase_edit6b_analysis_personal",
            "installId": args.install_id,
            "sourceObjectKey": source_key,
            "preset": "personal_highlight",
            "templateId": "personal_highlight_v1",
            "targetDurationSeconds": 30,
            "aspectRatio": "9:16",
            "planTier": "free",
            "clips": clips,
        },
        trace_id=trace_id,
    )
    edit_job_id = str(edit_job["editJobId"])
    plan_response = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/plan?{urlencode({'installId': args.install_id})}",
        trace_id=trace_id,
    )
    plan = plan_response["plan"]
    assert_equal(plan.get("templateId"), "personal_highlight_v1", "plan.templateId")
    assert_equal(plan.get("targetDurationSeconds"), 30, "plan.targetDurationSeconds")
    assert_equal(plan.get("aspectRatio"), "9:16", "plan.aspectRatio")

    render_payload = {
        "installId": args.install_id,
        "sourceObjectKey": source_key,
        "planTier": "free",
        "editPlan": plan,
        "sourceClips": clips,
        "idempotencyKey": f"{edit_job_id}-phase6b-render",
    }
    first_render = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/render",
        render_payload,
        trace_id=trace_id,
    )
    duplicate_render = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/render",
        render_payload,
        trace_id=f"{trace_id}-duplicate",
    )
    assert_equal(duplicate_render.get("renderJobId"), first_render.get("renderJobId"), "duplicate.renderJobId")

    render_status = wait_for_render(args, edit_job_id, first_render, trace_id)
    assert_policy_response(render_status, expected_revision_id=None)
    download = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/download-url?{urlencode({'installId': args.install_id})}",
        trace_id=trace_id,
    )
    normal_dir = output_dir / "personal_highlight_free"
    normal_dir.mkdir(parents=True, exist_ok=True)
    normal_final = normal_dir / "final.mp4"
    download_file(str(download["downloadUrl"]), normal_final)
    normal_media = probe_media(normal_final, expected_aspect_ratio="9:16", expected_duration_seconds=to_float(render_status.get("durationSeconds")))

    render_log = fetch_render_log(args, str(render_status["renderLogObjectKey"]))
    assert_render_log_metadata(render_log, expected_template_id="personal_highlight_v1", expected_revision_id=None)

    revision_result = run_revision_smoke(args, output_dir, edit_job_id, trace_id)

    return {
        "normalRender": {
            "editJobId": edit_job_id,
            "renderJobId": render_status.get("renderJobId"),
            "duplicateRenderJobId": duplicate_render.get("renderJobId"),
            "duplicateBehavior": "idempotent_existing_render_returned",
            "outputObjectKey": download.get("outputObjectKey") or render_status.get("outputObjectKey"),
            "renderLogObjectKey": render_status.get("renderLogObjectKey"),
            "policy": render_status.get("policy"),
            "retentionMetadata": render_status.get("retentionMetadata"),
            "media": compact_media_summary(normal_media),
            "renderLog": compact_policy_log(render_log),
        },
        "revisionRender": revision_result,
    }


def run_revision_smoke(args: argparse.Namespace, output_dir: Path, edit_job_id: str, trace_id_prefix: str) -> Dict[str, Any]:
    trace_id = f"{trace_id_prefix}-revision-more-hype"
    revision = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/revise",
        {"installId": args.install_id, "command": "make_more_hype"},
        trace_id=trace_id,
    )
    revision_id = str(revision["revisionId"])
    if not revision.get("validationResult", {}).get("valid"):
        raise SmokeError("revision failed validation", {"revisionId": revision_id, "validationResult": revision.get("validationResult")})

    render = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/revisions/{revision_id}/render",
        {"installId": args.install_id, "idempotencyKey": f"{edit_job_id}-{revision_id}-phase6b-revision-render"},
        trace_id=trace_id,
    )
    revision_status = wait_for_render(args, edit_job_id, render, trace_id)
    assert_policy_response(revision_status, expected_revision_id=revision_id)

    download = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/download-url?{urlencode({'installId': args.install_id})}",
        trace_id=trace_id,
    )
    revision_dir = output_dir / "revision_more_hype"
    revision_dir.mkdir(parents=True, exist_ok=True)
    revision_final = revision_dir / "final.mp4"
    download_file(str(download["downloadUrl"]), revision_final)
    media = probe_media(revision_final, expected_aspect_ratio="9:16", expected_duration_seconds=to_float(revision_status.get("durationSeconds")))

    render_log = fetch_render_log(args, str(revision_status["renderLogObjectKey"]))
    assert_render_log_metadata(render_log, expected_template_id="personal_highlight_v1", expected_revision_id=revision_id)

    return {
        "editJobId": edit_job_id,
        "revisionId": revision_id,
        "renderJobId": revision_status.get("renderJobId"),
        "outputObjectKey": download.get("outputObjectKey") or revision_status.get("outputObjectKey"),
        "renderLogObjectKey": revision_status.get("renderLogObjectKey"),
        "policy": revision_status.get("policy"),
        "retentionMetadata": revision_status.get("retentionMetadata"),
        "validationResult": revision.get("validationResult"),
        "media": compact_media_summary(media),
        "renderLog": compact_policy_log(render_log),
    }


def run_policy_rejection_smoke(args: argparse.Namespace, source_key: str) -> Dict[str, Any]:
    trace_id = f"{args.trace_id_prefix}-policy-rejection"
    try:
        request_json(
            "POST",
            args.worker_url,
            "v1/edit-jobs",
            {
                "videoId": "phase_edit6b_too_long",
                "analysisJobId": "phase_edit6b_analysis_too_long",
                "installId": args.install_id,
                "sourceObjectKey": source_key,
                "preset": "personal_highlight",
                "templateId": "personal_highlight_v1",
                "targetDurationSeconds": 120,
                "aspectRatio": "9:16",
                "planTier": "free",
                "clips": smoke_clips(),
            },
            trace_id=trace_id,
        )
    except SmokeError as error:
        body = error.payload.get("body") if isinstance(error.payload, dict) else None
        status = error.payload.get("status") if isinstance(error.payload, dict) else None
        if status != 400 or not isinstance(body, dict) or body.get("errorCode") != "render_duration_limit":
            raise
        return {
            "status": "rejected_before_render",
            "httpStatus": status,
            "errorCode": body.get("errorCode"),
            "failureReason": body.get("failureReason"),
        }
    raise SmokeError("policy rejection smoke unexpectedly succeeded", {"expectedErrorCode": "render_duration_limit"})


def assert_policy_response(status: Dict[str, Any], expected_revision_id: Optional[str]) -> None:
    if status.get("status") != "rendered":
        raise SmokeError("render status was not rendered", {"status": status})
    if status.get("revisionId") != expected_revision_id:
        raise SmokeError("render status revisionId mismatch", {"expected": expected_revision_id, "actual": status.get("revisionId")})
    policy = status.get("policy") or {}
    retention = status.get("retentionMetadata") or {}
    required_policy = {
        "planTier": "free",
        "maxRenderSeconds": 45,
        "maxDailyRenders": 3,
        "watermarkRequired": True,
        "outroRequired": True,
    }
    for key, expected in required_policy.items():
        if policy.get(key) != expected:
            raise SmokeError("policy response mismatch", {"field": key, "expected": expected, "actual": policy.get(key)})
    required_retention = {
        "planTier": "free",
        "revisionId": expected_revision_id,
        "retentionClass": "free_final_render",
        "deleteEligible": True,
    }
    for key, expected in required_retention.items():
        if retention.get(key) != expected:
            raise SmokeError("retention metadata mismatch", {"field": key, "expected": expected, "actual": retention.get(key)})
    for key in ["expiresAt", "editJobId", "renderJobId", "templateId", "outputBytes", "durationSeconds"]:
        if key not in retention or retention[key] in {None, ""}:
            raise SmokeError("retention metadata missing field", {"field": key, "retentionMetadata": retention})


def assert_render_log_metadata(render_log: Dict[str, Any], expected_template_id: str, expected_revision_id: Optional[str]) -> None:
    if render_log.get("status") != "rendered":
        raise SmokeError("render log status mismatch", {"status": render_log.get("status")})
    if render_log.get("revisionId") != expected_revision_id:
        raise SmokeError("render log revisionId mismatch", {"expected": expected_revision_id, "actual": render_log.get("revisionId")})
    if render_log.get("planTier") != "free":
        raise SmokeError("render log planTier mismatch", {"planTier": render_log.get("planTier")})
    if render_log.get("policy", {}).get("watermarkRequired") is not True:
        raise SmokeError("render log policy missing watermark requirement", {"policy": render_log.get("policy")})
    retention = render_log.get("retentionMetadata") or {}
    if retention.get("revisionId") != expected_revision_id:
        raise SmokeError("render log retention revisionId mismatch", {"expected": expected_revision_id, "actual": retention.get("revisionId")})
    if retention.get("retentionClass") != "free_final_render":
        raise SmokeError("render log retention class mismatch", {"retentionMetadata": retention})
    ffmpeg = render_log.get("ffmpeg", {})
    if ffmpeg.get("templateId") != expected_template_id:
        raise SmokeError("render log templateId mismatch", {"expected": expected_template_id, "actual": ffmpeg.get("templateId")})
    signature = ffmpeg.get("templateSignature") or {}
    if signature.get("templateId") != expected_template_id:
        raise SmokeError("render log template signature mismatch", {"expected": expected_template_id, "actual": signature})


def fetch_render_log(args: argparse.Namespace, render_log_key: str) -> Dict[str, Any]:
    if args.r2_endpoint_url and args.r2_access_key_id and args.r2_secret_access_key:
        try:
            import boto3
        except ImportError as error:
            raise SmokeError("boto3 is required to verify R2 render logs", {}) from error

        client = boto3.client(
            "s3",
            endpoint_url=args.r2_endpoint_url,
            aws_access_key_id=args.r2_access_key_id,
            aws_secret_access_key=args.r2_secret_access_key,
            region_name=os.getenv("HOOPS_R2_REGION", "auto"),
        )
        log_body = client.get_object(Bucket=args.r2_output_bucket, Key=render_log_key)["Body"].read().decode("utf-8")
        return json.loads(log_body)

    command = [
        "npx",
        "wrangler",
        "r2",
        "object",
        "get",
        f"{args.r2_output_bucket}/{render_log_key}",
        "--remote",
        "--pipe",
    ]
    completed = subprocess.run(
        command,
        cwd=Path(args.wrangler_cwd).resolve(),
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if completed.returncode != 0:
        raise SmokeError(
            "failed to fetch render_log.json from R2",
            {
                "renderLogObjectKey": render_log_key,
                "stderr": completed.stderr[-1000:],
            },
        )
    stdout = strip_wrangler_noise(completed.stdout)
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as error:
        raise SmokeError("render_log.json was not valid JSON", {"renderLogObjectKey": render_log_key, "stdoutTail": stdout[-1000:]}) from error


def strip_wrangler_noise(stdout: str) -> str:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end < start:
        return stdout
    return stdout[start : end + 1]


def compact_policy_log(render_log: Dict[str, Any]) -> Dict[str, Any]:
    ffmpeg = render_log.get("ffmpeg") or {}
    return {
        "status": render_log.get("status"),
        "revisionId": render_log.get("revisionId"),
        "planTier": render_log.get("planTier"),
        "policy": render_log.get("policy"),
        "retentionMetadata": render_log.get("retentionMetadata"),
        "renderCost": render_log.get("renderCost"),
        "ffmpeg": {
            "templateId": ffmpeg.get("templateId"),
            "captionStyle": ffmpeg.get("captionStyle"),
            "templateSignature": ffmpeg.get("templateSignature"),
            "watermarkAssetId": ffmpeg.get("watermarkAssetId"),
            "outroAssetId": ffmpeg.get("outroAssetId"),
            "aspectRatio": ffmpeg.get("aspectRatio"),
            "durationSeconds": ffmpeg.get("durationSeconds"),
        },
    }


def to_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SmokeError, HTTPError) as error:
        details = getattr(error, "payload", {})
        print(json.dumps({"status": "fail", "error": str(error), "details": sanitize_for_log(details)}, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)

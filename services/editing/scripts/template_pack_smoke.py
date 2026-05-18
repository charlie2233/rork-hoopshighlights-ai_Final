#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from live_render_smoke import SmokeError, create_source, download_file, probe_media


@dataclass(frozen=True)
class TemplateCase:
    template_id: str
    preset: str
    target_duration_seconds: int
    aspect_ratio: str
    caption_style: str
    effect_profile: str
    audio_profile: str
    outro_profile: str
    expected_width: int
    expected_height: int
    plan_tier: str = "free"


TEMPLATE_CASES: Dict[str, TemplateCase] = {
    "personal_highlight_v1": TemplateCase(
        template_id="personal_highlight_v1",
        preset="personal_highlight",
        target_duration_seconds=15,
        aspect_ratio="9:16",
        caption_style="bold_hype",
        effect_profile="hype_effects",
        audio_profile="hype",
        outro_profile="free_social_outro",
        expected_width=720,
        expected_height=1280,
    ),
    "full_game_highlight_v1": TemplateCase(
        template_id="full_game_highlight_v1",
        preset="full_game_highlight",
        target_duration_seconds=60,
        aspect_ratio="16:9",
        caption_style="clean_scorebug",
        effect_profile="subtle_recap",
        audio_profile="game_recap",
        outro_profile="standard_recap_outro",
        expected_width=1280,
        expected_height=720,
    ),
    "coach_review_v1": TemplateCase(
        template_id="coach_review_v1",
        preset="coach_review",
        target_duration_seconds=60,
        aspect_ratio="source",
        caption_style="plain",
        effect_profile="minimal_review",
        audio_profile="original_audio",
        outro_profile="minimal_review_outro",
        expected_width=1280,
        expected_height=720,
    ),
    "recruiting_reel_pro_v1": TemplateCase(
        template_id="recruiting_reel_pro_v1",
        preset="personal_highlight",
        target_duration_seconds=60,
        aspect_ratio="9:16",
        caption_style="recruiting_clean_hype",
        effect_profile="recruiting_focus",
        audio_profile="recruiting_clean",
        outro_profile="pro_clean_no_outro",
        expected_width=720,
        expected_height=1280,
        plan_tier="internal",
    ),
    "cinematic_mixtape_pro_v1": TemplateCase(
        template_id="cinematic_mixtape_pro_v1",
        preset="personal_highlight",
        target_duration_seconds=45,
        aspect_ratio="9:16",
        caption_style="cinematic_hype",
        effect_profile="cinematic_mixtape_effects",
        audio_profile="cinematic_mixtape",
        outro_profile="pro_clean_no_outro",
        expected_width=720,
        expected_height=1280,
        plan_tier="internal",
    ),
    "nba_recap_pro_v1": TemplateCase(
        template_id="nba_recap_pro_v1",
        preset="full_game_highlight",
        target_duration_seconds=120,
        aspect_ratio="16:9",
        caption_style="broadcast_scorebug",
        effect_profile="broadcast_recap_effects",
        audio_profile="broadcast_recap",
        outro_profile="pro_clean_no_outro",
        expected_width=1280,
        expected_height=720,
        plan_tier="internal",
    ),
    "team_highlight_pro_v1": TemplateCase(
        template_id="team_highlight_pro_v1",
        preset="full_game_highlight",
        target_duration_seconds=120,
        aspect_ratio="16:9",
        caption_style="team_clean",
        effect_profile="team_package_effects",
        audio_profile="team_package",
        outro_profile="pro_clean_no_outro",
        expected_width=1280,
        expected_height=720,
        plan_tier="internal",
    ),
}

DEFAULT_TEMPLATE_CASES = ["coach_review_v1", "full_game_highlight_v1", "personal_highlight_v1"]


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir or tempfile.mkdtemp(prefix="hoopclips-template-pack-smoke-")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = output_dir / "source.mp4"
    create_source(source_path)
    source_key = upload_source_to_worker(args, source_path)

    selected_cases = [TEMPLATE_CASES[template_id] for template_id in args.templates]
    results: List[Dict[str, Any]] = []
    revision_result: Optional[Dict[str, Any]] = None
    for case in selected_cases:
        results.append(run_template_case(args, output_dir, source_key, case))

    if not args.skip_revision:
        personal = next((result for result in results if result["templateId"] == "personal_highlight_v1"), None)
        if personal:
            revision_result = run_revision_case(args, output_dir, source_key, personal)

    summary = {
        "status": "pass",
        "workerUrl": args.worker_url,
        "editingUrl": args.editing_url,
        "sourceObjectKey": source_key,
        "outputDir": str(output_dir),
        "templates": results,
        "revision": revision_result,
    }
    summary_path = output_dir / "template_pack_smoke_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({**summary, "summaryPath": str(summary_path)}, indent=2, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke HoopClips AI Edit template packs through the active Worker path.")
    parser.add_argument("--worker-url", default=os.getenv("WORKER_BASE_URL", "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"))
    parser.add_argument("--editing-url", default=os.getenv("HOOPS_EDITING_BASE_URL", "https://hoopclips-editing-staging-npya43jiia-uc.a.run.app"))
    parser.add_argument("--install-id", default=os.getenv("HOOPS_SMOKE_INSTALL_ID", f"smoke-template-pack-{int(time.time())}"))
    parser.add_argument("--app-version", default=os.getenv("HOOPS_SMOKE_APP_VERSION", "phase-edit5b-smoke"))
    parser.add_argument("--analysis-version", default=os.getenv("HOOPS_SMOKE_ANALYSIS_VERSION", "phase-edit5b-smoke"))
    parser.add_argument("--output-dir", default=os.getenv("HOOPS_SMOKE_OUTPUT_DIR"))
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("HOOPS_SMOKE_TIMEOUT_SECONDS", "360")))
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("HOOPS_SMOKE_POLL_SECONDS", "2")))
    parser.add_argument("--trace-id-prefix", default=os.getenv("HOOPS_SMOKE_TRACE_ID", "phase-edit5b-template-pack-smoke"))
    parser.add_argument("--templates", nargs="+", choices=sorted(TEMPLATE_CASES), default=DEFAULT_TEMPLATE_CASES)
    parser.add_argument("--skip-revision", action="store_true")
    parser.add_argument("--r2-output-bucket", default=os.getenv("HOOPS_R2_OUTPUT_BUCKET") or os.getenv("HOOPS_R2_BUCKET") or "hoopsclips-results-staging")
    parser.add_argument("--r2-endpoint-url", default=os.getenv("HOOPS_R2_ENDPOINT_URL"))
    parser.add_argument("--r2-access-key-id", default=os.getenv("HOOPS_R2_ACCESS_KEY_ID"))
    parser.add_argument("--r2-secret-access-key", default=os.getenv("HOOPS_R2_SECRET_ACCESS_KEY"))
    parser.add_argument("--require-r2-log", action="store_true")
    args = parser.parse_args()
    if not args.worker_url:
        raise SmokeError("WORKER_BASE_URL is required", {})
    return args


def run_template_case(args: argparse.Namespace, output_dir: Path, source_key: str, case: TemplateCase) -> Dict[str, Any]:
    trace_id = f"{args.trace_id_prefix}-{case.template_id}"
    clips = smoke_clips()
    edit_job = request_json(
        "POST",
        args.worker_url,
        "v1/edit-jobs",
        {
            "videoId": f"template_pack_{case.template_id}",
            "analysisJobId": f"template_pack_analysis_{case.template_id}",
            "installId": args.install_id,
            "sourceObjectKey": source_key,
            "preset": case.preset,
            "templateId": case.template_id,
            "targetDurationSeconds": case.target_duration_seconds,
            "aspectRatio": case.aspect_ratio,
            "planTier": case.plan_tier,
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
    assert_equal(plan.get("templateId"), case.template_id, "plan.templateId")
    assert_equal(plan.get("captionStyle"), case.caption_style, "plan.captionStyle")
    assert_equal(plan.get("aspectRatio"), case.aspect_ratio, "plan.aspectRatio")
    assert_equal(int(plan.get("targetDurationSeconds")), case.target_duration_seconds, "plan.targetDurationSeconds")

    render_status = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/render",
        {
            "installId": args.install_id,
            "sourceObjectKey": source_key,
            "planTier": case.plan_tier,
            "editPlan": plan,
            "sourceClips": clips,
        },
        trace_id=trace_id,
    )
    render_status = wait_for_render(args, edit_job_id, render_status, trace_id)
    download = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/download-url?{urlencode({'installId': args.install_id})}",
        trace_id=trace_id,
    )
    case_dir = output_dir / case.template_id
    case_dir.mkdir(parents=True, exist_ok=True)
    final_path = case_dir / "final.mp4"
    download_file(str(download["downloadUrl"]), final_path)
    media = probe_media(
        final_path,
        expected_aspect_ratio="16:9" if case.aspect_ratio == "source" else case.aspect_ratio,
        expected_duration_seconds=to_float_or_none(render_status.get("durationSeconds")),
    )
    assert_media_dimensions(media, case.expected_width, case.expected_height, case.template_id)

    render_log_key = str(render_status.get("renderLogObjectKey") or "")
    output_object_key = str(download.get("outputObjectKey") or render_status.get("outputObjectKey") or "")
    r2 = load_render_log_and_heads(args, render_log_key, output_object_key)
    if r2.get("renderLog"):
        assert_template_log(r2["renderLog"], case)

    return {
        "templateId": case.template_id,
        "preset": case.preset,
        "editJobId": edit_job_id,
        "renderJobId": render_status.get("renderJobId"),
        "outputObjectKey": output_object_key,
        "renderLogObjectKey": render_log_key,
        "downloadedPath": str(final_path),
        "plan": {
            "templateId": plan.get("templateId"),
            "captionStyle": plan.get("captionStyle"),
            "aspectRatio": plan.get("aspectRatio"),
            "targetDurationSeconds": plan.get("targetDurationSeconds"),
            "audio": plan.get("audio"),
        },
        "media": compact_media_summary(media),
        "r2": r2,
    }


def run_revision_case(args: argparse.Namespace, output_dir: Path, source_key: str, base_result: Dict[str, Any]) -> Dict[str, Any]:
    edit_job_id = str(base_result["editJobId"])
    trace_id = f"{args.trace_id_prefix}-revision-more-hype"
    revision = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/revise",
        {"installId": args.install_id, "command": "make_more_hype"},
        trace_id=trace_id,
    )
    revision_id = str(revision["revisionId"])
    revised_plan = revision["revisedPlan"]
    assert_equal(revised_plan.get("templateId"), "personal_highlight_v1", "revision.revisedPlan.templateId")
    if not revision.get("validationResult", {}).get("valid"):
        raise SmokeError("revision did not validate", {"revisionId": revision_id, "validationResult": revision.get("validationResult")})

    render_status = request_json(
        "POST",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/revisions/{revision_id}/render",
        {"installId": args.install_id},
        trace_id=trace_id,
    )
    render_status = wait_for_render(args, edit_job_id, render_status, trace_id)
    download = request_json(
        "GET",
        args.worker_url,
        f"v1/edit-jobs/{edit_job_id}/download-url?{urlencode({'installId': args.install_id})}",
        trace_id=trace_id,
    )
    revision_dir = output_dir / "revision_more_hype"
    revision_dir.mkdir(parents=True, exist_ok=True)
    final_path = revision_dir / "final.mp4"
    download_file(str(download["downloadUrl"]), final_path)
    media = probe_media(final_path, expected_aspect_ratio="9:16", expected_duration_seconds=to_float_or_none(render_status.get("durationSeconds")))

    render_log_key = str(render_status.get("renderLogObjectKey") or "")
    output_object_key = str(download.get("outputObjectKey") or render_status.get("outputObjectKey") or "")
    r2 = load_render_log_and_heads(args, render_log_key, output_object_key)
    if r2.get("renderLog"):
        assert_template_log(r2["renderLog"], TEMPLATE_CASES["personal_highlight_v1"])

    return {
        "command": "make_more_hype",
        "editJobId": edit_job_id,
        "revisionId": revision_id,
        "renderJobId": render_status.get("renderJobId"),
        "outputObjectKey": output_object_key,
        "renderLogObjectKey": render_log_key,
        "downloadedPath": str(final_path),
        "revisedTemplateId": revised_plan.get("templateId"),
        "validationResult": revision.get("validationResult"),
        "media": compact_media_summary(media),
        "r2": r2,
    }


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
        trace_id=args.trace_id_prefix,
    )
    upload_headers = {str(key): str(value) for key, value in response.get("uploadHeaders", {}).items()}
    if "content-type" not in {key.lower() for key in upload_headers}:
        upload_headers["Content-Type"] = "video/mp4"
    upload_method = str(response.get("uploadMethod", "PUT"))
    with urlopen(Request(str(response["uploadUrl"]), data=source_path.read_bytes(), headers=upload_headers, method=upload_method), timeout=120) as upload_response:
        if upload_response.status >= 400:
            raise SmokeError("signed source upload failed", {"status": upload_response.status})
    return str(response["sourceObjectKey"])


def smoke_clips() -> List[Dict[str, Any]]:
    return [
        clip("c1", 0.0, 10.0, "Fast Break", 0.95),
        clip("c2", 8.0, 18.0, "Made Shot", 0.90),
    ]


def clip(clip_id: str, start: float, end: float, label: str, score: float) -> Dict[str, Any]:
    return {
        "id": clip_id,
        "start": start,
        "end": end,
        "eventCenter": start + ((end - start) / 2.0),
        "label": label,
        "confidence": score,
        "excitement": score,
        "watchability": score,
        "motionScore": score,
        "audioPeak": score / 2.0,
        "combinedScore": score,
    }


def wait_for_render(args: argparse.Namespace, edit_job_id: str, status: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    deadline = time.time() + args.timeout_seconds
    while time.time() < deadline and status.get("status") not in {"rendered", "failed", "cancelled"}:
        time.sleep(args.poll_seconds)
        try:
            status = request_json(
                "GET",
                args.worker_url,
                f"v1/edit-jobs/{edit_job_id}/render-status?{urlencode({'installId': args.install_id})}",
                trace_id=trace_id,
            )
        except SmokeError as error:
            if is_transient_render_not_found(error):
                status = {"status": "render_requested", "transientStatusError": error.payload}
                continue
            raise
    if status.get("status") != "rendered":
        raise SmokeError("render did not reach rendered", {"editJobId": edit_job_id, "renderStatus": status})
    return status


def is_transient_render_not_found(error: SmokeError) -> bool:
    body = error.payload.get("body") if isinstance(error.payload, dict) else None
    return isinstance(body, dict) and body.get("errorCode") == "render_job_not_found"


def load_render_log_and_heads(args: argparse.Namespace, render_log_key: str, output_object_key: str) -> Dict[str, Any]:
    if not render_log_key or not output_object_key:
        raise SmokeError("render status did not expose R2 object keys", {"renderLogObjectKey": render_log_key, "outputObjectKey": output_object_key})
    missing = [
        key
        for key, value in {
            "HOOPS_R2_ENDPOINT_URL": args.r2_endpoint_url,
            "HOOPS_R2_ACCESS_KEY_ID": args.r2_access_key_id,
            "HOOPS_R2_SECRET_ACCESS_KEY": args.r2_secret_access_key,
        }.items()
        if not value
    ]
    if missing:
        if args.require_r2_log:
            raise SmokeError("R2 credentials are required to verify render_log.json", {"missing": missing})
        return {"checked": False, "reason": "R2 credentials not configured"}

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
    final_head = client.head_object(Bucket=args.r2_output_bucket, Key=output_object_key)
    log_head = client.head_object(Bucket=args.r2_output_bucket, Key=render_log_key)
    log_body = client.get_object(Bucket=args.r2_output_bucket, Key=render_log_key)["Body"].read().decode("utf-8")
    render_log = json.loads(log_body)
    return {
        "checked": True,
        "bucket": args.r2_output_bucket,
        "finalHead": {
            "contentLength": final_head.get("ContentLength"),
            "contentType": final_head.get("ContentType"),
        },
        "renderLogHead": {
            "contentLength": log_head.get("ContentLength"),
            "contentType": log_head.get("ContentType"),
        },
        "renderLog": compact_render_log(render_log),
    }


def assert_template_log(render_log: Dict[str, Any], case: TemplateCase) -> None:
    ffmpeg = render_log.get("ffmpeg", render_log)
    signature = ffmpeg.get("templateSignature") or {}
    assert_equal(ffmpeg.get("templateId"), case.template_id, "renderLog.ffmpeg.templateId")
    assert_equal(ffmpeg.get("captionStyle"), case.caption_style, "renderLog.ffmpeg.captionStyle")
    assert_equal(signature.get("templateId"), case.template_id, "renderLog.ffmpeg.templateSignature.templateId")
    assert_equal(signature.get("captionStyle"), case.caption_style, "renderLog.ffmpeg.templateSignature.captionStyle")
    assert_equal(signature.get("effectProfile"), case.effect_profile, "renderLog.ffmpeg.templateSignature.effectProfile")
    assert_equal(signature.get("audioProfile"), case.audio_profile, "renderLog.ffmpeg.templateSignature.audioProfile")
    assert_equal(signature.get("outroProfile"), case.outro_profile, "renderLog.ffmpeg.templateSignature.outroProfile")


def compact_render_log(render_log: Dict[str, Any]) -> Dict[str, Any]:
    ffmpeg = render_log.get("ffmpeg", {})
    return {
        "status": render_log.get("status"),
        "failureReason": render_log.get("failureReason"),
        "ffmpeg": {
            "templateId": ffmpeg.get("templateId"),
            "captionStyle": ffmpeg.get("captionStyle"),
            "templateSignature": ffmpeg.get("templateSignature"),
            "watermarkAssetId": ffmpeg.get("watermarkAssetId"),
            "outroAssetId": ffmpeg.get("outroAssetId"),
            "aspectRatio": ffmpeg.get("aspectRatio"),
            "durationSeconds": ffmpeg.get("durationSeconds"),
            "clipCount": ffmpeg.get("clipCount"),
            "segmentCount": ffmpeg.get("segmentCount"),
        },
    }


def compact_media_summary(media: Dict[str, Any]) -> Dict[str, Any]:
    streams = media.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    return {
        "format": media.get("format", {}),
        "video": {
            "codec_name": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "pix_fmt": video.get("pix_fmt"),
            "r_frame_rate": video.get("r_frame_rate"),
        },
        "audio": {
            "codec_name": audio.get("codec_name"),
        },
    }


def assert_media_dimensions(media: Dict[str, Any], width: int, height: int, label: str) -> None:
    video = next((stream for stream in media.get("streams", []) if stream.get("codec_type") == "video"), None)
    if not video or video.get("width") != width or video.get("height") != height:
        raise SmokeError("rendered dimensions did not match template expectation", {"template": label, "expected": [width, height], "video": video})


def assert_equal(actual: object, expected: object, field: str) -> None:
    if actual != expected:
        raise SmokeError("unexpected smoke value", {"field": field, "expected": expected, "actual": actual})


def request_json(
    method: str,
    base_url: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    trace_id: str = "",
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "HoopClipsTemplatePackSmoke/1.0", "x-trace-id": trace_id}
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


def to_float_or_none(value: object) -> Optional[float]:
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

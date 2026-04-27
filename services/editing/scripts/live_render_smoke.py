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
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root / "ios" / "backend"))
    from app.editing import CreateEditJobRequest, build_edit_job

    args = parse_args()
    output_dir = Path(args.output_dir or tempfile.mkdtemp(prefix="hoopclips-editing-smoke-")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_key = args.source_object_key or f"sources/editing-smoke-{int(time.time())}.mp4"
    source_path = output_dir / "source.mp4"
    final_path = output_dir / "final.mp4"

    run(["ffmpeg", "-version"], capture=True)
    run(["ffprobe", "-version"], capture=True)

    if not args.source_object_key:
        create_source(source_path)
        if args.render_storage_provider == "r2":
            upload_to_r2(source_key, source_path)
        else:
            upload_root = Path(args.upload_root or os.getenv("HOOPS_UPLOAD_ROOT", "/tmp/hoopclips-editing")).resolve()
            local_path = upload_root.joinpath(*safe_key_parts(source_key))
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(source_path.read_bytes())

    edit_request = CreateEditJobRequest(
        videoId="editing_smoke_video",
        analysisJobId="editing_smoke_analysis",
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
    edit_job = build_edit_job(edit_request, "edit_smoke_" + str(int(time.time())))
    if edit_job.validation_errors:
        raise SmokeError("edit plan generation failed", {"validationErrors": [error.model_dump() for error in edit_job.validation_errors]})

    base_url = args.base_url.rstrip("/") + "/"
    readyz = get_json(base_url, "readyz")
    if readyz.get("status") != "ok" and not args.allow_degraded_readyz:
        raise SmokeError("readyz is not ok", readyz)

    headers = {}
    if args.editing_secret:
        headers["x-hoops-editing-secret"] = args.editing_secret
    payload = {
        "editJobId": edit_job.edit_job_id,
        "installId": args.install_id,
        "sourceObjectKey": source_key,
        "planTier": "free",
        "editPlan": edit_job.plan.model_dump(),
        "sourceClips": [clip.model_dump() for clip in edit_request.clips],
    }
    create_response = post_json(base_url, "v1/render-jobs", payload, headers)
    render_job_id = create_response["renderJobId"]
    status = create_response
    deadline = time.time() + args.timeout_seconds
    while time.time() < deadline:
        if status["status"] in {"rendered", "failed", "cancelled"}:
            break
        time.sleep(args.poll_seconds)
        status = get_json(
            base_url,
            f"v1/render-jobs/{render_job_id}",
            {"installId": args.install_id},
            headers,
        )
    if status["status"] != "rendered":
        raise SmokeError("render did not reach rendered", status)

    download = get_json(
        base_url,
        f"v1/render-jobs/{render_job_id}/download-url",
        {"installId": args.install_id},
        headers,
    )
    download_file(download["downloadUrl"], final_path)
    media = probe_media(final_path, expected_aspect_ratio=edit_job.plan.aspectRatio, expected_duration_seconds=status.get("durationSeconds"))
    print(
        json.dumps(
            {
                "status": "pass",
                "baseUrl": args.base_url,
                "editJobId": edit_job.edit_job_id,
                "renderJobId": render_job_id,
                "sourceObjectKey": source_key,
                "outputObjectKey": status.get("outputObjectKey"),
                "renderLogObjectKey": status.get("renderLogObjectKey"),
                "durationSeconds": status.get("durationSeconds"),
                "downloadedPath": str(final_path),
                "readyz": readyz,
                "media": media,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke the canonical HoopClips editing service render path.")
    parser.add_argument("--base-url", default=os.getenv("HOOPS_EDITING_BASE_URL", "http://127.0.0.1:8090"))
    parser.add_argument("--install-id", default=os.getenv("HOOPS_SMOKE_INSTALL_ID", "smoke-install-001"))
    parser.add_argument("--source-object-key", default=os.getenv("HOOPS_SMOKE_SOURCE_OBJECT_KEY"))
    parser.add_argument("--render-storage-provider", default=os.getenv("HOOPS_RENDER_STORAGE_PROVIDER", "local"), choices=["local", "r2"])
    parser.add_argument("--upload-root", default=os.getenv("HOOPS_UPLOAD_ROOT"))
    parser.add_argument("--editing-secret", default=os.getenv("HOOPS_EDITING_SERVICE_SECRET"))
    parser.add_argument("--output-dir", default=os.getenv("HOOPS_SMOKE_OUTPUT_DIR"))
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("HOOPS_SMOKE_TIMEOUT_SECONDS", "180")))
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("HOOPS_SMOKE_POLL_SECONDS", "2")))
    parser.add_argument("--allow-degraded-readyz", action="store_true")
    return parser.parse_args()


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


def create_source(path: Path) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=640x360:rate=30:duration=18",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=18",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        capture=True,
    )


def upload_to_r2(object_key: str, source_path: Path) -> None:
    try:
        import boto3
    except ImportError as error:
        raise SmokeError("boto3 is required for R2 smoke source upload", {}) from error

    required = {
        "HOOPS_R2_BUCKET": os.getenv("HOOPS_R2_SOURCE_BUCKET") or os.getenv("HOOPS_R2_BUCKET"),
        "HOOPS_R2_ENDPOINT_URL": os.getenv("HOOPS_R2_ENDPOINT_URL"),
        "HOOPS_R2_ACCESS_KEY_ID": os.getenv("HOOPS_R2_ACCESS_KEY_ID"),
        "HOOPS_R2_SECRET_ACCESS_KEY": os.getenv("HOOPS_R2_SECRET_ACCESS_KEY"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise SmokeError("missing R2 env vars for smoke upload", {"missing": missing})
    client = boto3.client(
        "s3",
        endpoint_url=required["HOOPS_R2_ENDPOINT_URL"],
        aws_access_key_id=required["HOOPS_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=required["HOOPS_R2_SECRET_ACCESS_KEY"],
        region_name=os.getenv("HOOPS_R2_REGION", "auto"),
    )
    client.upload_file(str(source_path), required["HOOPS_R2_BUCKET"], object_key, ExtraArgs={"ContentType": "video/mp4"})


def get_json(base_url: str, path: str, query: Optional[Dict[str, str]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    suffix = path + (("?" + urlencode(query)) if query else "")
    request = Request(urljoin(base_url, suffix), headers=headers or {})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(base_url: str, path: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    request = Request(
        urljoin(base_url, path),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url: str, destination: Path) -> None:
    with urlopen(url, timeout=60) as response:
        destination.write_bytes(response.read())
    if destination.stat().st_size <= 0:
        raise SmokeError("downloaded render output is empty", {"path": str(destination)})


def probe_media(path: Path, expected_aspect_ratio: str, expected_duration_seconds: Optional[float]) -> Dict[str, Any]:
    run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture=True)
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration,size:stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video_stream:
        raise SmokeError("rendered MP4 has no video stream", payload)
    if not audio_stream:
        raise SmokeError("rendered MP4 has no audio stream", payload)
    if "mp4" not in str(payload.get("format", {}).get("format_name", "")):
        raise SmokeError("rendered output is not an MP4 container", payload)
    if video_stream.get("codec_name") != "h264":
        raise SmokeError("rendered video stream is not h264", payload)
    if audio_stream.get("codec_name") != "aac":
        raise SmokeError("rendered audio stream is not aac", payload)
    expected_size = {"9:16": (720, 1280), "16:9": (1280, 720)}.get(expected_aspect_ratio)
    if expected_size and (video_stream.get("width"), video_stream.get("height")) != expected_size:
        raise SmokeError(
            "rendered output resolution does not match expected aspect ratio",
            {"expected": expected_size, "actual": [video_stream.get("width"), video_stream.get("height")], "media": payload},
        )
    duration = _float_or_none(payload.get("format", {}).get("duration"))
    if expected_duration_seconds is not None and duration is not None and abs(duration - float(expected_duration_seconds)) > 0.75:
        raise SmokeError(
            "rendered output duration does not match render status",
            {"expectedDurationSeconds": expected_duration_seconds, "actualDurationSeconds": duration},
        )
    return payload


def _float_or_none(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_key_parts(object_key: str) -> list[str]:
    parts = [part for part in Path(object_key).parts if part not in {"", ".", ".."}]
    if not parts:
        raise SmokeError("invalid source object key", {"sourceObjectKey": object_key})
    return parts


def run(command: list[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True) if capture else subprocess.run(command, check=True)
    except FileNotFoundError as error:
        raise SmokeError(f"missing required binary: {command[0]}", {}) from error
    except subprocess.CalledProcessError as error:
        raise SmokeError("command failed", {"command": command[0], "stderr": error.stderr}) from error


class SmokeError(RuntimeError):
    def __init__(self, message: str, payload: Dict[str, Any]) -> None:
        super().__init__(message)
        self.payload = payload


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as error:
        print(json.dumps({"status": "fail", "error": str(error), "details": error.payload}, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)

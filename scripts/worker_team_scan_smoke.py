#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class SmokeError(Exception):
    def __init__(self, message: str, payload: Dict[str, Any]) -> None:
        super().__init__(message)
        self.payload = payload


SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "callbackurl",
    "credential",
    "downloadurl",
    "objectkey",
    "secret",
    "signature",
    "sourceurl",
    "token",
    "uploadurl",
)
SAFE_URL_KEYS = {"workerurl"}
PRESIGNED_URL_MARKERS = ("X-Amz-", "Signature=", "Credential=", "AccessKeyId=", "token=")


def main() -> int:
    args = parse_args()
    result = run_smoke(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke the active Worker team-scan path with a real uploaded video. "
            "Output avoids presigned URLs, object keys, and secrets."
        )
    )
    parser.add_argument("--worker-url", default=os.getenv("WORKER_BASE_URL"))
    parser.add_argument("--video-path", default=os.getenv("HOOPS_TEAM_SCAN_SMOKE_VIDEO_PATH"))
    parser.add_argument("--duration-seconds", type=float, default=float(os.getenv("HOOPS_TEAM_SCAN_SMOKE_DURATION_SECONDS", "30")))
    parser.add_argument("--install-id", default=os.getenv("HOOPS_SMOKE_INSTALL_ID", "team-scan-smoke-install"))
    parser.add_argument("--app-version", default=os.getenv("HOOPS_SMOKE_APP_VERSION", "worker-team-scan-smoke"))
    parser.add_argument("--analysis-version", default=os.getenv("HOOPS_SMOKE_ANALYSIS_VERSION", "worker-team-scan-smoke"))
    parser.add_argument("--allow-unavailable", action="store_true", help="Do not fail when the scan provider returns no teams.")
    parser.add_argument("--start-selected-team", action="store_true", help="After a successful scan, start analysis for one detected team.")
    parser.add_argument("--start-all-teams", action="store_true", help="After upload/scan, start analysis in all-teams mode.")
    parser.add_argument("--selected-team-id", default=os.getenv("HOOPS_TEAM_SCAN_SMOKE_SELECTED_TEAM_ID"))
    parser.add_argument("--selected-color-label", default=os.getenv("HOOPS_TEAM_SCAN_SMOKE_SELECTED_COLOR_LABEL"))
    parser.add_argument("--confidence-threshold", type=float, default=float(os.getenv("HOOPS_TEAM_SCAN_SMOKE_CONFIDENCE_THRESHOLD", "0.85")))
    args = parser.parse_args()
    if not args.worker_url:
        raise SmokeError("WORKER_BASE_URL is required for team-scan smoke.", {})
    if not args.video_path:
        raise SmokeError("HOOPS_TEAM_SCAN_SMOKE_VIDEO_PATH or --video-path is required.", {})
    if args.start_selected_team and args.start_all_teams:
        raise SmokeError("Choose only one of --start-selected-team or --start-all-teams.", {})
    if args.duration_seconds <= 0:
        raise SmokeError("Duration must be positive.", {"durationSeconds": args.duration_seconds})
    return args


def run_smoke(args: argparse.Namespace) -> Dict[str, Any]:
    video_path = Path(args.video_path).expanduser().resolve()
    if not video_path.exists() or not video_path.is_file():
        raise SmokeError("Smoke video does not exist.", {"videoPath": str(video_path)})

    base_url = args.worker_url.rstrip("/") + "/"
    trace_id = "team_scan_smoke_" + str(int(time.time()))
    create_payload = build_create_payload(args, video_path)
    created = request_json("POST", base_url, "v1/analysis/jobs", create_payload, trace_id=trace_id)
    job_id = require_string(created, "jobId")
    upload_url = require_string(created, "uploadUrl")
    upload_headers = created.get("uploadHeaders") if isinstance(created.get("uploadHeaders"), dict) else {}
    upload_video(upload_url, upload_headers, video_path)

    scan = request_json(
        "POST",
        base_url,
        f"v1/analysis/jobs/{job_id}/team-scan",
        {"installId": args.install_id},
        trace_id=trace_id,
    )
    detected_teams = normalize_detected_teams(scan.get("detectedTeams"))
    if not detected_teams and not args.allow_unavailable:
        raise SmokeError("Team scan returned no selectable teams.", {"jobId": job_id, "scan": scan})

    result: Dict[str, Any] = {
        "status": "pass",
        "workerUrl": args.worker_url,
        "jobId": job_id,
        "teamScanStatus": scan.get("status", "unavailable"),
        "detectedTeamCount": len(detected_teams),
        "detectedTeams": detected_teams,
    }

    if args.start_selected_team:
        selected = choose_team(detected_teams, args.selected_team_id, args.selected_color_label)
        if selected is None:
            raise SmokeError("Requested selected team was not present in scan output.", {"requestedTeamId": args.selected_team_id})
        start_payload = {
            "installId": args.install_id,
            "teamSelection": {
                "mode": "team",
                "teamId": selected.get("teamId"),
                "label": selected.get("label"),
                "colorLabel": selected.get("colorLabel"),
                "confidenceThreshold": args.confidence_threshold,
                "includeUncertain": True,
            },
        }
        start = request_json("POST", base_url, f"v1/analysis/jobs/{job_id}/start", start_payload, trace_id=trace_id)
        result["analysisStart"] = {
            "mode": "team",
            "teamId": selected.get("teamId"),
            "colorLabel": selected.get("colorLabel"),
            "status": start.get("status"),
        }
    elif args.start_all_teams:
        start = request_json(
            "POST",
            base_url,
            f"v1/analysis/jobs/{job_id}/start",
            {"installId": args.install_id, "teamSelection": {"mode": "all"}},
            trace_id=trace_id,
        )
        result["analysisStart"] = {"mode": "all", "status": start.get("status")}

    return sanitize_for_log(result)


def build_create_payload(args: argparse.Namespace, video_path: Path) -> Dict[str, Any]:
    content_type = mimetypes.guess_type(video_path.name)[0] or "video/mp4"
    return {
        "filename": video_path.name,
        "contentType": content_type,
        "fileSizeBytes": video_path.stat().st_size,
        "durationSeconds": args.duration_seconds,
        "installId": args.install_id,
        "appVersion": args.app_version,
        "analysisVersion": args.analysis_version,
    }


def request_json(method: str, base_url: str, path: str, payload: Optional[Dict[str, Any]] = None, trace_id: str = "") -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "HoopClipsTeamScanSmoke/1.0", "x-trace-id": trace_id}
    try:
        with urlopen(Request(urljoin(base_url, path), data=data, headers=headers, method=method), timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            parsed_body: object = json.loads(body)
        except json.JSONDecodeError:
            parsed_body = body[:1000]
        raise SmokeError(
            f"{method} {path} failed with HTTP {error.code}",
            {"status": error.code, "body": parsed_body, "headers": dict(error.headers)},
        ) from error
    except URLError as error:
        raise SmokeError(f"{method} {path} failed", {"reason": str(error)}) from error


def upload_video(upload_url: str, upload_headers: Dict[str, Any], video_path: Path) -> None:
    headers = {str(key): str(value) for key, value in upload_headers.items()}
    data = video_path.read_bytes()
    try:
        with urlopen(Request(upload_url, data=data, headers=headers, method="PUT"), timeout=120) as response:
            if response.status >= 400:
                raise SmokeError("Upload failed.", {"status": response.status})
    except HTTPError as error:
        raise SmokeError("Upload failed.", {"status": error.code, "headers": dict(error.headers)}) from error
    except URLError as error:
        raise SmokeError("Upload failed.", {"reason": str(error)}) from error


def normalize_detected_teams(value: object) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    teams: list[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        team_id = item.get("teamId")
        label = item.get("label")
        if not isinstance(team_id, str) or not isinstance(label, str):
            continue
        teams.append(
            {
                "teamId": team_id,
                "label": label,
                "colorLabel": item.get("colorLabel") if isinstance(item.get("colorLabel"), str) else None,
                "confidence": item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else None,
            }
        )
    return teams


def choose_team(teams: list[Dict[str, Any]], team_id: Optional[str], color_label: Optional[str]) -> Optional[Dict[str, Any]]:
    normalized_color = color_label.strip().lower() if color_label else None
    for team in teams:
        if team_id and team.get("teamId") == team_id:
            return team
        if normalized_color and isinstance(team.get("colorLabel"), str) and team["colorLabel"].strip().lower() == normalized_color:
            return team
    return teams[0] if teams and not team_id and not normalized_color else None


def require_string(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SmokeError(f"Response missing {key}.", {"response": payload})
    return value


def sanitize_for_log(value: Any, key: str = "") -> Any:
    normalized_key = key.replace("_", "").replace("-", "").lower()
    if any(fragment in normalized_key for fragment in SENSITIVE_KEY_FRAGMENTS) or ("url" in normalized_key and normalized_key not in SAFE_URL_KEYS):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(child_key): sanitize_for_log(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [sanitize_for_log(item, key) for item in value]
    if isinstance(value, str) and any(marker.lower() in value.lower() for marker in PRESIGNED_URL_MARKERS):
        return "[redacted]"
    return value


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as error:
        print(json.dumps({"status": "fail", "error": str(error), "details": sanitize_for_log(error.payload)}, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)

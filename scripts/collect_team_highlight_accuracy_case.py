#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.make_team_highlight_label_template import build_label_template
from scripts.worker_team_scan_smoke import (
    SmokeError,
    choose_team,
    normalize_detected_teams,
    request_json,
    sanitize_for_log,
    upload_video,
)


DEFAULT_WORKER_URL = "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "succeeded", "expired"}


def main() -> int:
    args = parse_args()
    try:
        result = collect_case(args)
    except SmokeError as error:
        print(json.dumps({"status": "fail", "error": str(error), "details": sanitize_for_log(error.payload)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    except ValueError as error:
        print(json.dumps({"status": "fail", "error": str(error)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps(sanitize_for_log(result), indent=2, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upload a real basketball clip to the cloud Worker, run team/all-teams analysis, "
            "and write the analysis JSON plus a manual-label template for launch accuracy evaluation. "
            "This script does not inspect video pixels or run local analysis."
        )
    )
    parser.add_argument("--worker-url", default=os.getenv("WORKER_BASE_URL", DEFAULT_WORKER_URL))
    parser.add_argument("--video-path", required=True, help="Real basketball video to upload to staging.")
    parser.add_argument("--duration-seconds", type=float, default=float(os.getenv("HOOPS_TEAM_SCAN_SMOKE_DURATION_SECONDS", "30")))
    parser.add_argument("--case-id", help="Stable case ID for the accuracy manifest.")
    parser.add_argument("--video-id", help="Stable video ID for the accuracy manifest.")
    parser.add_argument("--team-mode", choices=("team", "all"), default="team")
    parser.add_argument("--selected-team-id", default=os.getenv("HOOPS_TEAM_SCAN_SMOKE_SELECTED_TEAM_ID"))
    parser.add_argument("--selected-color-label", default=os.getenv("HOOPS_TEAM_SCAN_SMOKE_SELECTED_COLOR_LABEL"))
    parser.add_argument("--confidence-threshold", type=float, default=float(os.getenv("HOOPS_TEAM_SCAN_SMOKE_CONFIDENCE_THRESHOLD", "0.85")))
    parser.add_argument("--allow-scan-unavailable", action="store_true")
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--install-id", default=os.getenv("HOOPS_SMOKE_INSTALL_ID", "team-highlight-accuracy-collector"))
    parser.add_argument("--app-version", default=os.getenv("HOOPS_SMOKE_APP_VERSION", "team-highlight-accuracy-collector"))
    parser.add_argument("--analysis-version", default=os.getenv("HOOPS_SMOKE_ANALYSIS_VERSION", "team-highlight-accuracy-collector"))
    parser.add_argument("--output-dir", default="artifacts/team_highlight_accuracy")
    parser.add_argument("--manifest", default="artifacts/team_highlight_accuracy_manifest.json")
    parser.add_argument("--no-manifest", action="store_true", help="Write case artifacts but do not create/update the manifest.")
    args = parser.parse_args()
    if args.duration_seconds <= 0:
        raise SmokeError("Duration must be positive.", {"durationSeconds": args.duration_seconds})
    if args.poll_interval_seconds <= 0:
        raise SmokeError("Poll interval must be positive.", {"pollIntervalSeconds": args.poll_interval_seconds})
    if args.timeout_seconds <= 0:
        raise SmokeError("Timeout must be positive.", {"timeoutSeconds": args.timeout_seconds})
    return args


def collect_case(args: argparse.Namespace) -> dict[str, Any]:
    video_path = Path(args.video_path).expanduser().resolve()
    if not video_path.exists() or not video_path.is_file():
        raise SmokeError("Accuracy collection video does not exist.", {"videoPath": str(video_path)})

    base_url = args.worker_url.rstrip("/") + "/"
    case_id = args.case_id or default_case_id(video_path)
    video_id = args.video_id or video_path.stem
    case_dir = Path(args.output_dir).expanduser().resolve() / safe_path_segment(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)

    trace_id = f"accuracy_case_{safe_path_segment(case_id)}_{int(time.time())}"
    created = request_json("POST", base_url, "v1/analysis/jobs", build_create_payload(args, video_path), trace_id=trace_id)
    job_id = require_string(created, "jobId")
    upload_video(require_string(created, "uploadUrl"), created.get("uploadHeaders") if isinstance(created.get("uploadHeaders"), dict) else {}, video_path)

    detected_teams: list[dict[str, Any]] = []
    selected_team: dict[str, Any] | None = None
    if args.team_mode == "team":
        scan = request_json("POST", base_url, f"v1/analysis/jobs/{job_id}/team-scan", {"installId": args.install_id}, trace_id=trace_id)
        detected_teams = normalize_detected_teams(scan.get("detectedTeams"))
        if not detected_teams and not args.allow_scan_unavailable:
            raise SmokeError("Team scan returned no selectable teams.", {"jobId": job_id, "scan": scan})
        selected_team = choose_team(detected_teams, args.selected_team_id, args.selected_color_label)
        if selected_team is None:
            raise SmokeError(
                "Requested selected team was not present in scan output.",
                {"requestedTeamId": args.selected_team_id, "requestedColorLabel": args.selected_color_label, "jobId": job_id},
            )

    start = request_json(
        "POST",
        base_url,
        f"v1/analysis/jobs/{job_id}/start",
        {"installId": args.install_id, "teamSelection": team_selection_payload(args, selected_team)},
        trace_id=trace_id,
    )
    final_job = poll_job(base_url, job_id, trace_id, args.timeout_seconds, args.poll_interval_seconds)
    if final_job.get("status") not in {"completed", "succeeded"} or not isinstance(final_job.get("results"), dict):
        raise SmokeError("Cloud analysis did not complete with result metadata.", {"jobId": job_id, "job": final_job})

    analysis_path = case_dir / "analysis_result.json"
    labels_path = case_dir / "manual_labels_template.json"
    write_json(analysis_path, final_job)
    write_json(
        labels_path,
        build_label_template(
            analysis=final_job,
            case_id=case_id,
            video_id=video_id,
            team_mode=args.team_mode,
            selected_team_id=selected_team.get("teamId") if selected_team else None,
            selected_team_color_label=selected_team.get("colorLabel") if selected_team else None,
            confidence_threshold=args.confidence_threshold,
        ),
    )

    manifest_path = None
    if not args.no_manifest:
        manifest_path = Path(args.manifest).expanduser().resolve()
        upsert_manifest_case(
            manifest_path,
            {
                "caseId": case_id,
                "videoId": video_id,
                "teamMode": args.team_mode,
                "analysisResult": relative_to_manifest(analysis_path, manifest_path),
                "labels": relative_to_manifest(labels_path, manifest_path),
                "selectedTeamId": selected_team.get("teamId") if selected_team else None,
                "confidenceThreshold": args.confidence_threshold,
            },
        )

    results = final_job.get("results") if isinstance(final_job.get("results"), dict) else {}
    clips = results.get("clips") if isinstance(results.get("clips"), list) else []
    return {
        "status": "pass",
        "workerUrl": args.worker_url,
        "caseId": case_id,
        "videoId": video_id,
        "jobId": job_id,
        "teamMode": args.team_mode,
        "analysisStartStatus": start.get("status"),
        "finalJobStatus": final_job.get("status"),
        "detectedTeamCount": len(detected_teams),
        "selectedTeamId": selected_team.get("teamId") if selected_team else None,
        "selectedColorLabel": selected_team.get("colorLabel") if selected_team else None,
        "clipCount": len(clips),
        "analysisResultPath": str(analysis_path),
        "manualLabelsTemplatePath": str(labels_path),
        "manifestPath": str(manifest_path) if manifest_path else None,
    }


def build_create_payload(args: argparse.Namespace, video_path: Path) -> dict[str, Any]:
    return {
        "filename": video_path.name,
        "contentType": "video/mp4",
        "fileSizeBytes": video_path.stat().st_size,
        "durationSeconds": args.duration_seconds,
        "installId": args.install_id,
        "appVersion": args.app_version,
        "analysisVersion": args.analysis_version,
    }


def team_selection_payload(args: argparse.Namespace, selected_team: dict[str, Any] | None) -> dict[str, Any]:
    if args.team_mode == "all":
        return {"mode": "all"}
    if selected_team is None:
        raise ValueError("Selected-team mode requires a selected team.")
    return {
        "mode": "team",
        "teamId": selected_team.get("teamId"),
        "label": selected_team.get("label"),
        "colorLabel": selected_team.get("colorLabel"),
        "confidenceThreshold": args.confidence_threshold,
        "includeUncertain": True,
    }


def poll_job(base_url: str, job_id: str, trace_id: str, timeout_seconds: float, poll_interval_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_job: dict[str, Any] | None = None
    while time.monotonic() <= deadline:
        job = request_json("GET", base_url, f"v1/analysis/jobs/{job_id}", trace_id=trace_id)
        last_job = job
        status = str(job.get("status") or "").lower()
        if status in TERMINAL_STATUSES:
            return job
        time.sleep(poll_interval_seconds)
    raise SmokeError("Timed out waiting for cloud analysis.", {"jobId": job_id, "lastJob": last_job})


def upsert_manifest_case(manifest_path: Path, case_entry: dict[str, Any]) -> None:
    if manifest_path.exists():
        existing = load_manifest(manifest_path)
    else:
        existing = {"schemaVersion": "team-highlight-accuracy-manifest-v1", "cases": []}

    cases = existing.setdefault("cases", [])
    if not isinstance(cases, list):
        raise ValueError("Manifest cases must be an array.")
    cases[:] = [case for case in cases if not (isinstance(case, dict) and case.get("caseId") == case_entry.get("caseId"))]
    cases.append(case_entry)
    write_json(manifest_path, existing)


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Manifest must contain a JSON object.")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SmokeError(f"Response missing {key}.", {"response": payload})
    return value


def relative_to_manifest(path: Path, manifest_path: Path) -> str:
    try:
        return str(path.relative_to(manifest_path.parent))
    except ValueError:
        return str(path)


def default_case_id(video_path: Path) -> str:
    return f"{safe_path_segment(video_path.stem)}_{int(time.time())}"


def safe_path_segment(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._") or "case"


if __name__ == "__main__":
    raise SystemExit(main())

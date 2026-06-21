#!/usr/bin/env python3
"""Create a fill-in-safe HoopClips background upload phone proof template."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a sanitized fill-in template for real-device background upload proof."
    )
    parser.add_argument("--out", help="Write the template to this path. Defaults to stdout.")
    parser.add_argument("--commit", default="", help="Git commit expected in the tested build.")
    parser.add_argument("--build", default="", help="TestFlight build number.")
    parser.add_argument("--app-version", default="", help="App version shown by the build.")
    parser.add_argument("--device", default="", help="Device model used for the proof.")
    parser.add_argument("--ios-version", default="", help="iOS version used for the proof.")
    parser.add_argument(
        "--label",
        default="real-device-background-upload",
        help="Short label for the proof run.",
    )
    return parser.parse_args()


def value_or_placeholder(value: str, placeholder: str) -> str:
    return value if value else placeholder


def build_template(args: argparse.Namespace) -> str:
    created_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return f"""# HoopClips background upload phone proof
# Fill only these fields. Do not paste URLs, local file paths, raw upload IDs,
# raw job IDs, R2 object keys, presigned fragments, or upload headers.

label: {args.label}
createdAt: {created_at}

appVersion: {value_or_placeholder(args.app_version, "<app-version>")}
buildVersion: {value_or_placeholder(args.build, "<testflight-build>")}
gitCommit: {value_or_placeholder(args.commit, "<git-sha>")}
deviceModel: {value_or_placeholder(args.device, "<device-model>")}
iOSVersion: {value_or_placeholder(args.ios_version, "<ios-version>")}
sourceVideoLength: <duration-or-unknown>
sourceVideoApproxSize: <size-or-unknown>

# Before switching apps while upload is active.
beforeSwitch.pipelineStage: Uploading
beforeSwitch.uploadProgress: <0.00-1.00>
beforeSwitch.nextAction: <wait_for_background_session|resume_upload|start_cloud_analysis|run_team_scan|missing>
beforeSwitch.uploadComplete: false
beforeSwitch.activeUploadSessions: true

# After returning to HoopClips.
pipelineStage: <Uploading|Analyzing|Review ready>
uploadProgress: <0.00-1.00>
nextAction: <wait_for_background_session|resume_upload|start_cloud_analysis|run_team_scan|missing>
uploadComplete: <true|false>
activeUploadSessions: <true|false>
staleWithoutActiveSession: <true|false>

# Set at least one app-switch evidence flag to true if observed.
backgroundedDuringUpload: true
completedWhileAway: <true|false>
wakeReceived: <true|false>
relaunchCompletion: <true|false>
inferredSourceCompletion: <true|false>

# Final continuation state.
analysisStatus: <Preparing|Uploading|Analyzing|Review ready|unknown>
reviewReady: <true|false>
privacyNote: No secrets, presigned URLs, object keys, upload IDs, job IDs, upload headers, or local file paths are included.
"""


def main() -> int:
    args = parse_args()
    template = build_template(args)
    if args.out:
        Path(args.out).write_text(template, encoding="utf-8")
    else:
        print(template, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

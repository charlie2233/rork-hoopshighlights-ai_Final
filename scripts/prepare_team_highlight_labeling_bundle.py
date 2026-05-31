#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.build_launch_team_accuracy_report import build_label_status, load_json
from scripts.build_team_highlight_label_review_page import (
    build_review_payload,
    parse_video_angle_paths,
    parse_video_angle_urls,
    parse_video_paths,
    parse_video_urls,
    render_review_page,
    review_page_output_metadata,
)


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_json(manifest_path)
    draft_bundle = load_json(Path(args.draft_bundle).expanduser().resolve()) if args.draft_bundle else None
    default_video_path = Path(args.video_path).expanduser().resolve() if args.video_path else None
    payload = build_review_payload(
        manifest=manifest,
        manifest_dir=manifest_path.parent,
        video_paths=parse_video_paths(args.video or []),
        video_urls=parse_video_urls(args.video_url or []),
        video_angle_paths=parse_video_angle_paths(args.video_angle or []),
        video_angle_urls=parse_video_angle_urls(args.video_url_angle or []),
        default_video_path=default_video_path,
        draft_bundle=draft_bundle,
    )

    review_page_path = output_dir / "team_highlight_label_review.html"
    review_page_path.write_text(render_review_page(payload, title=args.title), encoding="utf-8")

    status_payload = build_label_status(manifest=manifest, manifest_dir=manifest_path.parent)
    status_path = output_dir / "label_status.json"
    write_json(status_path, status_payload)

    metadata = {
        "schemaVersion": "team-highlight-labeling-bundle-v1",
        "manifest": str(manifest_path),
        "outputDir": str(output_dir),
        "reviewPage": str(review_page_path),
        "labelStatus": str(status_path),
        "status": status_payload["status"],
        "caseCount": status_payload["caseCount"],
        "clipCount": status_payload["clipCount"],
        "completeClipCount": status_payload["completeClipCount"],
        "incompleteClipCount": status_payload["incompleteClipCount"],
        "reviewPageMetadata": review_page_output_metadata(review_page_path, payload),
    }
    metadata_path = output_dir / "bundle_metadata.json"
    write_json(metadata_path, metadata)

    next_steps_path = output_dir / "next_steps.md"
    next_steps_path.write_text(next_steps_markdown(metadata, args), encoding="utf-8")

    if args.json:
        print(json.dumps(metadata, indent=2, sort_keys=True))
    else:
        print(f"review_page={review_page_path}")
        print(f"label_status={status_path}")
        print(f"next_steps={next_steps_path}")
        print(f"status={metadata['status']}")
        print(f"clips={metadata['completeClipCount']} complete / {metadata['clipCount']} total")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a local HoopClips team/highlight labeling bundle from an existing accuracy manifest. "
            "This creates a review HTML page, progress JSON, and command handoff. It does not analyze, "
            "render, export, upload, or modify videos."
        )
    )
    parser.add_argument("--manifest", required=True, help="Team-highlight accuracy manifest JSON.")
    parser.add_argument("--output-dir", default="artifacts/team_highlight_labeling_bundle")
    parser.add_argument("--video-path", help="Default local source video path for every case in the manifest.")
    parser.add_argument("--video", action="append", help="Map video id to local file as videoId=/absolute/path.mp4.")
    parser.add_argument(
        "--video-url",
        action="append",
        help="Map video id to local browser URL as videoId=http://127.0.0.1:8787/source.mp4.",
    )
    parser.add_argument(
        "--video-angle",
        action="append",
        help="Add local angle as videoId:angleName=/absolute/path.mp4. Repeat for multi-angle labeling.",
    )
    parser.add_argument(
        "--video-url-angle",
        action="append",
        help="Add local browser angle as videoId:angleName=http://127.0.0.1:8787/angle.mp4.",
    )
    parser.add_argument("--draft-bundle", help="Optional GPT draft bundle to prefill labels for human review.")
    parser.add_argument("--title", default="HoopClips Team Highlight Label Review")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def next_steps_markdown(metadata: dict[str, Any], args: argparse.Namespace) -> str:
    report_path = Path(metadata["outputDir"]) / "team_highlight_accuracy_report.json"
    eval_path = Path(metadata["outputDir"]) / "team_highlight_eval.json"
    manifest = metadata["manifest"]
    return "\n".join(
        [
            "# HoopClips Team Highlight Labeling Bundle",
            "",
            "## Files",
            "",
            f"- Review page: `{metadata['reviewPage']}`",
            f"- Label status: `{metadata['labelStatus']}`",
            f"- Manifest: `{manifest}`",
            "",
            "## Labeling Flow",
            "",
            "1. Open the review page in a browser.",
            "2. Use `Start`, `Event`, and `Finish` to jump every provided angle to the same clip time.",
            "3. Fill expected team, highlight yes/no, event, and outcome for every clip.",
            "4. Use `Mark reviewed + next` until the page enables `Download launch-ready labels`.",
            "5. Apply the downloaded `team_highlight_manual_labels_bundle.json`, then build the launch report.",
            "",
            "## Commands After Review",
            "",
            "```bash",
            "python3 scripts/apply_team_highlight_manual_labels.py \\",
            f"  --manifest {shell_quote(manifest)} \\",
            "  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \\",
            "  --apply \\",
            "  --json",
            "",
            "python3 scripts/build_launch_team_accuracy_report.py \\",
            f"  --manifest {shell_quote(manifest)} \\",
            f"  --eval-output {shell_quote(str(eval_path))} \\",
            f"  --report-output {shell_quote(str(report_path))} \\",
            "  --json",
            "",
            "python3 scripts/submission_readiness_preflight.py \\",
            f"  --team-accuracy-report {shell_quote(str(report_path))}",
            "```",
            "",
            "## Guardrails",
            "",
            "- The review page uses local playback and cloud metadata only.",
            "- It does not call GPT, analyze video, render video, export video, or upload video.",
            "- Do not paste secrets, R2 credentials, or presigned URLs into label files.",
            "- GPT draft labels, if imported, still require human review before launch evidence can count.",
            "",
        ]
    )


def shell_quote(value: str) -> str:
    if not value:
        return "''"
    if all(ch.isalnum() or ch in "/._:-" for ch in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)

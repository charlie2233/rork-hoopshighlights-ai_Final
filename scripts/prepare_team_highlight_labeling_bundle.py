#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts import draft_team_highlight_manual_labels_with_gpt as gpt_draft
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
    video_paths = parse_video_paths(args.video or [])
    default_video_path = Path(args.video_path).expanduser().resolve() if args.video_path else None
    draft_bundle, draft_metadata = resolve_draft_bundle(
        args=args,
        manifest=manifest,
        manifest_path=manifest_path,
        output_dir=output_dir,
        video_paths=video_paths,
        default_video_path=default_video_path,
    )
    payload = build_review_payload(
        manifest=manifest,
        manifest_dir=manifest_path.parent,
        video_paths=video_paths,
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
    if draft_metadata:
        metadata["gptDraft"] = draft_metadata
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
    parser.add_argument(
        "--draft-with-gpt",
        action="store_true",
        help=(
            "Generate a GPT vision draft bundle from sampled keyframes and prefill the review page. "
            "Requires HOOPS_OPENAI_API_KEY or OPENAI_API_KEY unless --draft-mock-response is used."
        ),
    )
    parser.add_argument("--draft-output", help="Where to write the generated GPT draft bundle.")
    parser.add_argument("--draft-context-output", help="Optional redacted GPT draft context JSON for audit/debug.")
    parser.add_argument("--draft-mock-response", help="Use a saved OpenAI/structured response JSON instead of calling GPT.")
    parser.add_argument("--draft-case", action="append", help="Optional caseId filter for GPT drafting. Repeat for subsets.")
    parser.add_argument("--draft-model", default=gpt_draft.default_model(), help="OpenAI vision-capable model for GPT draft labels.")
    parser.add_argument("--draft-endpoint", default=os.getenv("HOOPS_OPENAI_RESPONSES_ENDPOINT", "https://api.openai.com/v1/responses"))
    parser.add_argument("--draft-timeout-seconds", type=float, default=float(os.getenv("HOOPS_TEAM_LABEL_DRAFT_TIMEOUT_SECONDS", "90")))
    parser.add_argument("--draft-frames-per-clip", type=int, default=int(os.getenv("HOOPS_TEAM_LABEL_DRAFT_FRAMES_PER_CLIP", "5")))
    parser.add_argument("--draft-frame-width", type=int, default=int(os.getenv("HOOPS_TEAM_LABEL_DRAFT_FRAME_WIDTH", "768")))
    parser.add_argument("--draft-jpeg-quality", type=int, default=int(os.getenv("HOOPS_TEAM_LABEL_DRAFT_JPEG_QUALITY", "5")))
    parser.add_argument("--title", default="HoopClips Team Highlight Label Review")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.draft_bundle and args.draft_with_gpt:
        parser.error("Use either --draft-bundle or --draft-with-gpt, not both.")
    return args


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_draft_bundle(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    manifest_path: Path,
    output_dir: Path,
    video_paths: dict[str, Path],
    default_video_path: Path | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if args.draft_bundle:
        draft_path = Path(args.draft_bundle).expanduser().resolve()
        return load_json(draft_path), {"source": "existing_bundle", "path": str(draft_path)}
    if not args.draft_with_gpt:
        return None, None

    draft_output_path = Path(args.draft_output).expanduser().resolve() if args.draft_output else output_dir / "gpt_draft_labels.json"
    request_payload = gpt_draft.build_openai_draft_request(
        manifest=manifest,
        manifest_dir=manifest_path.parent,
        video_paths=video_paths,
        default_video_path=default_video_path,
        model=args.draft_model or gpt_draft.default_model(),
        frames_per_clip=gpt_draft.clamp_int(args.draft_frames_per_clip, 3, 8),
        frame_width=gpt_draft.clamp_int(args.draft_frame_width, 256, 1280),
        jpeg_quality=gpt_draft.clamp_int(args.draft_jpeg_quality, 2, 12),
        case_filter=set(args.draft_case or []),
    )
    if args.draft_context_output:
        write_json(Path(args.draft_context_output).expanduser().resolve(), gpt_draft.scrub_images_for_context_output(request_payload))

    if args.draft_mock_response:
        response_payload = load_json(Path(args.draft_mock_response).expanduser().resolve())
    else:
        api_key = os.getenv("HOOPS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Set HOOPS_OPENAI_API_KEY or OPENAI_API_KEY to use --draft-with-gpt.")
        response_payload = gpt_draft.call_openai_responses(
            request_payload,
            api_key=api_key,
            endpoint=args.draft_endpoint,
            timeout_seconds=args.draft_timeout_seconds,
        )

    decisions = gpt_draft.parse_decisions_response(response_payload)
    draft_bundle = gpt_draft.build_draft_bundle(request_payload["metadata"]["labelCases"], decisions)
    write_json(draft_output_path, draft_bundle)
    return draft_bundle, {
        "source": "gpt_draft_requires_human_review",
        "path": str(draft_output_path),
        "model": request_payload["model"],
        "caseCount": len(draft_bundle["cases"]),
        "clipCount": sum(len(case.get("clips", [])) for case in draft_bundle["cases"]),
        "humanReviewRequired": True,
    }


def next_steps_markdown(metadata: dict[str, Any], args: argparse.Namespace) -> str:
    report_path = Path(metadata["outputDir"]) / "team_highlight_accuracy_report.json"
    eval_path = Path(metadata["outputDir"]) / "team_highlight_eval.json"
    manifest = metadata["manifest"]
    draft_steps: list[str] = []
    if isinstance(metadata.get("gptDraft"), dict):
        draft = metadata["gptDraft"]
        draft_steps = [
            "",
            "## GPT Draft",
            "",
            f"- Draft bundle: `{draft.get('path')}`",
            f"- Model: `{draft.get('model', 'provided bundle')}`",
            "- The draft is prefilled for speed, but every clip still needs human review before launch evidence counts.",
        ]
    return "\n".join(
        [
            "# HoopClips Team Highlight Labeling Bundle",
            "",
            "## Files",
            "",
            f"- Review page: `{metadata['reviewPage']}`",
            f"- Label status: `{metadata['labelStatus']}`",
            f"- Manifest: `{manifest}`",
            *draft_steps,
            "",
            "## Labeling Flow",
            "",
            "1. Open the review page in a browser.",
            "2. Use `Next close review` first. These clips have uncertainty or weak evidence and should get the most careful watch.",
            "3. Use `Next incomplete` after close-review clips are done, then finish standard and quick-check clips.",
            "4. Quick-check clips are faster, but they still require watching the video before marking reviewed.",
            "5. Use keyboard playback while the clip card is active: `S/E/F` jump start/event/finish, `J/L` scrub back/forward 0.5s, `K` play/pause synced angles.",
            "6. Use `P` to copy the HoopClips/GPT draft into the fields, then verify the video before accepting it.",
            "7. For obvious clips, use `1` selected-team highlight, `2` not highlight, or `3` bad window after watching the clip.",
            "8. Use `Download progress checkpoint` any time you want to save a partial session outside browser storage.",
            "9. Use `R` or `Mark reviewed + next` until the page enables `Download launch-ready labels`.",
            "10. Apply the downloaded `team_highlight_manual_labels_bundle.json`, then build the launch report.",
            "",
            "The page auto-saves a local browser draft as you label. Still download a progress checkpoint before pausing and the launch-ready bundle before final reporting.",
            "",
            "## Commands To Save Partial Progress",
            "",
            "Use this only for a partial checkpoint. It is not launch evidence until every clip is complete and the final bundle is applied without `--allow-incomplete`.",
            "",
            "```bash",
            "PROGRESS_BUNDLE=\"$HOME/Downloads/team_highlight_manual_labels_progress_YYYY-MM-DDTHH-MM-SS.json\"",
            "",
            "python3 scripts/apply_team_highlight_manual_labels.py \\",
            f"  --manifest {shell_quote(manifest)} \\",
            "  --bundle \"$PROGRESS_BUNDLE\" \\",
            "  --allow-incomplete \\",
            "  --apply \\",
            "  --json",
            "```",
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
            "- It only calls GPT when `--draft-with-gpt` is explicitly used, and then sends sampled keyframes plus compact clip metadata only.",
            "- It does not run product analysis, render video, export video, or upload video.",
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

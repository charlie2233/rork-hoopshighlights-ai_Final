#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.build_launch_team_accuracy_report import manifest_case_entry
from scripts.build_team_highlight_eval_payload import extract_analysis_result, load_json, number_or_none, string_or_none


FORBIDDEN_REVIEW_KEYS = {
    "downloadUrl",
    "presignedUrl",
    "resultObjectKey",
    "sourceObjectKey",
    "sourceUrl",
    "uploadHeaders",
    "uploadUrl",
}

EVENT_TYPE_OPTIONS = [
    ("", "Choose event"),
    ("made_shot", "Made shot"),
    ("missed_shot", "Missed shot"),
    ("three_pointer", "Three pointer"),
    ("layup", "Layup / finish"),
    ("dunk", "Dunk"),
    ("fast_break", "Fast break"),
    ("block", "Block"),
    ("steal", "Steal"),
    ("forced_turnover", "Forced turnover"),
    ("defensive_stop", "Defensive stop"),
    ("rebound", "Rebound"),
    ("assist", "Assist"),
    ("boring", "Boring / not highlight"),
    ("bad_window", "Bad timing window"),
    ("not_basketball", "Not basketball"),
    ("unclear", "Unclear"),
]

OUTCOME_OPTIONS = [
    ("", "Choose outcome"),
    ("made", "Made"),
    ("missed", "Missed"),
    ("blocked", "Blocked"),
    ("steal", "Steal"),
    ("forced_turnover", "Forced turnover"),
    ("defensive_stop", "Defensive stop"),
    ("not_shot", "Not a shot"),
    ("not_highlight", "Not a highlight"),
    ("bad_window", "Bad window"),
    ("not_basketball", "Not basketball"),
    ("unclear", "Unclear"),
]


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    video_paths = parse_video_paths(args.video or [])
    default_video_path = Path(args.video_path).resolve() if args.video_path else None
    draft_bundle = load_json(Path(args.draft_bundle).expanduser().resolve()) if args.draft_bundle else None
    payload = build_review_payload(
        manifest=load_json(manifest_path),
        manifest_dir=manifest_path.parent,
        video_paths=video_paths,
        default_video_path=default_video_path,
        draft_bundle=draft_bundle,
    )
    html_output = render_review_page(payload, title=args.title)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_output, encoding="utf-8")
    if args.json:
        print(json.dumps({"output": str(output_path), "caseCount": len(payload["cases"])}, indent=2, sort_keys=True))
    else:
        print(f"wrote {output_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a local manual-review HTML page for HoopClips team/highlight labels. "
            "The page uses existing cloud analysis metadata and source video seek controls only; "
            "it does not analyze, render, export, or upload video."
        )
    )
    parser.add_argument("--manifest", required=True, help="Team-highlight accuracy manifest JSON.")
    parser.add_argument("--output", required=True, help="Write the local HTML review page here.")
    parser.add_argument("--video-path", help="Default local source video path for every case in the manifest.")
    parser.add_argument(
        "--draft-bundle",
        help=(
            "Optional GPT draft team_highlight_manual_labels_bundle.json to prefill expected labels. "
            "Rows with humanReviewRequired remain unreviewed."
        ),
    )
    parser.add_argument(
        "--video",
        action="append",
        help="Map one video id to a local file path as videoId=/absolute/path.mp4. Repeat for multiple videos.",
    )
    parser.add_argument("--title", default="HoopClips Team Highlight Label Review", help="HTML page title.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output metadata.")
    return parser.parse_args()


def parse_video_paths(values: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--video must use videoId=/absolute/path.mp4")
        video_id, raw_path = value.split("=", 1)
        video_id = video_id.strip()
        if not video_id:
            raise ValueError("--video is missing a video id.")
        mapping[video_id] = Path(raw_path).expanduser().resolve()
    return mapping


def build_review_payload(
    *,
    manifest: dict[str, Any],
    manifest_dir: Path,
    video_paths: dict[str, Path],
    default_video_path: Path | None,
    draft_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entries = manifest.get("cases")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a non-empty cases array.")

    cases: list[dict[str, Any]] = []
    videos: dict[str, str] = {}
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Manifest case {index} must be an object.")
        entry = manifest_case_entry(raw_entry, index, manifest_dir)
        analysis = load_json(entry.analysis_path)
        labels = sanitize_for_review(load_json(entry.labels_path))
        result = extract_analysis_result(analysis)
        video_id = (
            string_or_none(raw_entry.get("videoId"))
            or string_or_none(labels.get("videoId"))
            or string_or_none(result.get("videoId"))
            or f"case_{index + 1}"
        )
        video_path = video_paths.get(video_id) or default_video_path
        if video_path is None:
            raise ValueError(f"Missing source video path for videoId {video_id!r}. Use --video-path or --video {video_id}=...")
        videos[video_id] = video_path.as_uri()
        case_payload = review_case_payload(
            raw_entry=raw_entry,
            labels=labels,
            analysis_result=result,
            case_index=index,
            labels_path=entry.labels_path,
            video_id=video_id,
        )
        cases.append(case_payload)

    payload = {
        "schemaVersion": "team-highlight-label-review-page-v1",
        "source": "real_cloud_analysis_manual_review_helper",
        "videos": videos,
        "cases": cases,
    }
    if draft_bundle is not None:
        payload["draftPrefill"] = apply_draft_bundle_to_review_payload(payload, draft_bundle)
    return payload


def review_case_payload(
    *,
    raw_entry: dict[str, Any],
    labels: dict[str, Any],
    analysis_result: dict[str, Any],
    case_index: int,
    labels_path: Path,
    video_id: str,
) -> dict[str, Any]:
    clips = labels.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError(f"Label file for case {case_index} must contain a non-empty clips array.")
    case_id = string_or_none(raw_entry.get("caseId") or labels.get("caseId")) or f"case_{case_index + 1}"
    team_mode = string_or_none(raw_entry.get("teamMode") or labels.get("teamMode")) or "all"
    selected_team_id = string_or_none(raw_entry.get("selectedTeamId") or labels.get("selectedTeamId"))
    selected_team_color_label = string_or_none(raw_entry.get("selectedTeamColorLabel") or labels.get("selectedTeamColorLabel"))
    detected_teams = labels.get("detectedTeams") if isinstance(labels.get("detectedTeams"), list) else analysis_result.get("detectedTeams", [])
    labels["caseId"] = case_id
    labels["videoId"] = video_id
    return {
        "caseId": case_id,
        "videoId": video_id,
        "teamMode": team_mode,
        "selectedTeamId": selected_team_id,
        "selectedTeamColorLabel": selected_team_color_label,
        "detectedTeams": sanitize_for_review(detected_teams),
        "labelsPath": str(labels_path),
        "labelsPayload": labels,
        "clips": [review_clip_payload(index, clip) for index, clip in enumerate(clips) if isinstance(clip, dict)],
    }


def review_clip_payload(index: int, clip: dict[str, Any]) -> dict[str, Any]:
    predicted = clip.get("predicted") if isinstance(clip.get("predicted"), dict) else {}
    expected = clip.get("expected") if isinstance(clip.get("expected"), dict) else {}
    start = number_or_none(clip.get("start"))
    end = number_or_none(clip.get("end"))
    event_center = number_or_none(predicted.get("eventCenter"))
    if event_center is None and start is not None and end is not None:
        event_center = round((start + end) / 2.0, 3)
    return {
        "index": index,
        "labelId": string_or_none(clip.get("labelId")) or f"label_{index:03d}",
        "predictionClipId": string_or_none(clip.get("predictionClipId")) or string_or_none(clip.get("clipId")),
        "start": start,
        "end": end,
        "eventCenter": event_center,
        "needsLabel": clip.get("needsLabel") is not False,
        "predicted": sanitize_for_review(predicted),
        "expected": sanitize_for_review(expected),
        "labelingNotes": string_or_none(clip.get("labelingNotes")) or "",
    }


def apply_draft_bundle_to_review_payload(payload: dict[str, Any], draft_bundle: dict[str, Any]) -> dict[str, Any]:
    if draft_bundle.get("schemaVersion") != "team-highlight-manual-label-bundle-v1":
        raise ValueError("Draft bundle must use schemaVersion team-highlight-manual-label-bundle-v1.")
    draft_cases = draft_bundle.get("cases")
    if not isinstance(draft_cases, list) or not draft_cases:
        raise ValueError("Draft bundle must contain a non-empty cases array.")

    human_review_required = draft_bundle.get("humanReviewRequired") is True or "draft" in str(draft_bundle.get("source") or "")
    by_case_id: dict[str, dict[str, Any]] = {}
    for index, draft_case in enumerate(draft_cases):
        if not isinstance(draft_case, dict):
            raise ValueError(f"Draft bundle case {index} must be an object.")
        case_id = string_or_none(draft_case.get("caseId"))
        if not case_id:
            raise ValueError(f"Draft bundle case {index} is missing caseId.")
        if case_id in by_case_id:
            raise ValueError(f"Draft bundle contains duplicate caseId {case_id!r}.")
        by_case_id[case_id] = draft_case

    applied = 0
    skipped = 0
    for review_case in payload.get("cases", []):
        if not isinstance(review_case, dict):
            continue
        case_id = string_or_none(review_case.get("caseId") or review_case.get("labelsPayload", {}).get("caseId"))
        draft_case = by_case_id.get(case_id or "")
        if not draft_case:
            skipped += len([clip for clip in review_case.get("clips", []) if isinstance(clip, dict)])
            continue
        draft_clips = [clip for clip in draft_case.get("clips", []) if isinstance(clip, dict)]
        label_clips = [clip for clip in review_case.get("labelsPayload", {}).get("clips", []) if isinstance(clip, dict)]
        review_clips = [clip for clip in review_case.get("clips", []) if isinstance(clip, dict)]
        for draft_clip in draft_clips:
            clip_index = find_matching_draft_clip_index(label_clips, draft_clip)
            if clip_index < 0 or clip_index >= len(review_clips):
                skipped += 1
                continue
            prefill_clip_from_draft(label_clips[clip_index], draft_clip, human_review_required=human_review_required)
            prefill_clip_from_draft(review_clips[clip_index], draft_clip, human_review_required=human_review_required)
            applied += 1
    return {
        "schemaVersion": "team-highlight-label-review-draft-prefill-v1",
        "source": "draft_bundle",
        "appliedClipCount": applied,
        "skippedClipCount": skipped,
        "humanReviewRequired": human_review_required,
    }


def find_matching_draft_clip_index(current_clips: list[dict[str, Any]], draft_clip: dict[str, Any]) -> int:
    draft_label_id = string_or_none(draft_clip.get("labelId"))
    draft_prediction_clip_id = string_or_none(draft_clip.get("predictionClipId") or draft_clip.get("clipId"))
    for index, current_clip in enumerate(current_clips):
        current_label_id = string_or_none(current_clip.get("labelId"))
        current_prediction_clip_id = string_or_none(current_clip.get("predictionClipId") or current_clip.get("clipId"))
        label_matches = draft_label_id and current_label_id == draft_label_id
        prediction_matches = draft_prediction_clip_id and current_prediction_clip_id == draft_prediction_clip_id
        if label_matches or prediction_matches:
            return index
    return -1


def prefill_clip_from_draft(target_clip: dict[str, Any], draft_clip: dict[str, Any], *, human_review_required: bool) -> None:
    expected = draft_clip.get("expected") if isinstance(draft_clip.get("expected"), dict) else {}
    target_clip["expected"] = sanitize_for_review(expected)
    target_clip["labelingNotes"] = string_or_none(draft_clip.get("labelingNotes")) or string_or_none(target_clip.get("labelingNotes")) or ""
    target_clip["needsLabel"] = True if human_review_required else draft_clip.get("needsLabel") is not False


def sanitize_for_review(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): sanitize_for_review(item)
            for key, item in value.items()
            if str(key) not in FORBIDDEN_REVIEW_KEYS and not str(key).lower().endswith("url")
        }
    if isinstance(value, list):
        return [sanitize_for_review(item) for item in value]
    return value


def render_review_page(payload: dict[str, Any], *, title: str) -> str:
    data_json = json.dumps(payload, sort_keys=True).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    body = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(title)}</title>",
        "<style>",
        CSS,
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{escape(title)}</h1>",
        '<p class="lede">Review the original source video, jump to each cloud-selected clip window, and fill the labels needed for the 85% team-highlight gate.</p>',
        render_progress_summary(payload),
        render_video_sections(payload),
        render_case_sections(payload),
        f'<script id="review-data" type="application/json">{data_json}</script>',
        "<script>",
        JS,
        "</script>",
        "</body>",
        "</html>",
    ]
    return "\n".join(body) + "\n"


def render_progress_summary(payload: dict[str, Any]) -> str:
    total = 0
    remaining = 0
    for case in payload.get("cases", []):
        if not isinstance(case, dict):
            continue
        clips = [clip for clip in case.get("clips", []) if isinstance(clip, dict)]
        total += len(clips)
        remaining += sum(1 for clip in clips if clip.get("needsLabel") is not False)
    reviewed = total - remaining
    draft_prefill = payload.get("draftPrefill") if isinstance(payload.get("draftPrefill"), dict) else None
    draft_line = ""
    if draft_prefill:
        applied = int(draft_prefill.get("appliedClipCount") or 0)
        skipped = int(draft_prefill.get("skippedClipCount") or 0)
        review_copy = "Human review is still required." if draft_prefill.get("humanReviewRequired") else "Downloaded labels may already include reviewed rows."
        draft_line = (
            f'<p class="lede">GPT draft prefilled {applied} clips'
            f'{f"; skipped {skipped}" if skipped else ""}. {escape(review_copy)}</p>'
        )
    return "\n".join(
        [
            '<section class="panel summary-panel">',
            '<div class="case-heading">',
            "<div>",
            "<h2>Label Progress</h2>",
            f'<p id="overall-progress"><strong>{reviewed}</strong> / {total} clips reviewed. {remaining} still need labels.</p>',
            '<p class="lede">A clip is complete when it is marked reviewed and has expected team, highlight, event, and outcome fields filled.</p>',
            draft_line,
            '<p class="lede" id="draft-status">Local draft not loaded.</p>',
            "</div>",
            '<div class="button-row">',
            '<button type="button" onclick="focusNextIncomplete()">Next incomplete</button>',
            '<button type="button" onclick="downloadAllCaseLabels()">Download all labels</button>',
            '<label class="file-button">Import draft bundle<input id="bundle-import" type="file" accept="application/json" onchange="importDraftBundle(event)"></label>',
            '<button type="button" onclick="clearSavedDraft()">Clear saved draft</button>',
            "</div>",
            "</div>",
            "</section>",
        ]
    )


def render_video_sections(payload: dict[str, Any]) -> str:
    sections: list[str] = []
    videos = payload.get("videos", {})
    if not isinstance(videos, dict):
        return ""
    for video_id, url in videos.items():
        element_id = video_element_id(str(video_id))
        sections.append(
            "\n".join(
                [
                    '<section class="panel video-panel">',
                    f"<h2>Source Video: {escape(str(video_id))}</h2>",
                    f'<video id="{escape(element_id)}" controls preload="metadata" src="{escape(str(url))}"></video>',
                    "</section>",
                ]
            )
        )
    return "\n".join(sections)


def render_case_sections(payload: dict[str, Any]) -> str:
    sections: list[str] = []
    for case_index, case in enumerate(payload.get("cases", [])):
        if not isinstance(case, dict):
            continue
        clips_html = "\n".join(render_clip_card(case_index, case, clip) for clip in case.get("clips", []) if isinstance(clip, dict))
        selected = case.get("selectedTeamId") or "all teams"
        color = case.get("selectedTeamColorLabel") or "any color"
        teams = ", ".join(team_label(team) for team in case.get("detectedTeams", []) if isinstance(team, dict)) or "none"
        case_total = sum(1 for clip in case.get("clips", []) if isinstance(clip, dict))
        case_remaining = sum(1 for clip in case.get("clips", []) if isinstance(clip, dict) and clip.get("needsLabel") is not False)
        case_reviewed = case_total - case_remaining
        sections.append(
            "\n".join(
                [
                    f'<section class="panel case-panel" data-case-index="{case_index}">',
                    '<div class="case-heading">',
                    "<div>",
                    f"<h2>{escape(str(case.get('caseId') or f'case_{case_index + 1}'))}</h2>",
                    f'<p>Mode: <strong>{escape(str(case.get("teamMode") or "all"))}</strong> | Target: <strong>{escape(str(selected))}</strong> | Color: <strong>{escape(str(color))}</strong></p>',
                    f"<p>Detected teams: {escape(teams)}</p>",
                    f'<p class="label-progress" id="case-progress-{case_index}">{case_reviewed} / {case_total} clips reviewed. {case_remaining} remaining.</p>',
                    f'<p class="path">Labels file: {escape(str(case.get("labelsPath") or ""))}</p>',
                    "</div>",
                    f'<button type="button" onclick="downloadCaseLabels({case_index})">Download filled labels</button>',
                    "</div>",
                    '<div class="clip-grid">',
                    clips_html,
                    "</div>",
                    "</section>",
                ]
            )
        )
    return "\n".join(sections)


def render_clip_card(case_index: int, case: dict[str, Any], clip: dict[str, Any]) -> str:
    clip_index = int(clip.get("index") or 0)
    predicted = clip.get("predicted") if isinstance(clip.get("predicted"), dict) else {}
    expected = clip.get("expected") if isinstance(clip.get("expected"), dict) else {}
    label = predicted.get("label") or "Clip"
    start = seconds_or_empty(clip.get("start"))
    event = seconds_or_empty(clip.get("eventCenter"))
    finish = seconds_or_empty(clip.get("end"))
    expected_team = string_or_none(expected.get("teamId")) or ""
    expected_event = string_or_none(expected.get("eventType")) or ""
    expected_outcome = string_or_none(expected.get("outcome")) or ""
    is_highlight = expected.get("isHighlight")
    reviewed = "checked" if clip.get("needsLabel") is False else ""
    complete_class = " complete" if clip.get("needsLabel") is False else ""
    return "\n".join(
        [
            f'<article class="clip-card{complete_class}" data-case-index="{case_index}" data-clip-index="{clip_index}" tabindex="-1">',
            f"<h3>#{clip_index + 1} {escape(str(label))}</h3>",
            f'<p class="clip-meta">{escape(str(clip.get("predictionClipId") or clip.get("labelId") or ""))} | {start}s to {finish}s</p>',
            f'<p>Predicted team: <strong>{escape(str(predicted.get("teamId") or "unknown"))}</strong> ({escape(format_number(predicted.get("teamConfidence")))}) | Status: {escape(str(predicted.get("teamAttributionStatus") or "unknown"))}</p>',
            f'<p>Outcome: {escape(str(predicted.get("outcome") or "unknown"))} | Keep: {escape(str(predicted.get("keep")))}</p>',
            '<div class="button-row">',
            jump_button(case.get("videoId"), start, "Start"),
            jump_button(case.get("videoId"), event, "Event"),
            jump_button(case.get("videoId"), finish, "Finish"),
            f'<button type="button" onclick="markReviewedAndNext({case_index}, {clip_index})">Mark reviewed + next</button>',
            "</div>",
            '<div class="label-grid">',
            f'<label>Reviewed<input class="reviewed" type="checkbox" {reviewed}></label>',
            f'<label>Expected team<select class="expected-team">{team_options(case, expected_team)}</select></label>',
            f'<label>Highlight<select class="expected-highlight">{highlight_options(is_highlight)}</select></label>',
            f'<label>Event<select class="expected-event">{select_options(EVENT_TYPE_OPTIONS, expected_event)}</select></label>',
            f'<label>Outcome<select class="expected-outcome">{select_options(OUTCOME_OPTIONS, expected_outcome)}</select></label>',
            f'<label class="notes">Notes<textarea class="label-notes">{escape(str(clip.get("labelingNotes") or ""))}</textarea></label>',
            "</div>",
            "</article>",
        ]
    )


def jump_button(video_id: Any, seconds: str, label: str) -> str:
    if seconds == "":
        return f'<button type="button" disabled>{escape(label)}</button>'
    safe_video_id = escape(json.dumps(str(video_id)))
    return f'<button type="button" onclick="seekClip({safe_video_id}, {seconds})">{escape(label)} {seconds}s</button>'


def highlight_options(value: Any) -> str:
    selected = "unknown"
    if value is True:
        selected = "true"
    elif value is False:
        selected = "false"
    options = [("unknown", "Choose"), ("true", "Yes"), ("false", "No")]
    return "".join(f'<option value="{raw}" {"selected" if raw == selected else ""}>{label}</option>' for raw, label in options)


def team_options(case: dict[str, Any], selected_value: str) -> str:
    options: list[tuple[str, str]] = [("", "Choose team")]
    seen = {""}
    selected_team_id = string_or_none(case.get("selectedTeamId"))
    if selected_team_id and selected_team_id not in seen:
        label = string_or_none(case.get("selectedTeamColorLabel")) or selected_team_id
        options.append((selected_team_id, f"{selected_team_id} / selected team / {label}"))
        seen.add(selected_team_id)
    for team in case.get("detectedTeams", []):
        if not isinstance(team, dict):
            continue
        team_id = string_or_none(team.get("teamId"))
        if not team_id or team_id in seen:
            continue
        options.append((team_id, team_label(team)))
        seen.add(team_id)
    for raw, label in [
        ("opponent", "Opponent"),
        ("unclear", "Unclear team"),
        ("not_applicable", "Not applicable"),
    ]:
        if raw not in seen:
            options.append((raw, label))
            seen.add(raw)
    return select_options(options, selected_value)


def select_options(options: list[tuple[str, str]], selected_value: str) -> str:
    values = {raw for raw, _ in options}
    resolved_options = list(options)
    if selected_value and selected_value not in values:
        resolved_options.append((selected_value, f"Existing: {selected_value}"))
    return "".join(
        f'<option value="{escape(raw)}" {"selected" if raw == selected_value else ""}>{escape(label)}</option>'
        for raw, label in resolved_options
    )


def seconds_or_empty(value: Any) -> str:
    number = number_or_none(value)
    return "" if number is None else f"{number:.3f}"


def format_number(value: Any) -> str:
    number = number_or_none(value)
    return "unknown" if number is None else f"{number:.2f}"


def team_label(team: dict[str, Any]) -> str:
    label = string_or_none(team.get("label")) or string_or_none(team.get("teamId")) or "team"
    color = string_or_none(team.get("colorLabel"))
    confidence = number_or_none(team.get("confidence"))
    pieces = [label]
    if color:
        pieces.append(color)
    if confidence is not None:
        pieces.append(f"{confidence:.2f}")
    return " / ".join(pieces)


def video_element_id(video_id: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in video_id.lower()).strip("-")
    return f"video-{safe or 'source'}"


def escape(value: str) -> str:
    return html.escape(value, quote=True)


CSS = """
:root {
  color-scheme: dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #101116;
  color: #f5f7fb;
}
body {
  margin: 0;
  padding: 28px;
  line-height: 1.45;
}
h1, h2, h3, p {
  margin-top: 0;
}
.lede, .clip-meta, .path {
  color: #aeb4c2;
}
.summary-panel {
  border-color: #3a4562;
}
.label-progress {
  color: #f6c95f;
  font-weight: 800;
}
.panel {
  border: 1px solid #2c3140;
  border-radius: 14px;
  background: #171923;
  padding: 18px;
  margin: 0 0 18px;
}
video {
  display: block;
  width: min(100%, 960px);
  max-height: 62vh;
  border-radius: 12px;
  background: #000;
}
.case-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}
.clip-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 14px;
}
.clip-card {
  border: 1px solid #30364a;
  border-radius: 12px;
  background: #1d202d;
  padding: 14px;
}
.clip-card:focus {
  outline: 3px solid #f6c95f;
  outline-offset: 2px;
}
.clip-card.complete {
  border-color: #1f9d6a;
  background: #172620;
}
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}
button {
  border: 0;
  border-radius: 999px;
  background: #8b5cf6;
  color: white;
  font-weight: 700;
  padding: 9px 13px;
  cursor: pointer;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
.file-button {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #2563eb;
  color: white;
  font-weight: 800;
  padding: 9px 13px;
  cursor: pointer;
}
.file-button input {
  display: none;
}
.label-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
label {
  display: grid;
  gap: 5px;
  color: #c8cfdd;
  font-size: 13px;
  font-weight: 700;
}
input, select, textarea {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #373e52;
  border-radius: 10px;
  background: #11131b;
  color: #f5f7fb;
  padding: 9px;
}
input[type="checkbox"] {
  width: auto;
  justify-self: start;
}
.notes {
  grid-column: 1 / -1;
}
textarea {
  min-height: 64px;
  resize: vertical;
}
@media (max-width: 720px) {
  body {
    padding: 16px;
  }
  .case-heading {
    display: block;
  }
  .label-grid {
    grid-template-columns: 1fr;
  }
}
""".strip()


JS = r"""
const reviewData = JSON.parse(document.getElementById("review-data").textContent);
window.reviewData = reviewData;

function videoElementId(videoId) {
  const safe = String(videoId || "source").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `video-${safe || "source"}`;
}

function seekClip(videoId, seconds) {
  const video = document.getElementById(videoElementId(videoId));
  if (!video) return;
  video.currentTime = Math.max(0, Number(seconds) || 0);
  video.scrollIntoView({ behavior: "smooth", block: "center" });
  video.play().catch(() => {});
}

function boolFromSelect(value) {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

function draftStorageKey() {
  const caseIds = reviewData.cases.map(casePayload => casePayload.caseId || casePayload.labelsPayload?.caseId || "case").join("|");
  const draftPrefill = reviewData.draftPrefill;
  const prefillKey = draftPrefill
    ? `prefill:${draftPrefill.source || "draft"}:${draftPrefill.appliedClipCount || 0}:${draftPrefill.skippedClipCount || 0}:${draftPrefill.humanReviewRequired === true ? "human" : "trusted"}`
    : "prefill:none";
  return `hoopclips-team-label-draft:${caseIds}:${prefillKey}`;
}

function draftStatus(message) {
  const status = document.getElementById("draft-status");
  if (status) status.textContent = message;
}

function safeLocalStorage() {
  try {
    const storage = window.localStorage;
    const probe = "__hoopclips_label_probe__";
    storage.setItem(probe, "1");
    storage.removeItem(probe);
    return storage;
  } catch (_error) {
    return null;
  }
}

function updateClip(caseIndex, clipIndex) {
  const card = document.querySelector(`[data-case-index="${caseIndex}"][data-clip-index="${clipIndex}"]`);
  const clip = reviewData.cases[caseIndex].labelsPayload.clips[clipIndex];
  if (!card || !clip) return;
  const expectedTeam = card.querySelector(".expected-team").value.trim();
  const expectedEvent = card.querySelector(".expected-event").value.trim();
  const expectedOutcome = card.querySelector(".expected-outcome").value.trim();
  const expectedHighlight = boolFromSelect(card.querySelector(".expected-highlight").value);
  clip.needsLabel = !card.querySelector(".reviewed").checked;
  clip.expected = {
    teamId: expectedTeam || null,
    isHighlight: expectedHighlight,
    eventType: expectedEvent || null,
    outcome: expectedOutcome || null,
  };
  clip.labelingNotes = card.querySelector(".label-notes").value.trim();
}

function clipCompleteFromCard(card) {
  return Boolean(
    card.querySelector(".reviewed")?.checked &&
    card.querySelector(".expected-team")?.value &&
    card.querySelector(".expected-highlight")?.value !== "unknown" &&
    card.querySelector(".expected-event")?.value &&
    card.querySelector(".expected-outcome")?.value
  );
}

function updateCase(caseIndex) {
  const cards = document.querySelectorAll(`[data-case-index="${caseIndex}"][data-clip-index]`);
  cards.forEach(card => updateClip(caseIndex, Number(card.dataset.clipIndex)));
}

function updateAllCases() {
  reviewData.cases.forEach((_casePayload, caseIndex) => updateCase(caseIndex));
}

function setSelectValue(select, value) {
  if (!select) return;
  const normalized = value == null ? "" : String(value);
  select.value = normalized;
}

function applyClipPayloadToCard(caseIndex, clipIndex, clipPayload) {
  const card = document.querySelector(`[data-case-index="${caseIndex}"][data-clip-index="${clipIndex}"]`);
  if (!card || !clipPayload) return;
  const expected = clipPayload.expected || {};
  const highlightValue = expected.isHighlight === true ? "true" : expected.isHighlight === false ? "false" : "unknown";
  card.querySelector(".reviewed").checked = clipPayload.needsLabel === false;
  setSelectValue(card.querySelector(".expected-team"), expected.teamId);
  setSelectValue(card.querySelector(".expected-highlight"), highlightValue);
  setSelectValue(card.querySelector(".expected-event"), expected.eventType);
  setSelectValue(card.querySelector(".expected-outcome"), expected.outcome);
  const notes = card.querySelector(".label-notes");
  if (notes) notes.value = clipPayload.labelingNotes || "";
  updateClip(caseIndex, clipIndex);
}

function findCaseIndex(caseId) {
  return reviewData.cases.findIndex(casePayload => String(casePayload.caseId || casePayload.labelsPayload?.caseId || "") === String(caseId || ""));
}

function findClipIndex(caseIndex, draftClip) {
  const currentClips = reviewData.cases[caseIndex]?.labelsPayload?.clips || [];
  return currentClips.findIndex(currentClip => {
    const labelMatches = draftClip.labelId && currentClip.labelId === draftClip.labelId;
    const predictionMatches = draftClip.predictionClipId && currentClip.predictionClipId === draftClip.predictionClipId;
    return Boolean(labelMatches || predictionMatches);
  });
}

function applyDraftClipToCard(caseIndex, clipIndex, draftClip, humanReviewRequired) {
  const currentClip = reviewData.cases[caseIndex]?.labelsPayload?.clips?.[clipIndex];
  if (!currentClip || !draftClip || typeof draftClip !== "object") return false;
  const expected = draftClip.expected || {};
  currentClip.expected = {
    teamId: expected.teamId || null,
    isHighlight: expected.isHighlight === true ? true : expected.isHighlight === false ? false : null,
    eventType: expected.eventType || null,
    outcome: expected.outcome || null,
  };
  currentClip.labelingNotes = draftClip.labelingNotes || currentClip.labelingNotes || "";
  currentClip.needsLabel = humanReviewRequired ? true : draftClip.needsLabel !== false;
  applyClipPayloadToCard(caseIndex, clipIndex, currentClip);
  return true;
}

function applyDraftBundlePayload(payload) {
  if (!payload || payload.schemaVersion !== "team-highlight-manual-label-bundle-v1" || !Array.isArray(payload.cases)) {
    throw new Error("Draft bundle must use schemaVersion team-highlight-manual-label-bundle-v1.");
  }
  const humanReviewRequired = payload.humanReviewRequired === true || String(payload.source || "").includes("draft");
  let applied = 0;
  let skipped = 0;
  payload.cases.forEach(draftCase => {
    const caseIndex = findCaseIndex(draftCase?.caseId);
    if (caseIndex < 0 || !Array.isArray(draftCase?.clips)) {
      skipped += Array.isArray(draftCase?.clips) ? draftCase.clips.length : 1;
      return;
    }
    draftCase.clips.forEach(draftClip => {
      const clipIndex = findClipIndex(caseIndex, draftClip || {});
      if (clipIndex < 0) {
        skipped += 1;
        return;
      }
      if (applyDraftClipToCard(caseIndex, clipIndex, draftClip, humanReviewRequired)) {
        applied += 1;
      } else {
        skipped += 1;
      }
    });
  });
  updateProgress();
  saveDraft();
  draftStatus(`Imported ${applied} draft labels${skipped ? `; skipped ${skipped}` : ""}. Review and mark each clip before download.`);
}

function importDraftBundle(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      applyDraftBundlePayload(JSON.parse(String(reader.result || "{}")));
    } catch (error) {
      draftStatus(`Draft import failed: ${error.message || error}`);
    } finally {
      event.target.value = "";
    }
  };
  reader.onerror = () => {
    draftStatus("Draft import failed: could not read the selected file.");
    event.target.value = "";
  };
  reader.readAsText(file);
}

function saveDraft() {
  updateAllCases();
  const storage = safeLocalStorage();
  if (!storage) {
    draftStatus("Local draft unavailable in this browser.");
    return;
  }
  const payload = {
    schemaVersion: "team-highlight-manual-label-draft-v1",
    savedAt: new Date().toISOString(),
    cases: reviewData.cases.map(casePayload => casePayload.labelsPayload),
  };
  storage.setItem(draftStorageKey(), JSON.stringify(payload));
  draftStatus(`Local draft saved at ${new Date(payload.savedAt).toLocaleTimeString()}.`);
}

function restoreDraft() {
  const storage = safeLocalStorage();
  if (!storage) {
    draftStatus("Local draft unavailable in this browser.");
    return;
  }
  const raw = storage.getItem(draftStorageKey());
  if (!raw) {
    draftStatus("No local draft saved yet.");
    return;
  }
  try {
    const payload = JSON.parse(raw);
    if (payload.schemaVersion !== "team-highlight-manual-label-draft-v1" || !Array.isArray(payload.cases)) {
      draftStatus("Saved draft ignored because it has an unknown format.");
      return;
    }
    payload.cases.forEach((savedCase, caseIndex) => {
      const currentCase = reviewData.cases[caseIndex]?.labelsPayload;
      if (!currentCase || savedCase?.caseId !== currentCase.caseId || !Array.isArray(savedCase.clips)) return;
      savedCase.clips.forEach((savedClip, clipIndex) => {
        const currentClip = currentCase.clips?.[clipIndex];
        if (!currentClip) return;
        if (savedClip.labelId !== currentClip.labelId || savedClip.predictionClipId !== currentClip.predictionClipId) return;
        Object.assign(currentClip, savedClip);
        applyClipPayloadToCard(caseIndex, clipIndex, currentClip);
      });
    });
    draftStatus(`Local draft restored from ${new Date(payload.savedAt).toLocaleString()}.`);
  } catch (_error) {
    draftStatus("Saved draft ignored because it could not be read.");
  }
}

function clearSavedDraft() {
  const storage = safeLocalStorage();
  if (!storage) {
    draftStatus("Local draft unavailable in this browser.");
    return;
  }
  storage.removeItem(draftStorageKey());
  draftStatus("Local draft cleared.");
}

function updateProgress() {
  let total = 0;
  let complete = 0;
  reviewData.cases.forEach((casePayload, caseIndex) => {
    const cards = Array.from(document.querySelectorAll(`[data-case-index="${caseIndex}"][data-clip-index]`));
    const caseComplete = cards.filter(clipCompleteFromCard).length;
    const caseTotal = cards.length;
    total += caseTotal;
    complete += caseComplete;
    const row = document.getElementById(`case-progress-${caseIndex}`);
    if (row) row.textContent = `${caseComplete} / ${caseTotal} clips complete. ${caseTotal - caseComplete} remaining.`;
    cards.forEach(card => card.classList.toggle("complete", clipCompleteFromCard(card)));
  });
  const overall = document.getElementById("overall-progress");
  if (overall) overall.innerHTML = `<strong>${complete}</strong> / ${total} clips complete. ${total - complete} still need labels.`;
}

function allClipCards() {
  return Array.from(document.querySelectorAll("[data-case-index][data-clip-index]"));
}

function focusClipCard(card) {
  if (!card) {
    draftStatus("All visible clips are complete.");
    return false;
  }
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.focus({ preventScroll: true });
  const casePayload = reviewData.cases[Number(card.dataset.caseIndex)];
  const clipPayload = casePayload?.clips?.[Number(card.dataset.clipIndex)];
  const video = document.getElementById(videoElementId(casePayload?.videoId));
  if (video && clipPayload?.eventCenter != null) {
    video.currentTime = Math.max(0, Number(clipPayload.eventCenter) || 0);
  }
  return true;
}

function focusNextIncomplete(caseIndex = null, clipIndex = null) {
  updateProgress();
  const cards = allClipCards();
  if (!cards.length) return false;
  let startIndex = -1;
  if (caseIndex !== null && clipIndex !== null) {
    startIndex = cards.findIndex(card => (
      Number(card.dataset.caseIndex) === Number(caseIndex) &&
      Number(card.dataset.clipIndex) === Number(clipIndex)
    ));
  }
  const ordered = cards.slice(startIndex + 1).concat(cards.slice(0, startIndex + 1));
  return focusClipCard(ordered.find(card => !clipCompleteFromCard(card)));
}

function markReviewedAndNext(caseIndex, clipIndex) {
  const card = document.querySelector(`[data-case-index="${caseIndex}"][data-clip-index="${clipIndex}"]`);
  if (!card) return;
  if (!card.querySelector(".expected-team")?.value ||
      card.querySelector(".expected-highlight")?.value === "unknown" ||
      !card.querySelector(".expected-event")?.value ||
      !card.querySelector(".expected-outcome")?.value) {
    draftStatus("Fill team, highlight, event, and outcome before marking this clip reviewed.");
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.focus({ preventScroll: true });
    return;
  }
  card.querySelector(".reviewed").checked = true;
  updateClip(Number(caseIndex), Number(clipIndex));
  updateProgress();
  saveDraft();
  if (!focusNextIncomplete(caseIndex, clipIndex)) {
    draftStatus("All clips are complete. Download all labels when ready.");
  }
}

function downloadCaseLabels(caseIndex) {
  updateProgress();
  const cards = Array.from(document.querySelectorAll(`[data-case-index="${caseIndex}"][data-clip-index]`));
  const incomplete = cards.filter(card => !clipCompleteFromCard(card)).length;
  if (incomplete > 0 && !window.confirm(`${incomplete} clip labels are incomplete. Download anyway?`)) {
    return;
  }
  updateCase(caseIndex);
  const casePayload = reviewData.cases[caseIndex].labelsPayload;
  const blob = new Blob([JSON.stringify(casePayload, null, 2) + "\n"], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${casePayload.caseId || "team_labels"}_manual_labels.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 2000);
}

function downloadAllCaseLabels() {
  updateProgress();
  const cards = Array.from(document.querySelectorAll("[data-case-index][data-clip-index]"));
  const incomplete = cards.filter(card => !clipCompleteFromCard(card)).length;
  if (incomplete > 0 && !window.confirm(`${incomplete} clip labels are incomplete. Download all anyway?`)) {
    return;
  }
  updateAllCases();
  const bundlePayload = {
    schemaVersion: "team-highlight-manual-label-bundle-v1",
    source: "team_highlight_label_review_page",
    cases: reviewData.cases.map(casePayload => casePayload.labelsPayload),
  };
  const blob = new Blob([JSON.stringify(bundlePayload, null, 2) + "\n"], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "team_highlight_manual_labels_bundle.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 2000);
}

window.addEventListener("input", updateProgress);
window.addEventListener("change", updateProgress);
window.addEventListener("input", saveDraft);
window.addEventListener("change", saveDraft);
restoreDraft();
updateProgress();
""".strip()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)

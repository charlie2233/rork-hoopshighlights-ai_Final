#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


@dataclass(frozen=True)
class VideoAngle:
    video_id: str
    angle_id: str
    label: str
    url: str


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    video_paths = parse_video_paths(args.video or [])
    video_urls = parse_video_urls(args.video_url or [])
    video_angle_paths = parse_video_angle_paths(args.video_angle or [])
    video_angle_urls = parse_video_angle_urls(args.video_url_angle or [])
    default_video_path = Path(args.video_path).resolve() if args.video_path else None
    draft_bundle = load_json(Path(args.draft_bundle).expanduser().resolve()) if args.draft_bundle else None
    payload = build_review_payload(
        manifest=load_json(manifest_path),
        manifest_dir=manifest_path.parent,
        video_paths=video_paths,
        video_urls=video_urls,
        video_angle_paths=video_angle_paths,
        video_angle_urls=video_angle_urls,
        default_video_path=default_video_path,
        draft_bundle=draft_bundle,
    )
    html_output = render_review_page(payload, title=args.title)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_output, encoding="utf-8")
    if args.json:
        print(json.dumps(review_page_output_metadata(output_path, payload), indent=2, sort_keys=True))
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
    parser.add_argument(
        "--video-url",
        action="append",
        help=(
            "Map one video id to a local-only browser URL as videoId=http://127.0.0.1:8787/source.mp4. "
            "Only file://, localhost, 127.0.0.1, or ::1 URLs without query strings are allowed."
        ),
    )
    parser.add_argument(
        "--video-angle",
        action="append",
        help=(
            "Add another local angle as videoId:angleName=/absolute/path.mp4. "
            "Repeat for sideline, baseline, broadcast, phone, or other synced angles."
        ),
    )
    parser.add_argument(
        "--video-url-angle",
        action="append",
        help=(
            "Add another local browser angle as videoId:angleName=http://127.0.0.1:8787/angle.mp4. "
            "Only local URLs without query strings are allowed."
        ),
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


def parse_video_urls(values: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--video-url must use videoId=http://127.0.0.1:8787/path.mp4")
        video_id, raw_url = value.split("=", 1)
        video_id = video_id.strip()
        if not video_id:
            raise ValueError("--video-url is missing a video id.")
        mapping[video_id] = validate_local_video_url(raw_url.strip())
    return mapping


def parse_video_angle_paths(values: list[str]) -> dict[str, list[VideoAngle]]:
    mapping: dict[str, list[VideoAngle]] = {}
    for value in values:
        video_id, angle_id, raw_path = parse_video_angle_assignment(value, option_name="--video-angle")
        mapping.setdefault(video_id, []).append(
            VideoAngle(
                video_id=video_id,
                angle_id=angle_id,
                label=label_for_angle(angle_id),
                url=Path(raw_path).expanduser().resolve().as_uri(),
            )
        )
    return mapping


def parse_video_angle_urls(values: list[str]) -> dict[str, list[VideoAngle]]:
    mapping: dict[str, list[VideoAngle]] = {}
    for value in values:
        video_id, angle_id, raw_url = parse_video_angle_assignment(value, option_name="--video-url-angle")
        mapping.setdefault(video_id, []).append(
            VideoAngle(
                video_id=video_id,
                angle_id=angle_id,
                label=label_for_angle(angle_id),
                url=validate_local_video_url(raw_url.strip()),
            )
        )
    return mapping


def parse_video_angle_assignment(value: str, *, option_name: str) -> tuple[str, str, str]:
    if "=" not in value:
        raise ValueError(f"{option_name} must use videoId:angleName=/absolute/path.mp4")
    left, raw_location = value.split("=", 1)
    if ":" not in left:
        raise ValueError(f"{option_name} must include an angle name as videoId:angleName=...")
    video_id, angle_id = left.split(":", 1)
    video_id = video_id.strip()
    angle_id = angle_id.strip()
    if not video_id:
        raise ValueError(f"{option_name} is missing a video id.")
    if not angle_id:
        raise ValueError(f"{option_name} is missing an angle name.")
    if not raw_location.strip():
        raise ValueError(f"{option_name} is missing a path or local URL.")
    return video_id, safe_angle_id(angle_id), raw_location.strip()


def safe_angle_id(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    if not safe:
        raise ValueError("Angle name must include at least one letter or number.")
    return safe


def label_for_angle(angle_id: str) -> str:
    return " ".join(part.capitalize() for part in angle_id.replace("_", "-").split("-") if part) or angle_id


def validate_local_video_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"file", "http", "https"}:
        raise ValueError("--video-url must use file:// or a localhost http(s) URL.")
    if parsed.query or parsed.fragment:
        raise ValueError("--video-url must not include query strings or fragments.")
    if any(marker.lower() in raw_url.lower() for marker in ("x-amz-", "signature=", "token=", "secret", "credential=")):
        raise ValueError("--video-url must not include signed URL, token, or credential markers.")
    if parsed.scheme == "file":
        if parsed.netloc not in {"", "localhost"}:
            raise ValueError("--video-url file URLs must be local.")
        if not parsed.path:
            raise ValueError("--video-url file URLs must include a path.")
        return raw_url
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("--video-url http(s) URLs must point to localhost, 127.0.0.1, or ::1.")
    if not parsed.path or parsed.path == "/":
        raise ValueError("--video-url http(s) URLs must include a video path.")
    return raw_url


def build_review_payload(
    *,
    manifest: dict[str, Any],
    manifest_dir: Path,
    video_paths: dict[str, Path],
    default_video_path: Path | None,
    video_urls: dict[str, str] | None = None,
    video_angle_paths: dict[str, list[VideoAngle]] | None = None,
    video_angle_urls: dict[str, list[VideoAngle]] | None = None,
    draft_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entries = manifest.get("cases")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a non-empty cases array.")

    cases: list[dict[str, Any]] = []
    videos: dict[str, str] = {}
    video_angles: dict[str, list[dict[str, str]]] = {}
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
        angles = merged_video_angles(
            video_id=video_id,
            local_video_url=(video_urls or {}).get(video_id),
            local_video_path=video_paths.get(video_id) or default_video_path,
            video_angle_paths=(video_angle_paths or {}).get(video_id, []),
            video_angle_urls=(video_angle_urls or {}).get(video_id, []),
        )
        if not angles:
            if default_video_path is None and video_id not in video_paths and video_id not in (video_urls or {}):
                raise ValueError(
                    f"Missing source video path or local video URL for videoId {video_id!r}. "
                    f"Use --video-path, --video {video_id}=..., --video-url {video_id}=http://127.0.0.1:8787/..., "
                    f"or --video-angle {video_id}:broadcast=/path.mp4."
                )
        if angles:
            videos[video_id] = angles[0]["url"]
            video_angles[video_id] = angles
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
        "videoAngles": video_angles,
        "cases": cases,
    }
    if draft_bundle is not None:
        payload["draftPrefill"] = apply_draft_bundle_to_review_payload(payload, draft_bundle)
    return payload


def merged_video_angles(
    *,
    video_id: str,
    local_video_url: str | None,
    local_video_path: Path | None,
    video_angle_paths: list[VideoAngle],
    video_angle_urls: list[VideoAngle],
) -> list[dict[str, str]]:
    angles: list[VideoAngle] = []
    if local_video_url:
        angles.append(VideoAngle(video_id=video_id, angle_id="main", label="Main", url=local_video_url))
    elif local_video_path is not None:
        angles.append(VideoAngle(video_id=video_id, angle_id="main", label="Main", url=local_video_path.as_uri()))
    angles.extend(video_angle_paths)
    angles.extend(video_angle_urls)

    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for angle in angles:
        angle_key = safe_angle_id(angle.angle_id)
        if angle_key in seen:
            raise ValueError(f"Duplicate angle {angle.angle_id!r} for videoId {video_id!r}.")
        seen.add(angle_key)
        unique.append(
            {
                "videoId": video_id,
                "angleId": angle_key,
                "label": angle.label,
                "url": angle.url,
            }
        )
    return unique


def review_page_output_metadata(output_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    review_priority_counts = count_review_priorities(payload)
    video_angle_count = 0
    if isinstance(payload.get("videoAngles"), dict):
        video_angle_count = sum(
            len([angle for angle in angles if isinstance(angle, dict)])
            for angles in payload["videoAngles"].values()
            if isinstance(angles, list)
        )
    metadata: dict[str, Any] = {
        "output": str(output_path),
        "caseCount": len([case for case in payload.get("cases", []) if isinstance(case, dict)]),
        "clipCount": sum(
            len([clip for clip in case.get("clips", []) if isinstance(clip, dict)])
            for case in payload.get("cases", [])
            if isinstance(case, dict)
        ),
        "videoAngleCount": video_angle_count,
        "reviewPriorityCounts": dict(sorted(review_priority_counts.items())),
    }
    if isinstance(payload.get("draftPrefill"), dict):
        metadata["draftPrefill"] = payload["draftPrefill"]
    return metadata


def count_review_priorities(payload: dict[str, Any]) -> dict[str, int]:
    review_priority_counts: dict[str, int] = {}
    for case in payload.get("cases", []):
        if not isinstance(case, dict):
            continue
        for clip in case.get("clips", []):
            if not isinstance(clip, dict):
                continue
            priority = clip.get("reviewPriority") if isinstance(clip.get("reviewPriority"), dict) else {}
            priority_key = string_or_none(priority.get("key")) or "standard_review"
            review_priority_counts[priority_key] = review_priority_counts.get(priority_key, 0) + 1
    return review_priority_counts


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
    review_priority = review_priority_for_clip(clip=clip, predicted=predicted, expected=expected)
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
        "reviewPriority": review_priority,
    }


def review_priority_for_clip(*, clip: dict[str, Any], predicted: dict[str, Any], expected: dict[str, Any]) -> dict[str, str]:
    notes = (string_or_none(clip.get("labelingNotes")) or "").lower()
    predicted_confidence = number_or_none(predicted.get("confidence"))
    team_confidence = number_or_none(predicted.get("teamConfidence"))
    attribution_status = (string_or_none(predicted.get("teamAttributionStatus")) or "").lower()
    expected_team = (string_or_none(expected.get("teamId")) or "").lower()
    expected_event = (string_or_none(expected.get("eventType")) or "").lower()
    expected_outcome = (string_or_none(expected.get("outcome")) or "").lower()
    uncertainty_markers = (
        "uncertainty",
        "uncertain",
        "unclear",
        "interrupted",
        "blocked view",
        "not visible",
        "hard to tell",
        "low confidence",
        "weak evidence",
    )
    close_review = (
        any(marker in notes for marker in uncertainty_markers)
        or expected_team in {"unclear", "not_applicable"}
        or expected_event in {"unclear", "bad_window", "not_basketball"}
        or expected_outcome in {"unclear", "bad_window", "not_basketball"}
        or (team_confidence is not None and team_confidence < 0.85)
        or (predicted_confidence is not None and predicted_confidence < 0.75)
        or (attribution_status and attribution_status not in {"matched", "all_teams", "unknown"})
    )
    has_complete_prefill = bool(
        expected_team
        and expected_event
        and expected_outcome
        and expected.get("isHighlight") is not None
    )
    quick_check = (
        has_complete_prefill
        and not close_review
        and (predicted_confidence is None or predicted_confidence >= 0.9)
        and (team_confidence is None or team_confidence >= 0.9)
    )
    if close_review:
        return {
            "key": "needs_close_review",
            "label": "Close review",
            "detail": "Uncertainty or weak evidence; verify the video carefully.",
        }
    if quick_check:
        return {
            "key": "quick_check",
            "label": "Quick check",
            "detail": "High-confidence draft; still verify before marking reviewed.",
        }
    return {
        "key": "standard_review",
        "label": "Standard review",
        "detail": "Verify the clip window and expected labels.",
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
            review_clips[clip_index]["reviewPriority"] = review_priority_for_clip(
                clip=review_clips[clip_index],
                predicted=review_clips[clip_index].get("predicted") if isinstance(review_clips[clip_index].get("predicted"), dict) else {},
                expected=review_clips[clip_index].get("expected") if isinstance(review_clips[clip_index].get("expected"), dict) else {},
            )
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
    priority_counts = count_review_priorities(payload)
    priority_total = sum(priority_counts.values())
    priority_summary = (
        '<div class="priority-filter" aria-label="Review priority filters">'
        f'<button type="button" class="priority-filter-button active" data-priority-filter="all" onclick="setPriorityFilter(\'all\')">All {priority_total}</button>'
        f'<button type="button" class="priority-filter-button" data-priority-filter="needs_close_review" onclick="setPriorityFilter(\'needs_close_review\')">Close {priority_counts.get("needs_close_review", 0)}</button>'
        f'<button type="button" class="priority-filter-button" data-priority-filter="standard_review" onclick="setPriorityFilter(\'standard_review\')">Standard {priority_counts.get("standard_review", 0)}</button>'
        f'<button type="button" class="priority-filter-button" data-priority-filter="quick_check" onclick="setPriorityFilter(\'quick_check\')">Quick {priority_counts.get("quick_check", 0)}</button>'
        "</div>"
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
            priority_summary,
            '<p class="lede" id="draft-status">Local draft not loaded.</p>',
            "</div>",
            '<div class="button-row">',
            '<button type="button" onclick="focusNextIncomplete()">Next incomplete</button>',
            '<button type="button" onclick="focusNextCloseReview()">Next close review</button>',
            '<button id="download-ready-button" type="button" onclick="downloadLaunchReadyLabels()" disabled>Finish labels first</button>',
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
    video_angles = payload.get("videoAngles")
    videos = payload.get("videos")
    if isinstance(video_angles, dict) and video_angles:
        angle_groups = video_angles
    elif isinstance(videos, dict):
        angle_groups = {
            str(video_id): [{"videoId": str(video_id), "angleId": "main", "label": "Main", "url": str(url)}]
            for video_id, url in videos.items()
        }
    else:
        return ""
    for video_id, raw_angles in angle_groups.items():
        angles = [angle for angle in raw_angles if isinstance(angle, dict)] if isinstance(raw_angles, list) else []
        if not angles:
            continue
        angle_rows = []
        for angle in angles:
            angle_id = string_or_none(angle.get("angleId")) or "main"
            angle_label = string_or_none(angle.get("label")) or label_for_angle(angle_id)
            url = string_or_none(angle.get("url")) or ""
            element_id = video_element_id(str(video_id), angle_id)
            angle_rows.append(
                "\n".join(
                    [
                        '<div class="video-angle">',
                        f'<div class="angle-label">{escape(angle_label)}</div>',
                        f'<video id="{escape(element_id)}" controls preload="metadata" src="{escape(url)}"></video>',
                        "</div>",
                    ]
                )
            )
        suffix = f" ({len(angles)} angles)" if len(angles) > 1 else ""
        sections.append(
            "\n".join(
                [
                    '<section class="panel video-panel">',
                    f"<h2>Source Video: {escape(str(video_id))}{escape(suffix)}</h2>",
                    '<div class="video-angle-grid">',
                    "\n".join(angle_rows),
                    "</div>",
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
    video_id = str(case.get("videoId") or "")
    start = seconds_or_empty(clip.get("start"))
    event = seconds_or_empty(clip.get("eventCenter"))
    finish = seconds_or_empty(clip.get("end"))
    expected_team = string_or_none(expected.get("teamId")) or ""
    expected_event = string_or_none(expected.get("eventType")) or ""
    expected_outcome = string_or_none(expected.get("outcome")) or ""
    is_highlight = expected.get("isHighlight")
    reviewed = "checked" if clip.get("needsLabel") is False else ""
    complete_class = " complete" if clip.get("needsLabel") is False else ""
    priority = clip.get("reviewPriority") if isinstance(clip.get("reviewPriority"), dict) else {}
    priority_key = string_or_none(priority.get("key")) or "standard_review"
    priority_class = priority_key.replace("_", "-")
    priority_label = string_or_none(priority.get("label")) or "Standard review"
    priority_detail = string_or_none(priority.get("detail")) or "Verify the clip window and expected labels."
    return "\n".join(
        [
            (
                f'<article class="clip-card{complete_class}" data-case-index="{case_index}" data-clip-index="{clip_index}" '
                f'data-video-id="{escape(video_id)}" data-start-seconds="{escape(start)}" '
                f'data-event-seconds="{escape(event)}" data-finish-seconds="{escape(finish)}" '
                f'data-review-priority="{escape(priority_key)}" tabindex="-1">'
            ),
            f"<h3>#{clip_index + 1} {escape(str(label))}</h3>",
            (
                f'<p class="review-priority {escape(priority_class)}"><strong>{escape(priority_label)}:</strong> '
                f"{escape(priority_detail)}</p>"
            ),
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


def video_element_id(video_id: str, angle_id: str = "main") -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in video_id.lower()).strip("-")
    safe_angle = "".join(ch if ch.isalnum() else "-" for ch in angle_id.lower()).strip("-")
    return f"video-{safe or 'source'}-{safe_angle or 'main'}"


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
.video-panel {
  position: sticky;
  top: 0;
  z-index: 5;
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.34);
}
.video-panel h2 {
  font-size: 16px;
  margin-bottom: 8px;
}
.video-angle-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}
.video-angle {
  display: grid;
  gap: 6px;
}
.angle-label {
  color: #c8cfdd;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}
.video-panel video {
  max-height: min(42vh, 420px);
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
.review-priority {
  display: inline-flex;
  width: fit-content;
  max-width: 100%;
  border: 1px solid #394152;
  border-radius: 999px;
  background: #232839;
  color: #d8deea;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
}
.review-priority.quick-check {
  border-color: #1f9d6a;
  background: #173026;
  color: #b8f5d8;
}
.review-priority.needs-close-review {
  border-color: #f6c95f;
  background: #352b17;
  color: #ffe29a;
}
.priority-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}
.priority-filter-button {
  background: #232839;
  color: #d8deea;
}
.priority-filter-button.active {
  background: #f6c95f;
  color: #171923;
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
  .video-panel {
    position: static;
  }
  .label-grid {
    grid-template-columns: 1fr;
  }
}
""".strip()


JS = r"""
const reviewData = JSON.parse(document.getElementById("review-data").textContent);
window.reviewData = reviewData;
let currentPriorityFilter = "all";

function videoElementId(videoId, angleId = "main") {
  const safe = String(videoId || "source").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const safeAngle = String(angleId || "main").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `video-${safe || "source"}-${safeAngle || "main"}`;
}

function videoElementsFor(videoId) {
  const angles = reviewData.videoAngles?.[videoId];
  if (Array.isArray(angles) && angles.length > 0) {
    return angles
      .map(angle => document.getElementById(videoElementId(videoId, angle.angleId || "main")))
      .filter(Boolean);
  }
  const legacy = document.getElementById(videoElementId(videoId));
  return legacy ? [legacy] : [];
}

function seekClip(videoId, seconds) {
  const videos = videoElementsFor(videoId);
  if (!videos.length) return;
  const targetTime = Math.max(0, Number(seconds) || 0);
  videos.forEach(video => {
    video.currentTime = targetTime;
  });
  videos[0].scrollIntoView({ behavior: "smooth", block: "center" });
  videos[0].play().catch(() => {});
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

function updatePriorityFilterVisibility() {
  allClipCards({ visibleOnly: false }).forEach(card => {
    const matches = currentPriorityFilter === "all" || card.dataset.reviewPriority === currentPriorityFilter;
    card.hidden = !matches;
  });
  document.querySelectorAll(".priority-filter-button").forEach(button => {
    button.classList.toggle("active", button.dataset.priorityFilter === currentPriorityFilter);
  });
}

function setPriorityFilter(priority) {
  currentPriorityFilter = priority || "all";
  updatePriorityFilterVisibility();
  updateProgress();
  draftStatus(currentPriorityFilter === "all" ? "Showing all review priorities." : `Filtered to ${currentPriorityFilter.replace(/_/g, " ")} clips.`);
  focusNextIncomplete();
}

function updateProgress() {
  updatePriorityFilterVisibility();
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
  const readyButton = document.getElementById("download-ready-button");
  if (readyButton) {
    const incomplete = total - complete;
    readyButton.disabled = incomplete > 0;
    readyButton.textContent = incomplete > 0 ? `Finish ${incomplete} label${incomplete === 1 ? "" : "s"} first` : "Download launch-ready labels";
  }
}

function allClipCards(options = {}) {
  const visibleOnly = options.visibleOnly !== false;
  const cards = Array.from(document.querySelectorAll("[data-case-index][data-clip-index]"));
  return visibleOnly ? cards.filter(card => !card.hidden) : cards;
}

function activeClipCard() {
  const focused = document.activeElement?.closest?.("[data-case-index][data-clip-index]");
  if (focused) return focused;
  const cards = allClipCards();
  return cards.find(card => !clipCompleteFromCard(card)) || cards[0] || null;
}

function seekClipFromCard(card, marker) {
  if (!card) return;
  const seconds = card.dataset[`${marker}Seconds`];
  if (seconds === undefined || seconds === "") return;
  seekClip(card.dataset.videoId, seconds);
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
  const videos = videoElementsFor(casePayload?.videoId);
  if (videos.length && clipPayload?.eventCenter != null) {
    const targetTime = Math.max(0, Number(clipPayload.eventCenter) || 0);
    videos.forEach(video => {
      video.currentTime = targetTime;
    });
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

function focusNextCloseReview() {
  updateProgress();
  const cards = allClipCards();
  const closeReviewCard = cards.find(card => (
    card.dataset.reviewPriority === "needs_close_review" &&
    !clipCompleteFromCard(card)
  ));
  if (focusClipCard(closeReviewCard)) return true;
  draftStatus("No close-review clips remain. Continuing with the next incomplete label.");
  return focusNextIncomplete();
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

function handleReviewShortcut(event) {
  const targetTag = String(event.target?.tagName || "").toLowerCase();
  if (["input", "select", "textarea"].includes(targetTag)) return;
  if (event.altKey || event.ctrlKey || event.metaKey) return;

  const key = String(event.key || "").toLowerCase();
  if (!["s", "e", "f", "r", "n"].includes(key)) return;

  const card = activeClipCard();
  if (!card) return;

  event.preventDefault();
  if (key === "s") {
    seekClipFromCard(card, "start");
  } else if (key === "e") {
    seekClipFromCard(card, "event");
  } else if (key === "f") {
    seekClipFromCard(card, "finish");
  } else if (key === "r") {
    markReviewedAndNext(Number(card.dataset.caseIndex), Number(card.dataset.clipIndex));
  } else if (key === "n") {
    focusNextIncomplete(Number(card.dataset.caseIndex), Number(card.dataset.clipIndex));
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
  downloadLabelBundle();
}

function downloadLaunchReadyLabels() {
  updateProgress();
  const cards = Array.from(document.querySelectorAll("[data-case-index][data-clip-index]"));
  const incomplete = cards.filter(card => !clipCompleteFromCard(card)).length;
  if (incomplete > 0) {
    draftStatus(`${incomplete} clip labels are incomplete. Finish every label before downloading launch-ready labels.`);
    focusNextIncomplete();
    return;
  }
  downloadLabelBundle();
}

function downloadLabelBundle() {
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
window.addEventListener("keydown", handleReviewShortcut);
restoreDraft();
updateProgress();
""".strip()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)

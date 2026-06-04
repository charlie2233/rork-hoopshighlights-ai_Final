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

from scripts.build_team_highlight_eval_payload import (
    extract_analysis_result,
    load_json,
    normalize_detected_teams,
    normalize_team_mode,
    number_or_none,
    selected_team_color_from_analysis,
    selected_team_color_from_detected_options,
    selected_team_from_analysis,
    string_or_none,
    team_mode_from_analysis,
)


DEFAULT_TEMPORAL_DEDUPE_MIN_OVERLAP_RATIO = 0.25
DEFAULT_TEMPORAL_DEDUPE_CENTER_TOLERANCE_SECONDS = 4.0
DEFAULT_TEMPORAL_DEDUPE_START_TOLERANCE_SECONDS = 4.0


def main() -> int:
    args = parse_args()
    payload = build_label_template(
        analysis=load_json(Path(args.analysis_result)),
        case_id=args.case_id,
        video_id=args.video_id,
        team_mode=args.team_mode,
        selected_team_id=args.selected_team_id,
        selected_team_color_label=args.selected_team_color_label,
        confidence_threshold=args.confidence_threshold,
        temporal_dedupe=not args.no_temporal_dedupe,
        temporal_dedupe_min_overlap_ratio=args.temporal_dedupe_min_overlap_ratio,
        temporal_dedupe_center_tolerance_seconds=args.temporal_dedupe_center_tolerance_seconds,
        temporal_dedupe_start_tolerance_seconds=args.temporal_dedupe_start_tolerance_seconds,
    )
    output = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a manual-label JSON template from a real HoopClips cloud analysis result. "
            "The template is metadata only and must be filled by a human before evaluation."
        )
    )
    parser.add_argument("--analysis-result", required=True, help="Cloud analysis job/result JSON exported from staging or local backend.")
    parser.add_argument("--output", help="Write labels template here. Defaults to stdout.")
    parser.add_argument("--case-id", help="Override caseId for this footage case.")
    parser.add_argument("--video-id", help="Override videoId for this footage case.")
    parser.add_argument("--team-mode", choices=("team", "all"), help="Override team mode.")
    parser.add_argument("--selected-team-id", help="Override selected team id for selected-team labeling.")
    parser.add_argument("--selected-team-color-label", help="Override selected team jersey color label.")
    parser.add_argument("--confidence-threshold", type=float, help="Override selected-team confidence threshold.")
    parser.add_argument("--no-temporal-dedupe", action="store_true", help="Keep every cloud candidate, including near-identical overlapping windows.")
    parser.add_argument("--temporal-dedupe-min-overlap-ratio", type=float, default=DEFAULT_TEMPORAL_DEDUPE_MIN_OVERLAP_RATIO)
    parser.add_argument("--temporal-dedupe-center-tolerance-seconds", type=float, default=DEFAULT_TEMPORAL_DEDUPE_CENTER_TOLERANCE_SECONDS)
    parser.add_argument("--temporal-dedupe-start-tolerance-seconds", type=float, default=DEFAULT_TEMPORAL_DEDUPE_START_TOLERANCE_SECONDS)
    return parser.parse_args()


def build_label_template(
    *,
    analysis: dict[str, Any],
    case_id: str | None = None,
    video_id: str | None = None,
    team_mode: str | None = None,
    selected_team_id: str | None = None,
    selected_team_color_label: str | None = None,
    confidence_threshold: float | None = None,
    temporal_dedupe: bool = True,
    temporal_dedupe_min_overlap_ratio: float = DEFAULT_TEMPORAL_DEDUPE_MIN_OVERLAP_RATIO,
    temporal_dedupe_center_tolerance_seconds: float = DEFAULT_TEMPORAL_DEDUPE_CENTER_TOLERANCE_SECONDS,
    temporal_dedupe_start_tolerance_seconds: float = DEFAULT_TEMPORAL_DEDUPE_START_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    result = extract_analysis_result(analysis)
    analysis_job_id = string_or_none(
        analysis.get("jobId")
        or analysis.get("analysisJobId")
        or result.get("jobId")
        or result.get("analysisJobId")
    )
    detected_teams = normalize_detected_teams(result.get("detectedTeams") or analysis.get("detectedTeams"))
    resolved_team_mode = normalize_team_mode(team_mode) or team_mode_from_analysis(result) or ("team" if selected_team_id or selected_team_from_analysis(result) else "all")
    resolved_selected_team_id = (selected_team_id or selected_team_from_analysis(result)) if resolved_team_mode == "team" else None
    resolved_color_label = None
    if resolved_team_mode == "team":
        resolved_color_label = (
            selected_team_color_label
            or selected_team_color_from_analysis(result)
            or selected_team_color_from_detected_options(resolved_selected_team_id, detected_teams)
        )
    threshold = confidence_threshold
    if threshold is None:
        team_selection = result.get("teamSelection")
        if isinstance(team_selection, dict):
            threshold = number_or_none(team_selection.get("confidenceThreshold"))

    clips = [clip for clip in result.get("clips", []) if isinstance(clip, dict)]
    dedupe_result = temporal_dedupe_clips(
        clips,
        enabled=temporal_dedupe,
        min_overlap_ratio=temporal_dedupe_min_overlap_ratio,
        center_tolerance_seconds=temporal_dedupe_center_tolerance_seconds,
        start_tolerance_seconds=temporal_dedupe_start_tolerance_seconds,
    )
    kept_clips = dedupe_result["keptClips"]
    return {
        "schemaVersion": "team-highlight-manual-label-template-v1",
        "source": "real_cloud_analysis_label_template",
        "instructions": [
            "Fill every clip before running build_team_highlight_eval_payload.py.",
            "Set needsLabel to false only after expected.teamId, expected.isHighlight, expected.eventType, and expected.outcome are correct.",
            "Set reviewedByHuman to true only after watching the source video; GPT/predicted fields are data-entry help, not evidence.",
            "Keep opponent clips, boring clips, bad timing windows, and uncertain review clips in this file so precision and recall are not inflated.",
            "Do not paste secrets, storage credentials, or presigned URLs into this labels file.",
        ],
        "caseId": case_id or analysis_job_id or "replace_with_case_id",
        "videoId": video_id or string_or_none(analysis.get("videoId") or result.get("videoId")) or "replace_with_video_id",
        "analysisJobId": analysis_job_id,
        "teamMode": resolved_team_mode,
        "selectedTeamId": resolved_selected_team_id,
        "selectedTeamColorLabel": resolved_color_label,
        "confidenceThreshold": threshold if threshold is not None else 0.85,
        "detectedTeams": detected_teams,
        "temporalDedupe": dedupe_result["metadata"],
        "omittedDuplicateClips": dedupe_result["omittedDuplicateClips"],
        "clips": [label_template_row(int(item["predictionIndex"]), item["clip"]) for item in kept_clips],
    }


def temporal_dedupe_clips(
    clips: list[dict[str, Any]],
    *,
    enabled: bool,
    min_overlap_ratio: float,
    center_tolerance_seconds: float,
    start_tolerance_seconds: float,
) -> dict[str, Any]:
    indexed_clips = [{"predictionIndex": index, "clip": clip} for index, clip in enumerate(clips)]
    if not enabled:
        return {
            "keptClips": indexed_clips,
            "omittedDuplicateClips": [],
            "metadata": {
                "enabled": False,
                "originalClipCount": len(clips),
                "reviewClipCount": len(clips),
                "omittedClipCount": 0,
            },
        }

    kept_by_index: dict[int, dict[str, Any]] = {}
    omitted: list[dict[str, Any]] = []
    ranked = sorted(indexed_clips, key=lambda item: (-clip_quality_score(item["clip"]), clip_start(item["clip"]) or 0.0, item["predictionIndex"]))
    for candidate in ranked:
        duplicate_kept = first_temporal_duplicate(candidate, kept_by_index.values(), min_overlap_ratio, center_tolerance_seconds, start_tolerance_seconds)
        if duplicate_kept is None:
            kept_by_index[int(candidate["predictionIndex"])] = candidate
            continue
        omitted.append(omitted_duplicate_payload(candidate, duplicate_kept))

    kept = sorted(kept_by_index.values(), key=lambda item: int(item["predictionIndex"]))
    omitted.sort(key=lambda item: int(item["predictionIndex"]))
    return {
        "keptClips": kept,
        "omittedDuplicateClips": omitted,
        "metadata": {
            "enabled": True,
            "strategy": "ranked_temporal_overlap",
            "minOverlapRatio": min_overlap_ratio,
            "centerToleranceSeconds": center_tolerance_seconds,
            "startToleranceSeconds": start_tolerance_seconds,
            "originalClipCount": len(clips),
            "reviewClipCount": len(kept),
            "omittedClipCount": len(omitted),
        },
    }


def first_temporal_duplicate(
    candidate: dict[str, Any],
    kept_candidates: Any,
    min_overlap_ratio: float,
    center_tolerance_seconds: float,
    start_tolerance_seconds: float,
) -> dict[str, Any] | None:
    for kept in kept_candidates:
        if temporal_duplicate(candidate["clip"], kept["clip"], min_overlap_ratio, center_tolerance_seconds, start_tolerance_seconds):
            return kept
    return None


def temporal_duplicate(
    left: dict[str, Any],
    right: dict[str, Any],
    min_overlap_ratio: float,
    center_tolerance_seconds: float,
    start_tolerance_seconds: float,
) -> bool:
    left_start = clip_start(left)
    left_end = clip_end(left)
    right_start = clip_start(right)
    right_end = clip_end(right)
    if left_start is None or left_end is None or right_start is None or right_end is None:
        return False
    if left_end <= left_start or right_end <= right_start:
        return False

    overlap = max(0.0, min(left_end, right_end) - max(left_start, right_start))
    min_duration = max(min(left_end - left_start, right_end - right_start), 0.001)
    overlap_ratio = overlap / min_duration
    if overlap_ratio >= min_overlap_ratio:
        return True

    left_center = clip_event_center(left)
    right_center = clip_event_center(right)
    if left_center is not None and right_center is not None and abs(left_center - right_center) <= center_tolerance_seconds:
        return True

    return abs(left_start - right_start) <= start_tolerance_seconds and overlap > 0


def omitted_duplicate_payload(candidate: dict[str, Any], kept: dict[str, Any]) -> dict[str, Any]:
    clip = candidate["clip"]
    kept_clip = kept["clip"]
    return {
        "predictionIndex": int(candidate["predictionIndex"]),
        "predictionClipId": string_or_none(clip.get("id") or clip.get("clipId")) or f"prediction_{int(candidate['predictionIndex']):03d}",
        "start": clip_start(clip),
        "end": clip_end(clip),
        "eventCenter": clip_event_center(clip),
        "keptPredictionIndex": int(kept["predictionIndex"]),
        "keptPredictionClipId": string_or_none(kept_clip.get("id") or kept_clip.get("clipId")) or f"prediction_{int(kept['predictionIndex']):03d}",
        "reason": "temporal_overlap_duplicate",
    }


def clip_quality_score(clip: dict[str, Any]) -> float:
    team_attribution = clip.get("teamAttribution") if isinstance(clip.get("teamAttribution"), dict) else {}
    native_shot_signals = clip.get("nativeShotSignals") if isinstance(clip.get("nativeShotSignals"), dict) else {}
    score = 0.0
    if bool(clip.get("shouldAutoKeep") if "shouldAutoKeep" in clip else clip.get("keep", True)):
        score += 2.0
    for value in (
        clip.get("watchabilityScore"),
        clip.get("watchability"),
        clip.get("combinedScore"),
        clip.get("confidence"),
        clip.get("motionScore"),
        clip.get("audioPeak"),
        clip.get("audioScore"),
        team_attribution.get("confidence"),
        native_shot_signals.get("outcomeReliabilityScore"),
    ):
        score += number_or_none(value) or 0.0
    return score


def clip_start(clip: dict[str, Any]) -> float | None:
    return number_or_none(clip.get("startTime", clip.get("start")))


def clip_end(clip: dict[str, Any]) -> float | None:
    return number_or_none(clip.get("endTime", clip.get("end")))


def clip_event_center(clip: dict[str, Any]) -> float | None:
    center = number_or_none(clip.get("eventCenter"))
    if center is not None:
        return center
    start = clip_start(clip)
    end = clip_end(clip)
    if start is None or end is None:
        return None
    return round((start + end) / 2.0, 3)


def label_template_row(index: int, clip: dict[str, Any]) -> dict[str, Any]:
    start = number_or_none(clip.get("startTime", clip.get("start")))
    end = number_or_none(clip.get("endTime", clip.get("end")))
    clip_id = string_or_none(clip.get("id") or clip.get("clipId")) or f"prediction_{index:03d}"
    return {
        "labelId": f"label_{index:03d}_{clip_id}",
        "predictionIndex": index,
        "predictionClipId": clip_id,
        "start": start,
        "end": end,
        "needsLabel": True,
        "reviewedByHuman": False,
        "predicted": predicted_summary(clip),
        "expected": {
            "teamId": None,
            "isHighlight": None,
            "eventType": None,
            "outcome": None,
        },
        "labelingNotes": "",
    }


def predicted_summary(clip: dict[str, Any]) -> dict[str, Any]:
    team_attribution = clip.get("teamAttribution") if isinstance(clip.get("teamAttribution"), dict) else {}
    native_shot_signals = clip.get("nativeShotSignals") if isinstance(clip.get("nativeShotSignals"), dict) else {}
    summary = {
        "label": string_or_none(clip.get("label") or clip.get("eventType") or clip.get("basketballEvent")),
        "eventType": string_or_none(clip.get("eventType") or clip.get("basketballEvent") or clip.get("eventFamily")),
        "keep": bool(clip.get("shouldAutoKeep") if "shouldAutoKeep" in clip else clip.get("keep", True)),
        "confidence": number_or_none(clip.get("confidence")),
        "motionScore": number_or_none(clip.get("motionScore")),
        "audioPeak": number_or_none(clip.get("audioPeak") or clip.get("audioScore")),
        "watchabilityScore": number_or_none(clip.get("watchabilityScore") or clip.get("watchability") or clip.get("combinedScore")),
        "duplicateGroup": string_or_none(clip.get("duplicateGroup")),
        "teamId": string_or_none(team_attribution.get("teamId")),
        "teamConfidence": number_or_none(team_attribution.get("confidence")),
        "teamAttributionStatus": string_or_none(clip.get("teamAttributionStatus") or team_attribution.get("status")),
        "outcome": string_or_none(clip.get("outcome") or native_shot_signals.get("outcome")),
        "eventCenter": number_or_none(clip.get("eventCenter")),
        "nativeShotSignals": native_shot_signals or None,
    }
    for key in ("teamEvidence", "shotResultEvidence", "shotTrackingEvidence", "qualitySignals"):
        value = clip.get(key)
        if isinstance(value, dict):
            summary[key] = value
    return {key: value for key, value in summary.items() if value is not None}


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)

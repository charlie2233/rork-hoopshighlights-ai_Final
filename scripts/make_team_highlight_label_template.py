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
    return {
        "schemaVersion": "team-highlight-manual-label-template-v1",
        "source": "real_cloud_analysis_label_template",
        "instructions": [
            "Fill every clip before running build_team_highlight_eval_payload.py.",
            "Set needsLabel to false only after expected.teamId, expected.isHighlight, and expected.eventType are correct.",
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
        "clips": [label_template_row(index, clip) for index, clip in enumerate(clips)],
    }


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

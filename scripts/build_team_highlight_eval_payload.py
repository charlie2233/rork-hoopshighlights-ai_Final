#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_MIN_OVERLAP_RATIO = 0.25


def main() -> int:
    args = parse_args()
    payload = build_eval_payload(
        analysis=load_json(Path(args.analysis_result)),
        labels=load_json(Path(args.labels)),
        case_id=args.case_id,
        selected_team_id=args.selected_team_id,
        confidence_threshold=args.confidence_threshold,
        min_overlap_ratio=args.min_overlap_ratio,
        allow_unlabeled_predictions=args.allow_unlabeled_predictions,
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
            "Build a selected-team highlight accuracy eval payload from a real cloud analysis JSON "
            "and a manual labels JSON file. This does not inspect video pixels or call providers."
        )
    )
    parser.add_argument("--analysis-result", required=True, help="Cloud analysis job/result JSON exported from staging or local backend.")
    parser.add_argument("--labels", required=True, help="Manual labels JSON with expected team/highlight/event rows.")
    parser.add_argument("--output", help="Write evaluator-ready JSON here. Defaults to stdout.")
    parser.add_argument("--case-id", help="Override caseId for single-case label files.")
    parser.add_argument("--selected-team-id", help="Override selectedTeamId for single-case label files.")
    parser.add_argument("--confidence-threshold", type=float, help="Override selected-team confidence threshold.")
    parser.add_argument("--min-overlap-ratio", type=float, default=DEFAULT_MIN_OVERLAP_RATIO)
    parser.add_argument(
        "--allow-unlabeled-predictions",
        action="store_true",
        help="Allow prediction clips that were returned by analysis but not covered by manual labels.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} must contain a JSON object.")
    return payload


def build_eval_payload(
    *,
    analysis: dict[str, Any],
    labels: dict[str, Any],
    case_id: str | None = None,
    selected_team_id: str | None = None,
    confidence_threshold: float | None = None,
    min_overlap_ratio: float = DEFAULT_MIN_OVERLAP_RATIO,
    allow_unlabeled_predictions: bool = False,
) -> dict[str, Any]:
    result = extract_analysis_result(analysis)
    analysis_job_id = string_or_none(
        analysis.get("jobId")
        or analysis.get("analysisJobId")
        or result.get("jobId")
        or result.get("analysisJobId")
    )
    detected_teams = normalize_detected_teams(result.get("detectedTeams") or analysis.get("detectedTeams"))
    team_scan_job_id = string_or_none(
        analysis.get("teamScanJobId")
        or result.get("teamScanJobId")
        or analysis.get("scanJobId")
        or result.get("scanJobId")
        or (analysis_job_id if detected_teams else None)
    )
    prediction_clips = [clip for clip in ensure_list(result.get("clips")) if isinstance(clip, dict)]
    label_cases = normalize_label_cases(labels)
    if not label_cases:
        raise ValueError("Labels JSON must contain at least one case with clips.")
    if len(label_cases) > 1 and (case_id or selected_team_id or confidence_threshold is not None):
        raise ValueError("case-id, selected-team-id, and confidence-threshold overrides are only valid for single-case labels.")

    cases: list[dict[str, Any]] = []
    for index, label_case in enumerate(label_cases):
        label_selected_team_id = string_or_none(label_case.get("selectedTeamId"))
        analysis_selected_team_id = selected_team_from_analysis(result)
        case_team_mode = (
            normalize_team_mode(label_case.get("teamMode"))
            or team_mode_from_analysis(result)
            or ("team" if selected_team_id or label_selected_team_id or analysis_selected_team_id else "all")
        )
        selected = (
            selected_team_id or label_selected_team_id or analysis_selected_team_id
            if case_team_mode == "team"
            else None
        )
        case_detected_teams = normalize_detected_teams(label_case.get("detectedTeams")) or detected_teams
        selected_color_label = None
        if case_team_mode == "team":
            selected_color_label = (
                string_or_none(label_case.get("selectedTeamColorLabel") or label_case.get("colorLabel"))
                or selected_team_color_from_analysis(result)
                or selected_team_color_from_detected_options(selected, case_detected_teams)
            )
        threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else number_or_none(label_case.get("confidenceThreshold"))
        )
        matched_prediction_indexes: set[int] = set()
        clips: list[dict[str, Any]] = []
        for raw_label in ensure_list(label_case.get("clips")):
            if not isinstance(raw_label, dict):
                continue
            validate_manual_label_row(raw_label)
            prediction_index = resolve_prediction_index(raw_label, prediction_clips, min_overlap_ratio)
            prediction = (
                prediction_from_cloud_clip(prediction_clips[prediction_index])
                if prediction_index is not None
                else missing_prediction()
            )
            if prediction_index is not None:
                matched_prediction_indexes.add(prediction_index)
            clips.append(
                {
                    "labelId": string_or_none(raw_label.get("labelId") or raw_label.get("id")),
                    "expected": expected_from_label(raw_label),
                    "prediction": prediction,
                }
            )

        if not allow_unlabeled_predictions:
            unlabeled = [
                describe_prediction_clip(index, clip)
                for index, clip in enumerate(prediction_clips)
                if index not in matched_prediction_indexes
            ]
            if unlabeled:
                raise ValueError(
                    "Unlabeled prediction clips returned by analysis: "
                    + "; ".join(unlabeled[:8])
                    + (f"; and {len(unlabeled) - 8} more" if len(unlabeled) > 8 else "")
                )

        cases.append(
            {
                "caseId": case_id or string_or_none(label_case.get("caseId")) or string_or_none(analysis.get("jobId")) or f"case_{index + 1}",
                "videoId": string_or_none(label_case.get("videoId") or labels.get("videoId")),
                "analysisJobId": analysis_job_id,
                "teamScanJobId": string_or_none(label_case.get("teamScanJobId") or label_case.get("scanJobId")) or team_scan_job_id,
                "teamMode": case_team_mode,
                "selectedTeamId": selected,
                "selectedTeamColorLabel": selected_color_label,
                "detectedTeams": case_detected_teams,
                "confidenceThreshold": threshold if threshold is not None else 0.85,
                "clips": clips,
            }
        )

    return {
        "schemaVersion": "team-highlight-eval-v1",
        "source": "real_cloud_analysis_with_manual_labels",
        "cases": cases,
    }


def validate_manual_label_row(label: dict[str, Any]) -> None:
    if "needsLabel" not in label:
        return
    label_id = string_or_none(label.get("labelId") or label.get("id") or label.get("predictionClipId")) or "unknown"
    if label.get("needsLabel") is not False:
        raise ValueError(f"Manual label row {label_id} still has needsLabel=true; finish labeling before building eval payload.")

    expected = label.get("expected") or label.get("groundTruth") or {}
    if not isinstance(expected, dict):
        raise ValueError(f"Manual label row {label_id} expected must be an object.")
    missing: list[str] = []
    if not string_or_none(expected.get("teamId") or expected.get("groundTruthTeamId")):
        missing.append("expected.teamId")
    if not isinstance(expected.get("isHighlight"), bool) and "groundTruthHighlight" not in expected:
        missing.append("expected.isHighlight")
    if not string_or_none(expected.get("eventType") or expected.get("basketballEvent") or expected.get("label")):
        missing.append("expected.eventType")
    if missing:
        raise ValueError(f"Manual label row {label_id} is incomplete: {', '.join(missing)}.")


def extract_analysis_result(analysis: dict[str, Any]) -> dict[str, Any]:
    result = analysis.get("results") or analysis.get("result") or analysis
    if not isinstance(result, dict):
        raise ValueError("Analysis JSON must contain a result object.")
    if not isinstance(result.get("clips"), list):
        raise ValueError("Analysis result must contain a clips array.")
    return result


def normalize_label_cases(labels: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(labels.get("cases"), list):
        return [case for case in labels["cases"] if isinstance(case, dict)]
    if isinstance(labels.get("clips"), list):
        return [labels]
    return []


def resolve_prediction_index(
    label: dict[str, Any],
    prediction_clips: list[dict[str, Any]],
    min_overlap_ratio: float,
) -> int | None:
    explicit_index = integer_or_none(label.get("predictionIndex") or label.get("predictionClipIndex"))
    if explicit_index is not None:
        if explicit_index < 0 or explicit_index >= len(prediction_clips):
            raise ValueError(f"predictionIndex {explicit_index} is outside the analysis clip range.")
        return explicit_index

    explicit_id = string_or_none(label.get("predictionClipId") or label.get("clipId"))
    if explicit_id:
        for index, clip in enumerate(prediction_clips):
            if explicit_id == string_or_none(clip.get("id") or clip.get("clipId")):
                return index

    label_start = number_or_none(label.get("start"))
    label_end = number_or_none(label.get("end"))
    if label_start is None or label_end is None or label_end <= label_start:
        return None

    best_index: int | None = None
    best_ratio = 0.0
    label_duration = label_end - label_start
    for index, clip in enumerate(prediction_clips):
        clip_start = number_or_none(clip.get("startTime", clip.get("start")))
        clip_end = number_or_none(clip.get("endTime", clip.get("end")))
        if clip_start is None or clip_end is None or clip_end <= clip_start:
            continue
        overlap = max(0.0, min(label_end, clip_end) - max(label_start, clip_start))
        ratio = overlap / max(label_duration, 0.001)
        if ratio > best_ratio:
            best_ratio = ratio
            best_index = index

    return best_index if best_index is not None and best_ratio >= min_overlap_ratio else None


def expected_from_label(label: dict[str, Any]) -> dict[str, Any]:
    expected = label.get("expected") or label.get("groundTruth") or label
    if not isinstance(expected, dict):
        expected = label
    return {
        "teamId": expected.get("teamId") or expected.get("groundTruthTeamId"),
        "isHighlight": bool(expected.get("isHighlight") if "isHighlight" in expected else expected.get("groundTruthHighlight")),
        "eventType": expected.get("eventType") or expected.get("basketballEvent") or expected.get("label"),
        "outcome": expected.get("outcome") or expected.get("shotOutcome") or expected.get("result"),
    }


def prediction_from_cloud_clip(clip: dict[str, Any]) -> dict[str, Any]:
    team_attribution = clip.get("teamAttribution")
    if not isinstance(team_attribution, dict):
        team_attribution = {}
    native_shot_signals = clip.get("nativeShotSignals")
    if not isinstance(native_shot_signals, dict):
        native_shot_signals = {}

    start = number_or_none(clip.get("startTime", clip.get("start")))
    end = number_or_none(clip.get("endTime", clip.get("end")))
    duration = round(end - start, 4) if start is not None and end is not None else None
    keep = bool(clip.get("shouldAutoKeep") if "shouldAutoKeep" in clip else clip.get("keep", True))
    prediction: dict[str, Any] = {
        "keep": keep,
        "includeForReview": True,
        "teamAttribution": team_attribution,
        "teamAttributionStatus": clip.get("teamAttributionStatus") or team_attribution.get("status"),
        "eventType": clip.get("eventType") or clip.get("basketballEvent") or clip.get("eventFamily") or clip.get("label"),
        "start": start,
        "end": end,
        "duration": duration,
        "eventCenter": number_or_none(clip.get("eventCenter")),
        "outcome": clip.get("outcome") or native_shot_signals.get("outcome"),
        "outcomeEvidenceSource": clip.get("outcomeEvidenceSource") or native_shot_signals.get("outcomeEvidenceSource"),
        "outcomeReliabilityScore": clip.get("outcomeReliabilityScore") or native_shot_signals.get("outcomeReliabilityScore"),
        "nativeShotSignals": native_shot_signals,
    }
    for key in ("teamEvidence", "shotResultEvidence", "shotTrackingEvidence", "qualitySignals"):
        value = clip.get(key)
        if isinstance(value, dict):
            prediction[key] = value
    return prediction


def missing_prediction() -> dict[str, Any]:
    return {"keep": False, "includeForReview": False}


def selected_team_from_analysis(result: dict[str, Any]) -> str | None:
    team_selection = result.get("teamSelection")
    if isinstance(team_selection, dict) and team_selection.get("mode") == "team":
        return string_or_none(team_selection.get("teamId"))
    return None


def team_mode_from_analysis(result: dict[str, Any]) -> str | None:
    team_selection = result.get("teamSelection")
    if isinstance(team_selection, dict):
        return normalize_team_mode(team_selection.get("mode"))
    return None


def normalize_team_mode(value: Any) -> str | None:
    text = normalized_key(value)
    if text in {"all", "team"}:
        return text
    return None


def selected_team_color_from_analysis(result: dict[str, Any]) -> str | None:
    team_selection = result.get("teamSelection")
    if isinstance(team_selection, dict) and team_selection.get("mode") == "team":
        return string_or_none(team_selection.get("colorLabel"))
    return None


def selected_team_color_from_detected_options(selected_team_id: str | None, detected_teams: list[dict[str, Any]]) -> str | None:
    selected_key = normalized_key(selected_team_id)
    if not selected_key:
        return None
    for team in detected_teams:
        keys = {
            normalized_key(team.get("teamId")),
            normalized_key(team.get("label")),
            normalized_key(team.get("colorLabel")),
        }
        if selected_key in keys:
            return string_or_none(team.get("colorLabel"))
    return None


def normalize_detected_teams(value: Any) -> list[dict[str, Any]]:
    teams: list[dict[str, Any]] = []
    for item in ensure_list(value):
        if not isinstance(item, dict):
            continue
        team_id = string_or_none(item.get("teamId"))
        color_label = string_or_none(item.get("colorLabel"))
        label = string_or_none(item.get("label"))
        confidence = number_or_none(item.get("confidence"))
        teams.append(
            {
                "teamId": team_id,
                "label": label,
                "colorLabel": color_label,
                "confidence": confidence,
                "source": string_or_none(item.get("source")),
            }
        )
    return teams


def normalized_key(value: Any) -> str:
    text = string_or_none(value)
    if text is None:
        return ""
    return "".join(character.lower() for character in text if character.isalnum())


def describe_prediction_clip(index: int, clip: dict[str, Any]) -> str:
    start = clip.get("startTime", clip.get("start"))
    end = clip.get("endTime", clip.get("end"))
    label = clip.get("label") or clip.get("eventType") or "unknown"
    return f"index={index} {start}-{end} label={label!r}"


def ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def number_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def integer_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFENSIVE_EVENTS = {
    "block",
    "blocked_shot",
    "defensive_stop",
    "forced_to",
    "forced_turnover",
    "steal",
    "turnover_forced",
}
SHOT_EVENT_TOKENS = {
    "basket",
    "bucket",
    "dunk",
    "finish",
    "jumper",
    "layup",
    "made",
    "miss",
    "missed",
    "shot",
    "three",
}
MIN_EVAL_CLIP_SECONDS = 2.0
MIN_EVAL_SHOT_CLIP_SECONDS = 3.0
MIN_EVAL_SHOT_LEAD_IN_SECONDS = 0.9
MIN_EVAL_SHOT_FOLLOW_THROUGH_SECONDS = 0.6
MIN_EVAL_DEFENSIVE_LEAD_IN_SECONDS = 0.6
MIN_EVAL_DEFENSIVE_FOLLOW_THROUGH_SECONDS = 0.5


@dataclass(frozen=True)
class AccuracyThresholds:
    selectedTeamPrecision: float = 0.85
    selectedTeamRecallWithUncertain: float = 0.85
    highlightPrecision: float = 0.85
    highlightRecall: float = 0.85
    defensiveEventRecall: float = 0.85
    clipTimingQuality: float = 0.85


@dataclass(frozen=True)
class AccuracyMetrics:
    caseCount: int
    clipCount: int
    selectedTeamPrecision: float
    selectedTeamRecallWithUncertain: float
    highlightPrecision: float
    highlightRecall: float
    defensiveEventRecall: float
    clipTimingQuality: float
    uncertainReviewCount: int
    selectedTeamHighlightCount: int
    defensiveEventCount: int
    timingQualityClipCount: int
    badTimingClipCount: int


@dataclass(frozen=True)
class AccuracyReport:
    status: str
    metrics: AccuracyMetrics
    thresholds: AccuracyThresholds
    failures: list[str]


def main() -> int:
    args = parse_args()
    thresholds = AccuracyThresholds(
        selectedTeamPrecision=args.min_selected_team_precision,
        selectedTeamRecallWithUncertain=args.min_selected_team_recall,
        highlightPrecision=args.min_highlight_precision,
        highlightRecall=args.min_highlight_recall,
        defensiveEventRecall=args.min_defensive_event_recall,
        clipTimingQuality=args.min_clip_timing_quality,
    )
    report = evaluate_accuracy(load_json(Path(args.input)), thresholds=thresholds)

    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        print_text_report(report)

    return 0 if report.status == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score HoopClips selected-team/highlight accuracy from labeled JSON. "
            "This reads exported metadata only; it does not inspect videos or call providers."
        )
    )
    parser.add_argument("input", help="JSON file with cases/clips and ground-truth labels.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable report.")
    parser.add_argument("--min-selected-team-precision", type=float, default=0.85)
    parser.add_argument("--min-selected-team-recall", type=float, default=0.85)
    parser.add_argument("--min-highlight-precision", type=float, default=0.85)
    parser.add_argument("--min-highlight-recall", type=float, default=0.85)
    parser.add_argument("--min-defensive-event-recall", type=float, default=0.85)
    parser.add_argument("--min-clip-timing-quality", type=float, default=0.85)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit("Input JSON must be an object.")
    return payload


def evaluate_accuracy(payload: dict[str, Any], thresholds: AccuracyThresholds | None = None) -> AccuracyReport:
    thresholds = thresholds or AccuracyThresholds()
    cases = normalize_cases(payload)
    if not cases:
        metrics = AccuracyMetrics(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0)
        return AccuracyReport("fail", metrics, thresholds, ["No eval cases found."])

    counts = {
        "clips": 0,
        "confident_selected_predictions": 0,
        "correct_confident_selected_predictions": 0,
        "selected_team_highlights": 0,
        "selected_team_highlights_kept_or_uncertain": 0,
        "kept_predictions": 0,
        "correct_kept_predictions": 0,
        "highlights": 0,
        "kept_highlights": 0,
        "defensive_events": 0,
        "kept_defensive_events": 0,
        "uncertain_review": 0,
        "timing_quality_clips": 0,
        "good_timing_quality_clips": 0,
    }

    for case in cases:
        selected_team_id = string_or_none(case.get("selectedTeamId") or case.get("teamId"))
        confidence_threshold = number_or_default(case.get("confidenceThreshold"), 0.85)
        for raw_clip in ensure_list(case.get("clips")):
            if not isinstance(raw_clip, dict):
                continue
            clip = normalize_clip(raw_clip)
            if clip is None:
                continue
            counts["clips"] += 1

            expected_team_id = string_or_none(clip["expected"].get("teamId"))
            expected_highlight = bool(clip["expected"].get("isHighlight"))
            event_type = normalize_event_type(clip["expected"].get("eventType"))
            prediction = clip["prediction"]
            keep = bool(prediction.get("keep"))
            include_for_review = bool(prediction.get("includeForReview") or keep)
            predicted_team_id = string_or_none(prediction.get("teamId"))
            predicted_confidence = number_or_default(prediction.get("teamConfidence"), 0.0)
            status = str(prediction.get("teamAttributionStatus") or "").strip().lower()
            has_selected_team = selected_team_id is not None and expected_team_id == selected_team_id
            in_scope_highlight = expected_highlight and (selected_team_id is None or has_selected_team)
            confident_selected = (
                include_for_review
                and selected_team_id is not None
                and predicted_team_id == selected_team_id
                and predicted_confidence >= confidence_threshold
                and status != "uncertain"
            )
            uncertain_review = include_for_review and not confident_selected and (
                predicted_team_id is None
                or predicted_confidence < confidence_threshold
                or status in {"uncertain", "unknown", "missing"}
            )

            if confident_selected:
                counts["confident_selected_predictions"] += 1
                if has_selected_team:
                    counts["correct_confident_selected_predictions"] += 1

            if uncertain_review:
                counts["uncertain_review"] += 1

            if include_for_review:
                counts["timing_quality_clips"] += 1
                if clip_timing_is_valid(prediction, event_type):
                    counts["good_timing_quality_clips"] += 1

            if in_scope_highlight:
                counts["highlights"] += 1
                if keep:
                    counts["kept_highlights"] += 1

            if keep:
                counts["kept_predictions"] += 1
                if in_scope_highlight:
                    counts["correct_kept_predictions"] += 1

            if has_selected_team and expected_highlight:
                counts["selected_team_highlights"] += 1
                if keep and (confident_selected or uncertain_review):
                    counts["selected_team_highlights_kept_or_uncertain"] += 1

            if event_type in DEFENSIVE_EVENTS and has_selected_team:
                counts["defensive_events"] += 1
                if keep and (confident_selected or uncertain_review):
                    counts["kept_defensive_events"] += 1

    metrics = AccuracyMetrics(
        caseCount=len(cases),
        clipCount=counts["clips"],
        selectedTeamPrecision=ratio(
            counts["correct_confident_selected_predictions"],
            counts["confident_selected_predictions"],
        ),
        selectedTeamRecallWithUncertain=ratio(
            counts["selected_team_highlights_kept_or_uncertain"],
            counts["selected_team_highlights"],
        ),
        highlightPrecision=ratio(counts["correct_kept_predictions"], counts["kept_predictions"]),
        highlightRecall=ratio(counts["kept_highlights"], counts["highlights"]),
        defensiveEventRecall=ratio(counts["kept_defensive_events"], counts["defensive_events"]),
        clipTimingQuality=ratio(counts["good_timing_quality_clips"], counts["timing_quality_clips"]),
        uncertainReviewCount=counts["uncertain_review"],
        selectedTeamHighlightCount=counts["selected_team_highlights"],
        defensiveEventCount=counts["defensive_events"],
        timingQualityClipCount=counts["timing_quality_clips"],
        badTimingClipCount=counts["timing_quality_clips"] - counts["good_timing_quality_clips"],
    )
    failures = threshold_failures(metrics, thresholds)
    if metrics.clipCount == 0:
        failures.append("No scored clips found.")
    return AccuracyReport("fail" if failures else "pass", metrics, thresholds, failures)


def normalize_cases(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("cases"), list):
        return [case for case in payload["cases"] if isinstance(case, dict)]
    if isinstance(payload.get("clips"), list):
        return [
            {
                "caseId": payload.get("caseId", "default"),
                "selectedTeamId": payload.get("selectedTeamId") or payload.get("teamId"),
                "confidenceThreshold": payload.get("confidenceThreshold"),
                "clips": payload.get("clips"),
            }
        ]
    return []


def normalize_clip(raw_clip: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    expected = raw_clip.get("expected") or raw_clip.get("groundTruth") or {}
    prediction = raw_clip.get("prediction") or raw_clip.get("predicted") or {}
    if not isinstance(expected, dict) or not isinstance(prediction, dict):
        return None

    team_attribution = prediction.get("teamAttribution")
    if not isinstance(team_attribution, dict):
        team_attribution = {}

    normalized_expected = {
        "teamId": expected.get("teamId") or expected.get("groundTruthTeamId"),
        "isHighlight": bool(expected.get("isHighlight") if "isHighlight" in expected else expected.get("groundTruthHighlight")),
        "eventType": expected.get("eventType") or expected.get("basketballEvent") or expected.get("label"),
    }
    normalized_prediction = {
        "keep": bool(prediction.get("keep") if "keep" in prediction else prediction.get("shouldAutoKeep")),
        "includeForReview": bool(prediction.get("includeForReview", prediction.get("keep", prediction.get("shouldAutoKeep", False)))),
        "teamId": prediction.get("teamId") or team_attribution.get("teamId"),
        "teamConfidence": prediction.get("teamConfidence") or team_attribution.get("confidence"),
        "teamAttributionStatus": prediction.get("teamAttributionStatus") or team_attribution.get("status"),
        "eventType": prediction.get("eventType") or prediction.get("basketballEvent") or prediction.get("label") or normalized_expected["eventType"],
        "start": number_or_none(prediction.get("start", raw_clip.get("start"))),
        "end": number_or_none(prediction.get("end", raw_clip.get("end"))),
        "duration": number_or_none(prediction.get("duration", prediction.get("durationSeconds", raw_clip.get("duration", raw_clip.get("durationSeconds"))))),
        "eventCenter": number_or_none(prediction.get("eventCenter", raw_clip.get("eventCenter"))),
        "nativeShotTimingWindowOk": native_timing_window_ok(prediction),
    }
    return {"expected": normalized_expected, "prediction": normalized_prediction}


def clip_timing_is_valid(prediction: dict[str, Any], event_type: str) -> bool:
    start = number_or_none(prediction.get("start"))
    end = number_or_none(prediction.get("end"))
    event_center = number_or_none(prediction.get("eventCenter"))
    duration = number_or_none(prediction.get("duration"))
    if duration is None and start is not None and end is not None:
        duration = round(end - start, 4)
    if duration is None or duration < MIN_EVAL_CLIP_SECONDS:
        return False
    if prediction.get("nativeShotTimingWindowOk") is False:
        return False

    event_or_label = normalize_event_type(prediction.get("eventType") or event_type)
    defensive = event_or_label in DEFENSIVE_EVENTS or "blocked" in event_or_label
    shot_like = not defensive and any(token in event_or_label for token in SHOT_EVENT_TOKENS)
    if not shot_like and not defensive:
        return True
    if start is None or end is None or event_center is None:
        return False

    lead_in = event_center - start
    follow_through = end - event_center
    if shot_like:
        return (
            duration >= MIN_EVAL_SHOT_CLIP_SECONDS
            and lead_in >= MIN_EVAL_SHOT_LEAD_IN_SECONDS
            and follow_through >= MIN_EVAL_SHOT_FOLLOW_THROUGH_SECONDS
        )
    return lead_in >= MIN_EVAL_DEFENSIVE_LEAD_IN_SECONDS and follow_through >= MIN_EVAL_DEFENSIVE_FOLLOW_THROUGH_SECONDS


def threshold_failures(metrics: AccuracyMetrics, thresholds: AccuracyThresholds) -> list[str]:
    failures: list[str] = []
    checks = (
        ("selectedTeamPrecision", metrics.selectedTeamPrecision, thresholds.selectedTeamPrecision),
        ("selectedTeamRecallWithUncertain", metrics.selectedTeamRecallWithUncertain, thresholds.selectedTeamRecallWithUncertain),
        ("highlightPrecision", metrics.highlightPrecision, thresholds.highlightPrecision),
        ("highlightRecall", metrics.highlightRecall, thresholds.highlightRecall),
        ("defensiveEventRecall", metrics.defensiveEventRecall, thresholds.defensiveEventRecall),
        ("clipTimingQuality", metrics.clipTimingQuality, thresholds.clipTimingQuality),
    )
    for name, value, minimum in checks:
        if value < minimum:
            failures.append(f"{name} {value:.3f} is below required {minimum:.3f}.")
    return failures


def print_text_report(report: AccuracyReport) -> None:
    print(f"status: {report.status}")
    for key, value in asdict(report.metrics).items():
        print(f"{key}: {value}")
    if report.failures:
        print("failures:")
        for failure in report.failures:
            print(f"- {failure}")


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 4)


def ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_event_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    normalized = "".join(character if character.isalnum() else "_" for character in text)
    return "_".join(part for part in normalized.split("_") if part)


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


def number_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def native_timing_window_ok(prediction: dict[str, Any]) -> bool | None:
    signals = prediction.get("nativeShotSignals")
    if not isinstance(signals, dict) or "timingWindowOk" not in signals:
        return None
    return bool(signals.get("timingWindowOk"))


if __name__ == "__main__":
    sys.exit(main())

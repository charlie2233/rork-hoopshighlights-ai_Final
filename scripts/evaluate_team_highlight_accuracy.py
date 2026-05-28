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
MIN_EVAL_SHOT_OUTCOME_CONFIDENCE = 0.65
MIN_EVAL_RIM_ENTRY_SEQUENCE_CONFIDENCE = 0.72
MIN_EVAL_OUTCOME_RELIABILITY = 0.72
MIN_EVAL_TEAM_EVIDENCE_FRAME_REFS = 2
MIN_EVAL_TEAM_EVIDENCE_ROLE_GROUPS = 2

MADE_APPROACH_FRAME_ROLES = {"release", "shotarcearly", "eventcenter", "shotarclate", "rimapproach"}
MADE_ENTRY_FRAME_ROLES = {"outcome", "shotarclate", "rim", "rimentry"}
MADE_FOLLOW_THROUGH_FRAME_ROLES = {"belowrim", "postoutcome", "finish"}
MADE_BALL_FLIGHT_FRAME_ROLES = {
    "release",
    "shotarcearly",
    "eventcenter",
    "outcome",
    "shotarclate",
    "rimapproach",
    "rim",
    "rimentry",
    "belowrim",
    "postoutcome",
    "finish",
}


@dataclass(frozen=True)
class AccuracyThresholds:
    selectedTeamPrecision: float = 0.85
    selectedTeamEvidenceQuality: float = 0.85
    selectedTeamRecallWithUncertain: float = 0.85
    highlightPrecision: float = 0.85
    highlightRecall: float = 0.85
    defensiveEventRecall: float = 0.85
    clipTimingQuality: float = 0.85
    shotOutcomeEvidenceQuality: float = 0.85
    minSelectedTeamDefensiveEvents: int = 2
    minSelectedTeamBlocks: int = 1
    minSelectedTeamSteals: int = 1


@dataclass(frozen=True)
class AccuracyMetrics:
    caseCount: int
    clipCount: int
    selectedTeamPrecision: float
    selectedTeamEvidenceQuality: float
    selectedTeamRecallWithUncertain: float
    highlightPrecision: float
    highlightRecall: float
    defensiveEventRecall: float
    clipTimingQuality: float
    shotOutcomeEvidenceQuality: float
    uncertainReviewCount: int
    selectedTeamHighlightCount: int
    defensiveEventCount: int
    timingQualityClipCount: int
    badTimingClipCount: int
    shotOutcomeEvidenceClipCount: int
    badShotOutcomeEvidenceCount: int
    selectedTeamBlockCount: int
    selectedTeamStealCount: int
    selectedTeamEvidenceClipCount: int
    badSelectedTeamEvidenceCount: int


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
        selectedTeamEvidenceQuality=args.min_selected_team_evidence,
        selectedTeamRecallWithUncertain=args.min_selected_team_recall,
        highlightPrecision=args.min_highlight_precision,
        highlightRecall=args.min_highlight_recall,
        defensiveEventRecall=args.min_defensive_event_recall,
        clipTimingQuality=args.min_clip_timing_quality,
        shotOutcomeEvidenceQuality=args.min_shot_outcome_evidence,
        minSelectedTeamDefensiveEvents=args.min_selected_team_defensive_events,
        minSelectedTeamBlocks=args.min_selected_team_blocks,
        minSelectedTeamSteals=args.min_selected_team_steals,
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
    parser.add_argument("--min-selected-team-evidence", type=float, default=0.85)
    parser.add_argument("--min-selected-team-recall", type=float, default=0.85)
    parser.add_argument("--min-highlight-precision", type=float, default=0.85)
    parser.add_argument("--min-highlight-recall", type=float, default=0.85)
    parser.add_argument("--min-defensive-event-recall", type=float, default=0.85)
    parser.add_argument("--min-clip-timing-quality", type=float, default=0.85)
    parser.add_argument("--min-shot-outcome-evidence", type=float, default=0.85)
    parser.add_argument("--min-selected-team-defensive-events", type=int, default=2)
    parser.add_argument("--min-selected-team-blocks", type=int, default=1)
    parser.add_argument("--min-selected-team-steals", type=int, default=1)
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
        metrics = AccuracyMetrics(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        return AccuracyReport("fail", metrics, thresholds, ["No eval cases found."])

    counts = {
        "clips": 0,
        "confident_selected_predictions": 0,
        "correct_confident_selected_predictions": 0,
        "selected_team_evidence_predictions": 0,
        "good_selected_team_evidence_predictions": 0,
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
        "shot_outcome_evidence_clips": 0,
        "good_shot_outcome_evidence_clips": 0,
        "selected_team_blocks": 0,
        "selected_team_steals": 0,
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
            expected_shot_outcome = expected_outcome_for_clip(clip["expected"])
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
                counts["selected_team_evidence_predictions"] += 1
                if team_attribution_evidence_is_valid(prediction):
                    counts["good_selected_team_evidence_predictions"] += 1
                if has_selected_team:
                    counts["correct_confident_selected_predictions"] += 1

            if uncertain_review:
                counts["uncertain_review"] += 1

            if include_for_review:
                counts["timing_quality_clips"] += 1
                if clip_timing_is_valid(prediction, event_type):
                    counts["good_timing_quality_clips"] += 1
                if in_scope_highlight and expected_shot_outcome is not None:
                    counts["shot_outcome_evidence_clips"] += 1
                    if shot_outcome_evidence_is_valid(prediction, expected_shot_outcome):
                        counts["good_shot_outcome_evidence_clips"] += 1

            if in_scope_highlight:
                counts["highlights"] += 1
                if include_for_review:
                    counts["kept_highlights"] += 1

            if include_for_review:
                counts["kept_predictions"] += 1
                if in_scope_highlight:
                    counts["correct_kept_predictions"] += 1

            if has_selected_team and expected_highlight:
                counts["selected_team_highlights"] += 1
                if confident_selected or uncertain_review:
                    counts["selected_team_highlights_kept_or_uncertain"] += 1

            if event_type in DEFENSIVE_EVENTS and has_selected_team:
                counts["defensive_events"] += 1
                defensive_subtype = defensive_event_subtype(event_type)
                if defensive_subtype == "block":
                    counts["selected_team_blocks"] += 1
                elif defensive_subtype == "steal":
                    counts["selected_team_steals"] += 1
                if confident_selected or uncertain_review:
                    counts["kept_defensive_events"] += 1

    metrics = AccuracyMetrics(
        caseCount=len(cases),
        clipCount=counts["clips"],
        selectedTeamPrecision=ratio(
            counts["correct_confident_selected_predictions"],
            counts["confident_selected_predictions"],
        ),
        selectedTeamEvidenceQuality=ratio(
            counts["good_selected_team_evidence_predictions"],
            counts["selected_team_evidence_predictions"],
        ),
        selectedTeamRecallWithUncertain=ratio(
            counts["selected_team_highlights_kept_or_uncertain"],
            counts["selected_team_highlights"],
        ),
        highlightPrecision=ratio(counts["correct_kept_predictions"], counts["kept_predictions"]),
        highlightRecall=ratio(counts["kept_highlights"], counts["highlights"]),
        defensiveEventRecall=ratio(counts["kept_defensive_events"], counts["defensive_events"]),
        clipTimingQuality=ratio(counts["good_timing_quality_clips"], counts["timing_quality_clips"]),
        shotOutcomeEvidenceQuality=ratio(
            counts["good_shot_outcome_evidence_clips"],
            counts["shot_outcome_evidence_clips"],
        ),
        uncertainReviewCount=counts["uncertain_review"],
        selectedTeamHighlightCount=counts["selected_team_highlights"],
        defensiveEventCount=counts["defensive_events"],
        timingQualityClipCount=counts["timing_quality_clips"],
        badTimingClipCount=counts["timing_quality_clips"] - counts["good_timing_quality_clips"],
        shotOutcomeEvidenceClipCount=counts["shot_outcome_evidence_clips"],
        badShotOutcomeEvidenceCount=(
            counts["shot_outcome_evidence_clips"] - counts["good_shot_outcome_evidence_clips"]
        ),
        selectedTeamBlockCount=counts["selected_team_blocks"],
        selectedTeamStealCount=counts["selected_team_steals"],
        selectedTeamEvidenceClipCount=counts["selected_team_evidence_predictions"],
        badSelectedTeamEvidenceCount=(
            counts["selected_team_evidence_predictions"] - counts["good_selected_team_evidence_predictions"]
        ),
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
        "outcome": expected.get("outcome") or expected.get("shotOutcome") or expected.get("result"),
    }
    native_shot_signals = prediction.get("nativeShotSignals")
    if not isinstance(native_shot_signals, dict):
        native_shot_signals = {}
    shot_result_evidence = prediction.get("shotResultEvidence")
    if not isinstance(shot_result_evidence, dict):
        shot_result_evidence = {}
    shot_tracking_evidence = prediction.get("shotTrackingEvidence")
    if not isinstance(shot_tracking_evidence, dict):
        shot_tracking_evidence = {}
    quality_signals = prediction.get("qualitySignals")
    if not isinstance(quality_signals, dict):
        quality_signals = {}
    team_evidence = prediction.get("teamEvidence")
    if not isinstance(team_evidence, dict):
        team_evidence = {}
    normalized_prediction = {
        "keep": bool(prediction.get("keep") if "keep" in prediction else prediction.get("shouldAutoKeep")),
        "includeForReview": bool(prediction.get("includeForReview", prediction.get("keep", prediction.get("shouldAutoKeep", False)))),
        "teamId": prediction.get("teamId") or team_attribution.get("teamId"),
        "teamConfidence": prediction.get("teamConfidence") or team_attribution.get("confidence"),
        "teamAttributionStatus": prediction.get("teamAttributionStatus") or team_attribution.get("status"),
        "teamEvidenceStatus": string_or_none(team_evidence.get("status")),
        "teamEvidenceBacked": team_evidence.get("evidenceBacked") if isinstance(team_evidence.get("evidenceBacked"), bool) else None,
        "teamEvidenceFrameRefCount": number_or_none(team_evidence.get("frameRefCount")),
        "teamEvidenceRoleGroupCount": number_or_none(team_evidence.get("roleGroupCount")),
        "teamEvidenceFrameRefs": string_list(prediction.get("evidenceFrameRefs") or team_attribution.get("evidenceFrameRefs")),
        "teamEvidenceRoleGroups": string_list(prediction.get("evidenceRoleGroups") or team_attribution.get("evidenceRoleGroups")),
        "eventType": prediction.get("eventType") or prediction.get("basketballEvent") or prediction.get("label") or normalized_expected["eventType"],
        "start": number_or_none(prediction.get("start", raw_clip.get("start"))),
        "end": number_or_none(prediction.get("end", raw_clip.get("end"))),
        "duration": number_or_none(prediction.get("duration", prediction.get("durationSeconds", raw_clip.get("duration", raw_clip.get("durationSeconds"))))),
        "eventCenter": number_or_none(prediction.get("eventCenter", raw_clip.get("eventCenter"))),
        "nativeShotTimingWindowOk": native_timing_window_ok(prediction),
        "outcome": prediction.get("outcome") or prediction.get("basketballOutcome") or native_shot_signals.get("outcome"),
        "outcomeEvidenceSource": prediction.get("outcomeEvidenceSource") or native_shot_signals.get("outcomeEvidenceSource"),
        "outcomeReliabilityScore": prediction.get("outcomeReliabilityScore") or native_shot_signals.get("outcomeReliabilityScore"),
        "nativeShotSignals": native_shot_signals,
        "shotResultEvidence": shot_result_evidence,
        "shotTrackingEvidence": shot_tracking_evidence,
        "qualitySignals": quality_signals,
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
        ("selectedTeamEvidenceQuality", metrics.selectedTeamEvidenceQuality, thresholds.selectedTeamEvidenceQuality),
        ("selectedTeamRecallWithUncertain", metrics.selectedTeamRecallWithUncertain, thresholds.selectedTeamRecallWithUncertain),
        ("highlightPrecision", metrics.highlightPrecision, thresholds.highlightPrecision),
        ("highlightRecall", metrics.highlightRecall, thresholds.highlightRecall),
        ("defensiveEventRecall", metrics.defensiveEventRecall, thresholds.defensiveEventRecall),
        ("clipTimingQuality", metrics.clipTimingQuality, thresholds.clipTimingQuality),
        (
            "shotOutcomeEvidenceQuality",
            metrics.shotOutcomeEvidenceQuality,
            thresholds.shotOutcomeEvidenceQuality,
        ),
    )
    for name, value, minimum in checks:
        if value < minimum:
            failures.append(f"{name} {value:.3f} is below required {minimum:.3f}.")
    coverage_checks = (
        ("selectedTeamDefensiveEventCoverage", metrics.defensiveEventCount, thresholds.minSelectedTeamDefensiveEvents),
        ("selectedTeamBlockCoverage", metrics.selectedTeamBlockCount, thresholds.minSelectedTeamBlocks),
        ("selectedTeamStealCoverage", metrics.selectedTeamStealCount, thresholds.minSelectedTeamSteals),
    )
    for name, value, minimum in coverage_checks:
        if value < minimum:
            failures.append(f"{name} {value} is below required {minimum}.")
    return failures


def team_attribution_evidence_is_valid(prediction: dict[str, Any]) -> bool:
    evidence_status = normalize_event_type(prediction.get("teamEvidenceStatus"))
    if evidence_status and evidence_status != "evidence_backed":
        return False
    if prediction.get("teamEvidenceBacked") is False:
        return False
    frame_ref_count = number_or_none(prediction.get("teamEvidenceFrameRefCount"))
    if frame_ref_count is not None and frame_ref_count < MIN_EVAL_TEAM_EVIDENCE_FRAME_REFS:
        return False
    role_group_count = number_or_none(prediction.get("teamEvidenceRoleGroupCount"))
    if role_group_count is not None and role_group_count < MIN_EVAL_TEAM_EVIDENCE_ROLE_GROUPS:
        return False
    return (
        len(string_set(prediction.get("teamEvidenceFrameRefs"))) >= MIN_EVAL_TEAM_EVIDENCE_FRAME_REFS
        and len(string_set(prediction.get("teamEvidenceRoleGroups"))) >= MIN_EVAL_TEAM_EVIDENCE_ROLE_GROUPS
    )


def defensive_event_subtype(event_type: str) -> str | None:
    normalized = normalize_event_type(event_type)
    if "block" in normalized or "blocked" in normalized:
        return "block"
    if "steal" in normalized or "strip" in normalized:
        return "steal"
    if "turnover" in normalized or normalized in {"forced_to", "forced_turnover"}:
        return "forced_turnover"
    if "stop" in normalized:
        return "defensive_stop"
    return None


def expected_outcome_for_clip(expected: dict[str, Any]) -> str | None:
    explicit = normalize_shot_outcome(expected.get("outcome") or expected.get("shotOutcome") or expected.get("result"))
    if explicit is not None:
        return explicit
    event_type = normalize_event_type(expected.get("eventType"))
    if any(token in event_type for token in ("miss", "missed")):
        return "missed"
    if "block" in event_type or "blocked" in event_type:
        return "blocked"
    if any(token in event_type for token in ("made", "bucket", "basket", "dunk", "three", "3pt")):
        return "made"
    return None


def shot_outcome_evidence_is_valid(prediction: dict[str, Any], expected_outcome: str) -> bool:
    predicted_outcome = normalize_shot_outcome(prediction.get("outcome"))
    if predicted_outcome != expected_outcome:
        return False

    result_evidence = prediction.get("shotResultEvidence")
    if not isinstance(result_evidence, dict):
        result_evidence = {}
    tracking_evidence = prediction.get("shotTrackingEvidence")
    if not isinstance(tracking_evidence, dict):
        tracking_evidence = {}
    quality_signals = prediction.get("qualitySignals")
    if not isinstance(quality_signals, dict):
        quality_signals = {}

    evidence_confidence = number_or_default(result_evidence.get("outcomeConfidence"), 0.0)
    if evidence_confidence < MIN_EVAL_SHOT_OUTCOME_CONFIDENCE:
        return False
    if str(prediction.get("outcomeEvidenceSource") or "").strip().lower() == "label_only":
        return False
    reliability_score = number_or_none(prediction.get("outcomeReliabilityScore"))
    if reliability_score is not None and reliability_score < MIN_EVAL_OUTCOME_RELIABILITY:
        return False

    rim_result = str(result_evidence.get("rimResultEvidence") or "").strip().lower()
    rim_sequence = str(result_evidence.get("rimEntrySequence") or "").strip().lower()
    rim_sequence_confidence = number_or_default(result_evidence.get("rimEntrySequenceConfidence"), 0.0)
    approach_role = normalize_event_type(result_evidence.get("ballApproachFrameRole"))
    rim_entry_role = normalize_event_type(result_evidence.get("rimEntryFrameRole"))
    below_rim_role = normalize_event_type(result_evidence.get("ballBelowRimOrNetFrameRole"))
    ball_roles = string_set(tracking_evidence.get("ballVisibleFrameRoles"))
    rim_roles = string_set(tracking_evidence.get("rimVisibleFrameRoles"))
    result_role = normalize_event_type(tracking_evidence.get("resultFrameRole"))
    entry_role = normalize_event_type(tracking_evidence.get("ballEntersRimFrameRole"))
    trajectory = str(tracking_evidence.get("trajectoryContinuity") or "").strip().lower()

    if expected_outcome == "made":
        return (
            rim_result == "made_visible"
            and rim_sequence == "visible_entry"
            and rim_sequence_confidence >= MIN_EVAL_RIM_ENTRY_SEQUENCE_CONFIDENCE
            and approach_role in MADE_APPROACH_FRAME_ROLES
            and rim_entry_role in MADE_ENTRY_FRAME_ROLES
            and below_rim_role in MADE_FOLLOW_THROUGH_FRAME_ROLES
            and entry_role in MADE_ENTRY_FRAME_ROLES
            and result_role in MADE_ENTRY_FRAME_ROLES | MADE_FOLLOW_THROUGH_FRAME_ROLES
            and len(ball_roles & MADE_BALL_FLIGHT_FRAME_ROLES) >= 2
            and bool(rim_roles & (MADE_ENTRY_FRAME_ROLES | MADE_FOLLOW_THROUGH_FRAME_ROLES))
            and trajectory == "continuous"
            and quality_signals.get("ballPathVisible") is True
            and quality_signals.get("rimResultVisible") is True
        )
    if expected_outcome == "missed":
        return (
            rim_result == "clear_miss"
            and rim_sequence in {"visible_miss", "unclear"}
            and (bool(result_role) or bool(rim_roles))
            and quality_signals.get("ballPathVisible") is True
            and quality_signals.get("rimResultVisible") is True
        )
    if expected_outcome == "blocked":
        defensive_roles = {"challenge", "defenseoutcome", "possessionchange", "eventcenter"}
        return (
            rim_result == "blocked"
            and rim_sequence == "blocked"
            and bool(ball_roles & defensive_roles)
            and quality_signals.get("ballPathVisible") is True
        )
    return False


def normalize_shot_outcome(value: Any) -> str | None:
    text = normalize_event_type(value)
    if text in {"made", "make", "bucket", "basket", "score", "scored", "visible_entry"}:
        return "made"
    if text in {"miss", "missed", "clear_miss", "visible_miss"}:
        return "missed"
    if text in {"block", "blocked", "blocked_shot"}:
        return "blocked"
    return None


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


def string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {normalize_event_type(item) for item in value if normalize_event_type(item)}


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = string_or_none(item)
        if text is None or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


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

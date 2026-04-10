from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.datasets import ANNOTATION_SCHEMA_VERSION
from services.inference.scripts.run_eval_report import load_eval_rows, load_predictions


HARD_NEGATIVES = [
    {
        "clipId": "negative-deadball-001",
        "sourceDomain": "hard_negative",
        "expectedLabel": "uncertain",
        "expectedEventFamily": "other",
        "expectedShotSubtype": None,
        "expectedOutcome": "uncertain",
        "ballVisible": True,
        "hoopVisible": False,
        "ballNearRim": 0.05,
        "ballThroughHoopLikelihood": 0.01,
        "possessionChangeLikelihood": 0.08,
        "transitionLikelihood": 0.05,
        "teacherConfidence": 0.72,
        "reviewerNotes": "Dead-ball reset with no highlight-worthy action.",
        "signalAuditFocus": "no coherent ball-rim-player relation should abstain",
    },
    {
        "clipId": "negative-inbound-001",
        "sourceDomain": "hard_negative",
        "expectedLabel": "uncertain",
        "expectedEventFamily": "other",
        "expectedShotSubtype": None,
        "expectedOutcome": "uncertain",
        "ballVisible": True,
        "hoopVisible": False,
        "ballNearRim": 0.07,
        "ballThroughHoopLikelihood": 0.02,
        "possessionChangeLikelihood": 0.12,
        "transitionLikelihood": 0.09,
        "teacherConfidence": 0.7,
        "reviewerNotes": "Inbound pass with no shot attempt.",
        "signalAuditFocus": "ball visible, hoop irrelevant, no release cue",
    },
    {
        "clipId": "negative-dribble-only-001",
        "sourceDomain": "hard_negative",
        "expectedLabel": "uncertain",
        "expectedEventFamily": "other",
        "expectedShotSubtype": None,
        "expectedOutcome": "uncertain",
        "ballVisible": True,
        "hoopVisible": True,
        "ballNearRim": 0.09,
        "ballThroughHoopLikelihood": 0.03,
        "possessionChangeLikelihood": 0.14,
        "transitionLikelihood": 0.07,
        "teacherConfidence": 0.68,
        "reviewerNotes": "Dribble sequence only; no finish, no pass, no turnover.",
        "signalAuditFocus": "ball motion without rim relation should stay uncertain",
    },
    {
        "clipId": "negative-replay-001",
        "sourceDomain": "hard_negative",
        "expectedLabel": "uncertain",
        "expectedEventFamily": "other",
        "expectedShotSubtype": None,
        "expectedOutcome": "uncertain",
        "ballVisible": False,
        "hoopVisible": True,
        "ballNearRim": 0.02,
        "ballThroughHoopLikelihood": 0.0,
        "possessionChangeLikelihood": 0.03,
        "transitionLikelihood": 0.02,
        "teacherConfidence": 0.64,
        "reviewerNotes": "Replay / scoreboard shot only.",
        "signalAuditFocus": "camera replays should not be treated as play events",
    },
    {
        "clipId": "negative-celebration-001",
        "sourceDomain": "hard_negative",
        "expectedLabel": "uncertain",
        "expectedEventFamily": "other",
        "expectedShotSubtype": None,
        "expectedOutcome": "uncertain",
        "ballVisible": False,
        "hoopVisible": False,
        "ballNearRim": 0.01,
        "ballThroughHoopLikelihood": 0.0,
        "possessionChangeLikelihood": 0.01,
        "transitionLikelihood": 0.02,
        "teacherConfidence": 0.66,
        "reviewerNotes": "Celebration after the play is over.",
        "signalAuditFocus": "players reacting, no live possession",
    },
    {
        "clipId": "negative-camera-pan-001",
        "sourceDomain": "hard_negative",
        "expectedLabel": "uncertain",
        "expectedEventFamily": "other",
        "expectedShotSubtype": None,
        "expectedOutcome": "uncertain",
        "ballVisible": False,
        "hoopVisible": False,
        "ballNearRim": 0.0,
        "ballThroughHoopLikelihood": 0.0,
        "possessionChangeLikelihood": 0.0,
        "transitionLikelihood": 0.0,
        "teacherConfidence": 0.58,
        "reviewerNotes": "Camera pan across the crowd / benches.",
        "signalAuditFocus": "visual motion without basketball structure",
    },
    {
        "clipId": "negative-halfcourt-setup-001",
        "sourceDomain": "hard_negative",
        "expectedLabel": "uncertain",
        "expectedEventFamily": "other",
        "expectedShotSubtype": None,
        "expectedOutcome": "uncertain",
        "teacherEventFamily": "transition",
        "teacherOutcome": "uncertain",
        "teacherShotSubtype": None,
        "teacherDisplayLabel": "Fast Break",
        "teacherConfidence": 0.84,
        "ballVisible": True,
        "hoopVisible": True,
        "ballNearRim": 0.12,
        "ballThroughHoopLikelihood": 0.02,
        "possessionChangeLikelihood": 0.16,
        "transitionLikelihood": 0.11,
        "teacherConfidence": 0.7,
        "reviewerNotes": "Half-court setup without a shot or turnover.",
        "signalAuditFocus": "setup should not be forced into a highlight",
    },
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[3]
    eval_base = repo_root / "services" / "inference" / "evals"

    eval_rows = load_eval_rows(eval_base / "basketball_eval_set.json")
    predictions = load_predictions(eval_base / "baseline_predictions.json")

    gold_rows = [build_gold_row(row, predictions[row.clip_id]) for row in eval_rows]
    gold_rows.extend(build_hard_negative_row(spec) for spec in HARD_NEGATIVES)

    silver_rows = [build_silver_row(row) for row in gold_rows]
    disagreement_rows = build_disagreement_queue(gold_rows, silver_rows)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "gold_annotations.jsonl", gold_rows)
    write_jsonl(output_dir / "silver_teacher_annotations.jsonl", silver_rows)
    write_jsonl(output_dir / "disagreement_queue.jsonl", disagreement_rows)

    print(output_dir / "gold_annotations.jsonl")
    print(output_dir / "silver_teacher_annotations.jsonl")
    print(output_dir / "disagreement_queue.jsonl")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build gold, silver, and disagreement probe datasets.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets",
    )
    return parser.parse_args(argv)


def build_gold_row(row: Any, prediction: Any) -> dict[str, Any]:
    source_domain = "benchmark_eval"
    runtime = build_runtime_outputs(row.clip_id, prediction, row.expected_label, row.expected_event_family, row.expected_shot_subtype, row.expected_outcome, row.signal_audit_focus)
    teacher = build_teacher_outputs(
        clip_id=row.clip_id,
        source_domain=source_domain,
        event_family=row.expected_event_family,
        outcome=row.expected_outcome,
        shot_subtype=row.expected_shot_subtype,
        label=row.expected_label,
        signal_audit_focus=row.signal_audit_focus,
        runtime=runtime,
        source_duration_seconds=row.source_duration_seconds,
    )
    return {
        "clipId": row.clip_id,
        "sourceDomain": source_domain,
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "eventFamily": row.expected_event_family,
        "outcome": row.expected_outcome,
        "shotSubtype": row.expected_shot_subtype,
        "ballVisible": _ball_visible_for_family(row.expected_event_family, row.expected_label),
        "hoopVisible": _hoop_visible_for_family(row.expected_event_family, row.expected_label),
        "ballNearRim": _signal_value(row.expected_event_family, row.expected_label, row.expected_outcome, "ballNearRim"),
        "ballThroughHoopLikelihood": _signal_value(row.expected_event_family, row.expected_label, row.expected_outcome, "ballThroughHoopLikelihood"),
        "possessionChangeLikelihood": _signal_value(row.expected_event_family, row.expected_label, row.expected_outcome, "possessionChangeLikelihood"),
        "transitionLikelihood": _signal_value(row.expected_event_family, row.expected_label, row.expected_outcome, "transitionLikelihood"),
        "teacherConfidence": teacher["confidence"],
        "humanVerified": True,
        "reviewerNotes": row.notes,
        "rawRuntimeOutputs": runtime,
        "rawTeacherOutputs": teacher,
    }


def build_hard_negative_row(spec: dict[str, Any]) -> dict[str, Any]:
    runtime = {
        "modelVersion": "videomae:MCG-NJU/videomae-base-finetuned-kinetics",
        "label": "Highlight",
        "confidence": 0.42,
        "eventFamily": "other",
        "shotSubtype": None,
        "outcome": "uncertain",
        "topKLabels": [
            {"label": "highlight", "confidence": 0.42},
            {"label": "uncertain", "confidence": 0.31},
            {"label": "steal", "confidence": 0.09},
        ],
        "videoMAE": build_topk_payload(
            model_version="videomae:MCG-NJU/videomae-base-finetuned-kinetics",
            labels=["highlight", "uncertain", "steal"],
            confidences=[0.42, 0.31, 0.09],
        ),
        "xclip": build_topk_payload(
            model_version="xclip:microsoft/xclip-base-patch32",
            labels=["highlight", "uncertain", "transition"],
            confidences=[0.38, 0.29, 0.11],
        ),
        "structuredSignals": {
            "ballNearRim": spec["ballNearRim"],
            "ballAboveRim": 0.0,
            "ballArcApex": 0.08,
            "ballThroughHoopLikelihood": spec["ballThroughHoopLikelihood"],
            "possessionChangeLikelihood": spec["possessionChangeLikelihood"],
            "playerToRimDistance": 0.72,
            "ballCarrierSpeed": 0.11,
            "transitionSpeedScore": spec["transitionLikelihood"],
            "defenderProximityAtShot": 0.05,
            "shotReleaseCandidate": 0.05,
            "samePlayContinuityScore": 0.14,
        },
    }
    teacher = build_teacher_outputs(
        clip_id=spec["clipId"],
        source_domain=spec["sourceDomain"],
        event_family=spec.get("teacherEventFamily", "other"),
        outcome=spec.get("teacherOutcome", "uncertain"),
        shot_subtype=spec.get("teacherShotSubtype"),
        label=spec.get("teacherDisplayLabel", "uncertain"),
        signal_audit_focus=spec["signalAuditFocus"],
        runtime=runtime,
        source_duration_seconds=None,
        teacher_confidence_override=spec.get("teacherConfidence"),
        display_label_override=spec.get("teacherDisplayLabel"),
    )
    return {
        "clipId": spec["clipId"],
        "sourceDomain": spec["sourceDomain"],
        "schemaVersion": ANNOTATION_SCHEMA_VERSION,
        "eventFamily": "other",
        "outcome": "uncertain",
        "shotSubtype": None,
        "ballVisible": spec["ballVisible"],
        "hoopVisible": spec["hoopVisible"],
        "ballNearRim": spec["ballNearRim"],
        "ballThroughHoopLikelihood": spec["ballThroughHoopLikelihood"],
        "possessionChangeLikelihood": spec["possessionChangeLikelihood"],
        "transitionLikelihood": spec["transitionLikelihood"],
        "teacherConfidence": spec["teacherConfidence"],
        "humanVerified": True,
        "reviewerNotes": spec["reviewerNotes"],
        "rawRuntimeOutputs": runtime,
        "rawTeacherOutputs": teacher,
    }


def build_silver_row(gold_row: dict[str, Any]) -> dict[str, Any]:
    teacher = deepcopy(gold_row["rawTeacherOutputs"])
    runtime = deepcopy(gold_row["rawRuntimeOutputs"])
    return {
        "clipId": gold_row["clipId"],
        "sourceDomain": "teacher_pseudo",
        "schemaVersion": gold_row["schemaVersion"],
        "eventFamily": teacher.get("eventFamily") or gold_row["eventFamily"],
        "outcome": teacher.get("outcome") or gold_row["outcome"],
        "shotSubtype": teacher.get("shotSubtype") if teacher.get("shotSubtype") is not None else gold_row["shotSubtype"],
        "ballVisible": gold_row["ballVisible"],
        "hoopVisible": gold_row["hoopVisible"],
        "ballNearRim": gold_row["ballNearRim"],
        "ballThroughHoopLikelihood": gold_row["ballThroughHoopLikelihood"],
        "possessionChangeLikelihood": gold_row["possessionChangeLikelihood"],
        "transitionLikelihood": gold_row["transitionLikelihood"],
        "teacherConfidence": teacher.get("confidence", gold_row["teacherConfidence"]),
        "humanVerified": False,
        "reviewerNotes": "Teacher pseudo-label retained separately from human gold.",
        "rawRuntimeOutputs": runtime,
        "rawTeacherOutputs": teacher,
    }


def build_runtime_outputs(
    clip_id: str,
    prediction: Any,
    label: str,
    event_family: str,
    shot_subtype: Any,
    outcome: str,
    signal_audit_focus: str,
) -> dict[str, Any]:
    runtime_outcome = outcome
    runtime_label = label if label != "uncertain" else "Highlight"
    runtime_shot_subtype = shot_subtype
    if clip_id in {"eval-layup-002", "eval-miss-002"} and outcome == "missed":
        runtime_outcome = "made"
        runtime_label = "Made Shot"
        runtime_shot_subtype = shot_subtype or "jumper"

    top_k = list(prediction.top_k_labels or [])
    top_k_payload = build_topk_payload(
        model_version="videomae:MCG-NJU/videomae-base-finetuned-kinetics",
        labels=top_k,
        confidences=_descending_confidences(float(prediction.confidence), len(top_k)),
    )
    xclip_labels = _xclip_labels_for(runtime_label, event_family, runtime_outcome, runtime_shot_subtype)
    xclip_payload = build_topk_payload(
        model_version="xclip:microsoft/xclip-base-patch32",
        labels=xclip_labels,
        confidences=_descending_confidences(max(float(prediction.confidence) - 0.05, 0.35), len(xclip_labels)),
    )
    structured_signals = {
        "ballNearRim": _signal_value(event_family, label, outcome, "ballNearRim"),
        "ballAboveRim": _signal_value(event_family, label, outcome, "ballAboveRim"),
        "ballArcApex": _signal_value(event_family, label, outcome, "ballArcApex"),
        "ballThroughHoopLikelihood": _signal_value(event_family, label, outcome, "ballThroughHoopLikelihood"),
        "possessionChangeLikelihood": _signal_value(event_family, label, outcome, "possessionChangeLikelihood"),
        "playerToRimDistance": _signal_value(event_family, label, outcome, "playerToRimDistance"),
        "ballCarrierSpeed": _signal_value(event_family, label, outcome, "ballCarrierSpeed"),
        "transitionSpeedScore": _signal_value(event_family, label, outcome, "transitionLikelihood"),
        "defenderProximityAtShot": _signal_value(event_family, label, outcome, "defenderProximityAtShot"),
        "shotReleaseCandidate": _signal_value(event_family, label, outcome, "shotReleaseCandidate"),
        "samePlayContinuityScore": _signal_value(event_family, label, outcome, "samePlayContinuityScore"),
    }
    return {
        "modelVersion": "videomae:MCG-NJU/videomae-base-finetuned-kinetics",
        "promptSetVersion": "xclip-bball-v2",
        "label": runtime_label,
        "confidence": float(prediction.confidence),
        "eventFamily": event_family,
        "shotSubtype": runtime_shot_subtype,
        "outcome": runtime_outcome,
        "topKLabels": top_k,
        "videoMAE": top_k_payload,
        "xclip": xclip_payload,
        "structuredSignals": structured_signals,
        "signalAuditFocus": signal_audit_focus,
        "clipDurationSeconds": prediction.clip_duration_seconds,
        "eventCenterSeconds": prediction.event_center_seconds,
        "preRollSeconds": prediction.pre_roll_seconds,
        "postRollSeconds": prediction.post_roll_seconds,
        "windowPolicyVersion": prediction.window_policy_version,
        "wasMerged": prediction.was_merged,
        "sourceEventCount": prediction.source_event_count,
        "isUncertain": prediction.is_uncertain or runtime_outcome == "uncertain",
    }


def build_teacher_outputs(
    *,
    clip_id: str,
    source_domain: str,
    event_family: str,
    outcome: str,
    shot_subtype: Any,
    label: str,
    signal_audit_focus: str,
    runtime: dict[str, Any],
    source_duration_seconds: float | None,
    teacher_confidence_override: float | None = None,
    display_label_override: str | None = None,
) -> dict[str, Any]:
    evidence = [signal_audit_focus]
    if runtime["structuredSignals"]["ballNearRim"] >= 0.7:
        evidence.append("ball near rim")
    if runtime["structuredSignals"]["ballThroughHoopLikelihood"] >= 0.6:
        evidence.append("through-hoop evidence")
    if runtime["structuredSignals"]["possessionChangeLikelihood"] >= 0.7:
        evidence.append("possession change evidence")
    if runtime["structuredSignals"]["transitionSpeedScore"] >= 0.7:
        evidence.append("transition speed evidence")

    confidence = teacher_confidence_override if teacher_confidence_override is not None else _teacher_confidence(event_family, outcome, source_domain)
    suggestion = display_label_override or _display_label_suggestion(event_family, outcome, shot_subtype, label)
    if clip_id == "eval-miss-001":
        suggestion = "Made Shot"
        confidence = max(confidence, 0.86)
        outcome = "made"
        evidence.append("teacher override seeded for corrected-example audit")
    return {
        "modelVersion": "teacher:qwen-basketball-teacher-v1",
        "promptVersion": "qwen-basketball-teacher-v1",
        "clipId": clip_id,
        "sourceDomain": source_domain,
        "eventFamily": event_family,
        "outcome": outcome,
        "shotSubtype": shot_subtype,
        "displayLabelSuggestion": suggestion,
        "confidence": confidence,
        "evidence": evidence,
        "notes": f"Teacher audit seed for {source_domain}",
        "sourceDurationSeconds": source_duration_seconds,
    }


def build_topk_payload(*, model_version: str, labels: list[str], confidences: list[float]) -> dict[str, Any]:
    items = []
    for label, confidence in zip(labels, confidences):
        items.append({"label": label, "confidence": round(min(max(confidence, 0.01), 0.999), 4), "modelVersion": model_version})
    return {"modelVersion": model_version, "topK": items}


def build_disagreement_queue(gold_rows: list[dict[str, Any]], silver_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    silver_by_id = {row["clipId"]: row for row in silver_rows}
    queue: list[dict[str, Any]] = []
    for row in gold_rows:
        teacher = silver_by_id[row["clipId"]]["rawTeacherOutputs"]
        runtime = row["rawRuntimeOutputs"]
        reasons = []
        priority = 0.0
        if runtime.get("label") == "Highlight":
            reasons.append("app_facing_highlight_only")
            priority += 0.35
        if runtime.get("outcome") != teacher.get("outcome"):
            reasons.append("runtime_teacher_outcome_disagreement")
            priority += 0.25
        if runtime.get("eventFamily") != teacher.get("eventFamily"):
            reasons.append("runtime_teacher_family_disagreement")
            priority += 0.2
        if runtime.get("shotSubtype") != teacher.get("shotSubtype"):
            reasons.append("runtime_teacher_subtype_disagreement")
            priority += 0.15
        if row["outcome"] == "missed" and runtime.get("outcome") == "made":
            reasons.append("miss_vs_made_disagreement")
            priority += 0.35
        if row["shotSubtype"] is None and row["ballNearRim"] >= 0.6:
            reasons.append("strong_ball_hoop_without_subtype")
            priority += 0.2
        if teacher.get("confidence", 0.0) >= 0.8 and float(runtime.get("confidence", 0.0)) <= 0.65:
            reasons.append("high_teacher_low_runtime")
            priority += 0.2
        if row["sourceDomain"] == "hard_negative":
            reasons.append("hard_negative")
            priority += 0.1
        if reasons:
            queue.append(
                {
                    "clipId": row["clipId"],
                    "sourceDomain": row["sourceDomain"],
                    "schemaVersion": row["schemaVersion"],
                    "priorityScore": round(min(priority, 1.0), 3),
                    "reasons": unique_ordered(reasons),
                    "gold": {
                        "eventFamily": row["eventFamily"],
                        "outcome": row["outcome"],
                        "shotSubtype": row["shotSubtype"],
                    },
                    "runtime": {
                        "label": runtime.get("label"),
                        "eventFamily": runtime.get("eventFamily"),
                        "outcome": runtime.get("outcome"),
                        "shotSubtype": runtime.get("shotSubtype"),
                        "confidence": runtime.get("confidence"),
                    },
                    "teacher": {
                        "eventFamily": teacher.get("eventFamily"),
                        "outcome": teacher.get("outcome"),
                        "shotSubtype": teacher.get("shotSubtype"),
                        "confidence": teacher.get("confidence"),
                    },
                    "reviewerNotes": row["reviewerNotes"],
                }
            )
    queue.sort(key=lambda item: (-float(item["priorityScore"]), item["clipId"]))
    return queue


def _teacher_confidence(event_family: str, outcome: str, source_domain: str) -> float:
    if source_domain == "hard_negative":
        return 0.72
    if event_family == "shot_attempt" and outcome == "made":
        return 0.93
    if event_family == "shot_attempt" and outcome == "missed":
        return 0.88
    if outcome == "blocked":
        return 0.86
    if event_family == "turnover":
        return 0.84
    if event_family == "transition":
        return 0.81
    return 0.7


def _display_label_suggestion(event_family: str, outcome: str, shot_subtype: Any, label: str) -> str:
    if event_family == "turnover":
        return "Steal"
    if event_family == "transition":
        return "Fast Break"
    if event_family == "defensive_event":
        return "Block" if outcome == "blocked" else "Highlight"
    if outcome == "made":
        if shot_subtype == "three":
            return "Three Pointer"
        if shot_subtype in {"dunk", "layup", "jumper", "putback"}:
            return "Made Shot"
        return label.title()
    if outcome == "missed":
        return "Highlight"
    return "Highlight"


def _signal_value(event_family: str, label: str, outcome: str, name: str) -> float:
    if event_family == "shot_attempt":
        base = {
            "ballNearRim": 0.82,
            "ballAboveRim": 0.54 if outcome == "made" else 0.22,
            "ballArcApex": 0.71,
            "ballThroughHoopLikelihood": 0.88 if outcome == "made" else 0.14 if outcome == "missed" else 0.34,
            "possessionChangeLikelihood": 0.1,
            "playerToRimDistance": 0.18 if label in {"dunk", "layup", "putback"} else 0.31,
            "ballCarrierSpeed": 0.34,
            "transitionLikelihood": 0.12,
            "defenderProximityAtShot": 0.28 if outcome != "made" else 0.18,
            "shotReleaseCandidate": 0.88,
            "samePlayContinuityScore": 0.42,
        }
        return base[name]
    if event_family == "turnover":
        base = {
            "ballNearRim": 0.12,
            "ballAboveRim": 0.0,
            "ballArcApex": 0.14,
            "ballThroughHoopLikelihood": 0.02,
            "possessionChangeLikelihood": 0.89,
            "playerToRimDistance": 0.7,
            "ballCarrierSpeed": 0.47,
            "transitionLikelihood": 0.26,
            "defenderProximityAtShot": 0.22,
            "shotReleaseCandidate": 0.1,
            "samePlayContinuityScore": 0.31,
        }
        return base[name]
    if event_family == "defensive_event":
        base = {
            "ballNearRim": 0.68,
            "ballAboveRim": 0.18,
            "ballArcApex": 0.22,
            "ballThroughHoopLikelihood": 0.08,
            "possessionChangeLikelihood": 0.34,
            "playerToRimDistance": 0.24,
            "ballCarrierSpeed": 0.23,
            "transitionLikelihood": 0.18,
            "defenderProximityAtShot": 0.79,
            "shotReleaseCandidate": 0.31,
            "samePlayContinuityScore": 0.24,
        }
        return base[name]
    if event_family == "transition":
        base = {
            "ballNearRim": 0.1,
            "ballAboveRim": 0.02,
            "ballArcApex": 0.08,
            "ballThroughHoopLikelihood": 0.02,
            "possessionChangeLikelihood": 0.46,
            "playerToRimDistance": 0.58,
            "ballCarrierSpeed": 0.83,
            "transitionLikelihood": 0.92,
            "defenderProximityAtShot": 0.13,
            "shotReleaseCandidate": 0.18,
            "samePlayContinuityScore": 0.63,
        }
        return base[name]
    base = {
        "ballNearRim": 0.08,
        "ballAboveRim": 0.02,
        "ballArcApex": 0.06,
        "ballThroughHoopLikelihood": 0.01,
        "possessionChangeLikelihood": 0.06,
        "playerToRimDistance": 0.7,
        "ballCarrierSpeed": 0.12,
        "transitionLikelihood": 0.07,
        "defenderProximityAtShot": 0.08,
        "shotReleaseCandidate": 0.05,
        "samePlayContinuityScore": 0.13,
    }
    return base[name]


def _ball_visible_for_family(event_family: str, label: str) -> bool:
    return event_family != "other" or label == "uncertain"


def _hoop_visible_for_family(event_family: str, label: str) -> bool:
    return event_family in {"shot_attempt", "defensive_event"} or label in {"dunk", "layup", "jumper", "three", "putback", "miss"}


def _xclip_labels_for(label: str, event_family: str, outcome: str, shot_subtype: Any) -> list[str]:
    if event_family == "turnover":
        return ["steal", "block", "fast break"]
    if event_family == "transition":
        return ["fast break", "layup", "dunk"]
    if event_family == "defensive_event":
        return ["block", "steal", "fast break"]
    if outcome == "missed":
        return ["miss", shot_subtype or "jumper", "three"]
    if outcome == "made":
        labels = [shot_subtype or label, "made shot", "highlight"]
        if shot_subtype == "three":
            labels = ["three", "jumper", "highlight"]
        return labels
    return ["highlight", "uncertain", "other"]


def _descending_confidences(start: float, count: int) -> list[float]:
    if count <= 0:
        return []
    values: list[float] = []
    current = min(max(start, 0.05), 0.99)
    for index in range(count):
        values.append(round(min(max(current - (index * 0.12), 0.01), 0.999), 4))
    return values


def build_topk_payload(*, model_version: str, labels: list[str], confidences: list[float]) -> dict[str, Any]:
    return {
        "modelVersion": model_version,
        "topK": [
            {"label": label, "confidence": confidence, "modelVersion": model_version}
            for label, confidence in zip(labels, confidences)
        ],
    }


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable


CANONICAL_LABELS = [
    "dunk",
    "layup",
    "jumper",
    "three",
    "putback",
    "block",
    "steal",
    "fast break",
    "miss",
]

EVENT_FAMILIES = ["shot_attempt", "turnover", "defensive_event", "transition", "other"]
SHOT_SUBTYPES = ["dunk", "layup", "jumper", "three", "putback", "unknown"]
OUTCOMES = ["made", "missed", "blocked", "uncertain"]

LABEL_SYNONYMS = {
    "three pointer": "three",
    "three-pointer": "three",
    "3 pointer": "three",
    "3-pointer": "three",
    "midrange jumper": "jumper",
    "mid-range jumper": "jumper",
    "shot": "jumper",
    "made shot": "jumper",
    "made": "jumper",
    "fastbreak": "fast break",
    "fast-break": "fast break",
    "highlight": "miss",
}

EVENT_FAMILY_SYNONYMS = {
    "defense": "defensive_event",
    "defensive": "defensive_event",
    "shot": "shot_attempt",
    "shot attempt": "shot_attempt",
    "turnover": "turnover",
    "transition": "transition",
    "other": "other",
}

SHOT_SUBTYPE_SYNONYMS = {
    "fast_break": "unknown",
    "fast break": "unknown",
    "unknown": "unknown",
}

OUTCOME_SYNONYMS = {
    "make": "made",
    "made": "made",
    "miss": "missed",
    "missed": "missed",
    "blocked": "blocked",
    "block": "blocked",
    "unknown": "uncertain",
    "n/a": "uncertain",
    "uncertain": "uncertain",
}

CLIP_MIN_DURATION_SECONDS = 3.5


@dataclass
class EvaluationRow:
    clip_id: str
    expected_label: str
    expected_event_family: str
    expected_shot_subtype: str
    expected_outcome: str
    source_ref: str
    notes: str = ""
    split: str = "train"
    source_duration_seconds: float | None = None
    signal_audit_focus: str = ""


@dataclass
class PredictionRow:
    clip_id: str
    label: str
    confidence: float
    top_k_labels: list[str]
    event_family: str
    shot_subtype: str
    outcome: str
    top_k_event_families: list[str]
    top_k_shot_subtypes: list[str]
    top_k_outcomes: list[str]
    clip_duration_seconds: float | None = None
    event_center_seconds: float | None = None
    pre_roll_seconds: float | None = None
    post_roll_seconds: float | None = None
    window_policy_version: str | None = None
    was_merged: bool = False
    source_event_count: int | None = None
    is_uncertain: bool = False


def main() -> int:
    args = parse_args()
    eval_rows = load_eval_rows(args.eval_set)
    predictions = load_predictions(args.predictions)
    report = build_report(eval_rows, predictions)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    md_path = output_dir / "report.md"

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(md_path)
    print(json_path)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a basketball eval report.")
    parser.add_argument("--eval-set", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_eval_rows(path: Path) -> list[EvaluationRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[EvaluationRow] = []
    for item in payload:
        rows.append(
            EvaluationRow(
                clip_id=str(item["clipId"]),
                expected_label=normalize_label(str(item["expectedLabel"])),
                expected_event_family=normalize_event_family(item.get("expectedEventFamily") or item.get("expectedEventType")),
                expected_shot_subtype=normalize_shot_subtype(item.get("expectedShotSubtype") or item.get("expectedShotType")),
                expected_outcome=normalize_outcome(item.get("expectedOutcome") or item.get("expectedMakeMiss")),
                source_ref=str(item.get("sourceRef", "")),
                notes=str(item.get("notes", "")),
                split=str(item.get("split", "train")),
                source_duration_seconds=to_optional_float(item.get("sourceDurationSeconds")),
                signal_audit_focus=str(item.get("signalAuditFocus", "")),
            )
        )
    return rows


def load_predictions(path: Path) -> dict[str, PredictionRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, PredictionRow] = {}
    for item in payload:
        clip_id = str(item["clipId"])
        label = normalize_label(str(item["label"]))
        top_k_labels = unique_in_order(normalize_label(str(value)) for value in item.get("topKLabels", []))
        event_family = normalize_event_family(item.get("eventFamily"))
        shot_subtype = normalize_shot_subtype(item.get("shotSubtype"))
        outcome = normalize_outcome(item.get("outcome"))
        if not event_family or not shot_subtype or not outcome:
            fallback_family, fallback_subtype, fallback_outcome = taxonomy_for_label(label)
            event_family = event_family or fallback_family
            shot_subtype = shot_subtype or fallback_subtype
            outcome = outcome or fallback_outcome

        if item.get("topKEventFamilies"):
            top_k_event_families = unique_in_order(normalize_event_family(value) for value in item["topKEventFamilies"])
        else:
            top_k_event_families = unique_in_order(taxonomy_for_label(value)[0] for value in top_k_labels)
        if item.get("topKShotSubtypes"):
            top_k_shot_subtypes = unique_in_order(normalize_shot_subtype(value) for value in item["topKShotSubtypes"])
        else:
            top_k_shot_subtypes = unique_in_order(taxonomy_for_label(value)[1] for value in top_k_labels)
        if item.get("topKOutcomes"):
            top_k_outcomes = unique_in_order(normalize_outcome(value) for value in item["topKOutcomes"])
        else:
            top_k_outcomes = unique_in_order(taxonomy_for_label(value)[2] for value in top_k_labels)

        result[clip_id] = PredictionRow(
            clip_id=clip_id,
            label=label,
            confidence=float(item.get("confidence", 0.0)),
            top_k_labels=top_k_labels,
            event_family=event_family,
            shot_subtype=shot_subtype,
            outcome=outcome,
            top_k_event_families=top_k_event_families,
            top_k_shot_subtypes=top_k_shot_subtypes,
            top_k_outcomes=top_k_outcomes,
            clip_duration_seconds=to_optional_float(item.get("clipDurationSeconds")),
            event_center_seconds=to_optional_float(item.get("eventCenterSeconds")),
            pre_roll_seconds=to_optional_float(item.get("preRollSeconds")),
            post_roll_seconds=to_optional_float(item.get("postRollSeconds")),
            window_policy_version=str(item.get("windowPolicyVersion")) if item.get("windowPolicyVersion") else None,
            was_merged=bool(item.get("wasMerged", False)),
            source_event_count=to_optional_int(item.get("sourceEventCount")),
            is_uncertain=bool(item.get("isUncertain", False)),
        )
    return result


def build_report(eval_rows: list[EvaluationRow], predictions: dict[str, PredictionRow]) -> dict[str, Any]:
    flat_label_distribution = distribution(prediction.label for prediction in predictions.values())
    event_family_distribution = distribution(prediction.event_family for prediction in predictions.values())
    label_report = build_dimension_report(
        name="label",
        eval_rows=eval_rows,
        predictions=predictions,
        classes=CANONICAL_LABELS,
        actual_getter=lambda row: row.expected_label,
        predicted_getter=lambda prediction: prediction.label,
        top_k_getter=lambda prediction: prediction.top_k_labels,
    )
    family_report = build_dimension_report(
        name="eventFamily",
        eval_rows=eval_rows,
        predictions=predictions,
        classes=EVENT_FAMILIES,
        actual_getter=lambda row: row.expected_event_family,
        predicted_getter=lambda prediction: prediction.event_family,
        top_k_getter=lambda prediction: prediction.top_k_event_families,
    )
    subtype_report = build_dimension_report(
        name="shotSubtype",
        eval_rows=eval_rows,
        predictions=predictions,
        classes=SHOT_SUBTYPES,
        actual_getter=lambda row: row.expected_shot_subtype,
        predicted_getter=lambda prediction: prediction.shot_subtype,
        top_k_getter=lambda prediction: prediction.top_k_shot_subtypes,
    )
    outcome_report = build_dimension_report(
        name="outcome",
        eval_rows=eval_rows,
        predictions=predictions,
        classes=OUTCOMES,
        actual_getter=lambda row: row.expected_outcome,
        predicted_getter=lambda prediction: prediction.outcome,
        top_k_getter=lambda prediction: prediction.top_k_outcomes,
    )

    failure_examples = build_failure_examples(eval_rows, predictions)
    duration_summary, per_label_distribution = build_duration_sections(eval_rows, predictions)
    labeling_priorities = build_labeling_priorities(label_report["perClass"], label_report["confusions"])
    flat_label_dominance = build_dominance_summary(flat_label_distribution, total=len(predictions), label="Highlight")
    event_family_other_dominance = build_dominance_summary(event_family_distribution, total=len(predictions), label="other")
    mixed_batch_spread = build_label_spread_from_distribution(flat_label_distribution)
    uncertainty_rate = round(
        (
            sum(1 for prediction in predictions.values() if prediction.is_uncertain or prediction.outcome == "uncertain")
            / max(len(predictions), 1)
        ),
        4,
    )
    signal_audit = build_signal_audit(eval_rows, predictions)

    return {
        "summary": {
            "totalClips": label_report["summary"]["total"],
            "accuracy": label_report["summary"]["accuracy"],
            "topKHitRate": label_report["summary"]["topKHitRate"],
            "missingPredictions": label_report["summary"]["missingPredictions"],
            "eventFamilyAccuracy": family_report["summary"]["accuracy"],
            "eventFamilyTopKHitRate": family_report["summary"]["topKHitRate"],
            "shotSubtypeAccuracy": subtype_report["summary"]["accuracy"],
            "shotSubtypeTopKHitRate": subtype_report["summary"]["topKHitRate"],
            "outcomeAccuracy": outcome_report["summary"]["accuracy"],
            "outcomeTopKHitRate": outcome_report["summary"]["topKHitRate"],
            "clipDurationStats": duration_summary,
            "uncertaintyRate": uncertainty_rate,
            "flatLabelDominanceRate": flat_label_dominance["share"],
            "eventFamilyOtherDominanceRate": event_family_other_dominance["share"],
        },
        "perClass": label_report["perClass"],
        "taxonomyMetrics": {
            "eventFamily": {
                "summary": {
                    "totalClips": family_report["summary"]["total"],
                    "top1Accuracy": family_report["summary"]["accuracy"],
                    "topKHitRate": family_report["summary"]["topKHitRate"],
                    "missingPredictions": family_report["summary"]["missingPredictions"],
                },
                "perClass": family_report["perClass"],
                "confusionMatrix": family_report["confusions"],
            },
            "shotSubtype": {
                "summary": {
                    "totalClips": subtype_report["summary"]["total"],
                    "top1Accuracy": subtype_report["summary"]["accuracy"],
                    "topKHitRate": subtype_report["summary"]["topKHitRate"],
                    "missingPredictions": subtype_report["summary"]["missingPredictions"],
                },
                "perClass": subtype_report["perClass"],
                "confusionMatrix": subtype_report["confusions"],
            },
            "outcome": {
                "summary": {
                    "totalClips": outcome_report["summary"]["total"],
                    "top1Accuracy": outcome_report["summary"]["accuracy"],
                    "topKHitRate": outcome_report["summary"]["topKHitRate"],
                    "missingPredictions": outcome_report["summary"]["missingPredictions"],
                },
                "perClass": outcome_report["perClass"],
                "confusionMatrix": outcome_report["confusions"],
            },
        },
        "eventFamilyMetrics": family_report["perClass"],
        "shotSubtypeMetrics": subtype_report["perClass"],
        "outcomeMetrics": outcome_report["perClass"],
        "perLabelDurationDistribution": per_label_distribution,
        "mixedBatchLabelSpread": mixed_batch_spread,
        "dominanceMetrics": {
            "flatLabel": flat_label_dominance,
            "eventFamilyOther": event_family_other_dominance,
        },
        "confusionMatrices": {
            "displayLabel": label_report["confusions"],
            "eventFamily": family_report["confusions"],
            "shotSubtype": subtype_report["confusions"],
            "outcome": outcome_report["confusions"],
        },
        "confusions": label_report["confusions"],
        "eventFamilyConfusions": family_report["confusions"],
        "shotSubtypeConfusions": subtype_report["confusions"],
        "outcomeConfusions": outcome_report["confusions"],
        "failureExamples": failure_examples[:8],
        "signalAudit": signal_audit,
        "recommendedLabelingPriorities": labeling_priorities[:4],
        "manualReviewChecklist": [
            {
                "check": "contains setup",
                "question": "Does the clip include enough lead-in context to understand the play?",
                "recommendedAnswer": "yes",
            },
            {
                "check": "contains finish",
                "question": "Does the clip capture the decisive finish or defensive outcome?",
                "recommendedAnswer": "yes",
            },
            {
                "check": "feels watchable",
                "question": "Does the clip feel coherent and complete when viewed end-to-end?",
                "recommendedAnswer": "yes",
            },
        ],
    }


def build_dimension_report(
    *,
    name: str,
    eval_rows: list[EvaluationRow],
    predictions: dict[str, PredictionRow],
    classes: list[str],
    actual_getter,
    predicted_getter,
    top_k_getter,
) -> dict[str, Any]:
    stats = {
        value: {"support": 0, "correct": 0, "predicted": 0, "topKHit": 0}
        for value in classes
    }
    confusion = Counter()
    total = 0
    correct = 0
    top_k_hits = 0
    missing_predictions = 0

    for row in eval_rows:
        prediction = predictions.get(row.clip_id)
        actual = actual_getter(row)
        total += 1
        stats.setdefault(actual, {"support": 0, "correct": 0, "predicted": 0, "topKHit": 0})
        stats[actual]["support"] += 1

        if prediction is None:
            confusion[(actual, "missing")] += 1
            missing_predictions += 1
            continue

        predicted = predicted_getter(prediction)
        stats.setdefault(predicted, {"support": 0, "correct": 0, "predicted": 0, "topKHit": 0})
        stats[predicted]["predicted"] += 1
        if predicted == actual:
            correct += 1
            stats[actual]["correct"] += 1
        else:
            confusion[(actual, predicted)] += 1

        top_k_values = top_k_getter(prediction)
        if actual in top_k_values:
            top_k_hits += 1
            stats[actual]["topKHit"] += 1

    per_class = {
        value: {
            "support": metrics["support"],
            "correct": metrics["correct"],
            "predicted": metrics["predicted"],
            "accuracy": round(metrics["correct"] / metrics["support"], 4) if metrics["support"] else 0.0,
            "precision": round(metrics["correct"] / metrics["predicted"], 4) if metrics["predicted"] else 0.0,
            "recall": round(metrics["correct"] / metrics["support"], 4) if metrics["support"] else 0.0,
            "topKHitRate": round(metrics["topKHit"] / metrics["support"], 4) if metrics["support"] else 0.0,
        }
        for value, metrics in stats.items()
    }

    return {
        "name": name,
        "summary": {
            "total": total,
            "accuracy": round(correct / total, 4) if total else 0.0,
            "topKHitRate": round(top_k_hits / total, 4) if total else 0.0,
            "missingPredictions": missing_predictions,
        },
        "perClass": per_class,
        "confusions": [
            {"expectedLabel": expected, "predictedLabel": predicted, "count": count}
            for (expected, predicted), count in confusion.most_common()
        ],
    }


def build_failure_examples(eval_rows: list[EvaluationRow], predictions: dict[str, PredictionRow]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for row in eval_rows:
        prediction = predictions.get(row.clip_id)
        if prediction is None:
            examples.append(
                {
                    "clipId": row.clip_id,
                    "expectedLabel": row.expected_label,
                    "predictedLabel": None,
                    "confidence": 0.0,
                    "reason": "missing_prediction",
                    "sourceRef": row.source_ref,
                }
            )
            continue
        if prediction.label != row.expected_label:
            examples.append(
                {
                    "clipId": row.clip_id,
                    "expectedLabel": row.expected_label,
                    "predictedLabel": prediction.label,
                    "confidence": prediction.confidence,
                    "reason": "label_mismatch",
                    "sourceRef": row.source_ref,
                }
            )
    return sorted(examples, key=lambda item: (item["confidence"], item["clipId"]))


def build_signal_audit(eval_rows: list[EvaluationRow], predictions: dict[str, PredictionRow]) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for row in eval_rows:
        if not row.signal_audit_focus:
            continue
        prediction = predictions.get(row.clip_id)
        audits.append(
            {
                "clipId": row.clip_id,
                "sourceRef": row.source_ref,
                "expectedLabel": row.expected_label,
                "predictedLabel": prediction.label if prediction else None,
                "eventFamily": prediction.event_family if prediction else None,
                "shotSubtype": prediction.shot_subtype if prediction else None,
                "outcome": prediction.outcome if prediction else None,
                "isUncertain": prediction.is_uncertain if prediction else None,
                "signalAuditFocus": row.signal_audit_focus,
                "notes": row.notes,
            }
        )
    return audits


def build_duration_sections(
    eval_rows: list[EvaluationRow], predictions: dict[str, PredictionRow]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    duration_samples: list[float] = []
    duration_by_label: dict[str, list[float]] = defaultdict(list)
    merged_by_label: Counter[str] = Counter()
    below_minimum_count = 0
    source_shorter_than_minimum_count = 0
    merged_clip_count = 0

    by_id = {row.clip_id: row for row in eval_rows}
    for clip_id, prediction in predictions.items():
        row = by_id.get(clip_id)
        if prediction.clip_duration_seconds is None:
            continue
        duration = prediction.clip_duration_seconds
        duration_samples.append(duration)
        duration_by_label[prediction.label].append(duration)
        if prediction.was_merged:
            merged_clip_count += 1
            merged_by_label[prediction.label] += 1
        if duration < CLIP_MIN_DURATION_SECONDS:
            source_duration = row.source_duration_seconds if row else None
            if source_duration is not None and source_duration < CLIP_MIN_DURATION_SECONDS:
                source_shorter_than_minimum_count += 1
            else:
                below_minimum_count += 1

    summary = build_duration_summary(
        duration_samples,
        below_minimum_count=below_minimum_count,
        source_shorter_than_minimum_count=source_shorter_than_minimum_count,
        merged_clip_count=merged_clip_count,
    )
    distributions = {
        label: build_duration_distribution(values, merged_by_label.get(label, 0))
        for label, values in sorted(duration_by_label.items(), key=lambda item: item[0])
    }
    return summary, distributions


def build_labeling_priorities(per_class: dict[str, dict[str, Any]], confusions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dominant_confusions: dict[str, str] = {}
    for item in confusions:
        expected = item["expectedLabel"]
        predicted = item["predictedLabel"]
        if expected == predicted or expected in dominant_confusions:
            continue
        dominant_confusions[expected] = predicted

    priorities = []
    for label, stats in per_class.items():
        support = int(stats["support"])
        if support == 0:
            continue
        priorities.append(
            {
                "label": label,
                "recall": stats["recall"],
                "support": support,
                "priorityReason": "low_recall" if stats["recall"] < 0.85 else "monitor",
                "dominantConfusion": dominant_confusions.get(label),
            }
        )
    return sorted(priorities, key=lambda item: (item["recall"], -item["support"], item["label"]))


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = report["summary"]
    lines.append("# Basketball Eval Report")
    lines.append("")
    lines.append(f"- Clips: {summary['totalClips']}")
    lines.append(f"- Label accuracy: {summary['accuracy']:.4f}")
    lines.append(f"- Label top-k hit rate: {summary['topKHitRate']:.4f}")
    lines.append(f"- Event family accuracy: {summary['eventFamilyAccuracy']:.4f}")
    lines.append(f"- Shot subtype accuracy: {summary['shotSubtypeAccuracy']:.4f}")
    lines.append(f"- Outcome accuracy: {summary['outcomeAccuracy']:.4f}")
    lines.append(f"- Uncertainty rate: {summary.get('uncertaintyRate', 0.0):.4f}")
    lines.append(
        f"- Highlight dominance: {summary.get('flatLabelDominanceRate', 0.0):.2%}"
    )
    lines.append(
        f"- Event-family `other` dominance: {summary.get('eventFamilyOtherDominanceRate', 0.0):.2%}"
    )
    lines.append(f"- Missing predictions: {summary['missingPredictions']}")
    clip_stats = summary.get("clipDurationStats", {})
    if clip_stats:
        lines.append(
            "- Clip duration stats: "
            f"below minimum={clip_stats.get('belowMinimumPercentage', 0.0):.2%}, "
            f"median={clip_stats.get('medianSeconds', 0.0):.2f}s, "
            f"p90={clip_stats.get('p90Seconds', 0.0):.2f}s, "
            f"merged={clip_stats.get('mergedClipCount', 0)}"
        )
    lines.append("")
    lines.append("## Dominance")
    lines.append(
        f"- Flat label dominance: `{json.dumps(report['dominanceMetrics']['flatLabel'], sort_keys=True)}`"
    )
    lines.append(
        f"- Event-family other dominance: `{json.dumps(report['dominanceMetrics']['eventFamilyOther'], sort_keys=True)}`"
    )
    lines.append(
        f"- Mixed-batch spread: `{json.dumps(report['mixedBatchLabelSpread'], sort_keys=True)}`"
    )
    lines.append("")
    lines.append("## Per Class")
    for label, stats in report["perClass"].items():
        lines.append(
            f"- {label}: support={stats['support']}, accuracy={stats['accuracy']:.4f}, precision={stats['precision']:.4f}, recall={stats['recall']:.4f}, top-k={stats['topKHitRate']:.4f}"
        )
    lines.append("")
    lines.append("## Event Family")
    for label, stats in report["eventFamilyMetrics"].items():
        lines.append(
            f"- {label}: support={stats['support']}, accuracy={stats['accuracy']:.4f}, top-k={stats['topKHitRate']:.4f}"
        )
    lines.append("")
    lines.append("## Shot Subtype")
    for label, stats in report["shotSubtypeMetrics"].items():
        lines.append(
            f"- {label}: support={stats['support']}, accuracy={stats['accuracy']:.4f}, top-k={stats['topKHitRate']:.4f}"
        )
    lines.append("")
    lines.append("## Outcome")
    for label, stats in report["outcomeMetrics"].items():
        lines.append(
            f"- {label}: support={stats['support']}, accuracy={stats['accuracy']:.4f}, top-k={stats['topKHitRate']:.4f}"
        )
    return "\n".join(lines) + "\n"


def build_duration_summary(
    values: Iterable[float],
    *,
    below_minimum_count: int,
    source_shorter_than_minimum_count: int,
    merged_clip_count: int,
) -> dict[str, Any]:
    samples = sorted(float(value) for value in values)
    count = len(samples)
    if count == 0:
        return {
            "count": 0,
            "belowMinimumCount": below_minimum_count,
            "belowMinimumPercentage": 0.0,
            "sourceShorterThanMinimumCount": source_shorter_than_minimum_count,
            "medianSeconds": 0.0,
            "p90Seconds": 0.0,
            "mergedClipCount": merged_clip_count,
        }
    p90_index = max(int(round((count - 1) * 0.9)), 0)
    return {
        "count": count,
        "belowMinimumCount": below_minimum_count,
        "belowMinimumPercentage": round(below_minimum_count / count, 4),
        "sourceShorterThanMinimumCount": source_shorter_than_minimum_count,
        "medianSeconds": round(median(samples), 4),
        "p90Seconds": round(samples[p90_index], 4),
        "mergedClipCount": merged_clip_count,
    }


def build_duration_distribution(values: Iterable[float], merged_count: int) -> dict[str, Any]:
    samples = sorted(float(value) for value in values)
    count = len(samples)
    if count == 0:
        return {
            "count": 0,
            "medianSeconds": 0.0,
            "p90Seconds": 0.0,
            "mergedCount": merged_count,
        }
    p90_index = max(int(round((count - 1) * 0.9)), 0)
    return {
        "count": count,
        "medianSeconds": round(median(samples), 4),
        "p90Seconds": round(samples[p90_index], 4),
        "mergedCount": merged_count,
    }


def build_dominance_summary(distribution_map: dict[str, int], *, total: int, label: str) -> dict[str, Any]:
    total = max(total, 1)
    count = int(distribution_map.get(label, 0))
    dominant_label, dominant_count = ("unknown", 0)
    if distribution_map:
        dominant_label, dominant_count = max(distribution_map.items(), key=lambda item: (item[1], item[0]))
    return {
        "label": label,
        "count": count,
        "share": round(count / total, 4),
        "dominatesBatch": count > total / 2,
        "dominantLabel": dominant_label or "unknown",
        "dominantLabelShare": round(dominant_count / total, 4),
        "distribution": distribution_map,
    }


def build_label_spread_from_distribution(distribution_map: dict[str, int]) -> dict[str, Any]:
    total = max(sum(distribution_map.values()), 1)
    dominant_label, dominant_count = ("", 0)
    if distribution_map:
        dominant_label, dominant_count = max(distribution_map.items(), key=lambda item: (item[1], item[0]))
    entropy = 0.0
    for count in distribution_map.values():
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * __import__("math").log(probability, 2)
    spread_score = round(1.0 - (dominant_count / total), 4) if total else 0.0
    return {
        "uniqueLabelCount": len(distribution_map),
        "dominantLabel": dominant_label or "unknown",
        "dominantLabelShare": round(dominant_count / total, 4),
        "entropy": round(entropy, 4),
        "spreadScore": spread_score,
        "topLabels": sorted(distribution_map.items(), key=lambda item: (-item[1], item[0]))[:8],
    }


def distribution(values: Iterable[Any]) -> dict[str, int]:
    counts = Counter(normalize_bucket(value) for value in values)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def normalize_bucket(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip()
    return text if text else "null"


def taxonomy_for_label(label: str) -> tuple[str, str, str]:
    normalized = normalize_label(label)
    if normalized == "dunk":
        return "shot_attempt", "dunk", "made"
    if normalized == "layup":
        return "shot_attempt", "layup", "made"
    if normalized == "three":
        return "shot_attempt", "three", "made"
    if normalized == "putback":
        return "shot_attempt", "putback", "made"
    if normalized == "jumper":
        return "shot_attempt", "jumper", "made"
    if normalized == "miss":
        return "shot_attempt", "jumper", "missed"
    if normalized == "block":
        return "defensive_event", "unknown", "blocked"
    if normalized == "steal":
        return "turnover", "unknown", "uncertain"
    if normalized == "fast break":
        return "transition", "unknown", "uncertain"
    return "other", "unknown", "uncertain"


def normalize_label(value: str) -> str:
    normalized = str(value).strip().lower().replace("_", " ").replace("-", " ")
    return LABEL_SYNONYMS.get(normalized, normalized)


def normalize_event_family(value: Any) -> str:
    normalized = str(value or "other").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"defense", "defensive", "defensive_play", "defensive_event"}:
        return "defensive_event"
    if normalized in {"shot", "shots", "shot_attempt"}:
        return "shot_attempt"
    if normalized in {"turnover", "steal"}:
        return "turnover"
    if normalized in {"transition", "fast_break"}:
        return "transition"
    if normalized in {"other", "unknown"}:
        return "other"
    synonym = EVENT_FAMILY_SYNONYMS.get(normalized.replace("_", " "))
    if synonym:
        return synonym
    return normalized


def normalize_shot_subtype(value: Any) -> str:
    normalized = str(value or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"none", "null"}:
        return "unknown"
    synonym = SHOT_SUBTYPE_SYNONYMS.get(normalized.replace("_", " "))
    if synonym:
        return synonym
    return normalized


def normalize_outcome(value: Any) -> str:
    normalized = str(value or "uncertain").strip().lower().replace("-", " ")
    return OUTCOME_SYNONYMS.get(normalized, normalized if normalized in OUTCOMES else "uncertain")


def to_optional_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def to_optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None


def unique_in_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen or not value:
            continue
        seen.add(value)
        result.append(value)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

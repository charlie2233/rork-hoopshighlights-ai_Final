from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any


CANONICAL_LABELS = [
    "dunk",
    "layup",
    "jumper",
    "block",
    "steal",
    "fast break",
    "miss",
]

LABEL_SYNONYMS = {
    "three pointer": "jumper",
    "three-pointer": "jumper",
    "3 pointer": "jumper",
    "3-pointer": "jumper",
    "midrange jumper": "jumper",
    "mid-range jumper": "jumper",
    "shot": "jumper",
    "fastbreak": "fast break",
    "fast-break": "fast break",
    "made shot": "jumper",
    "made": "jumper",
}

LABEL_PRIORITY_ORDER = {
    "jumper": 0,
    "miss": 1,
    "layup": 2,
    "fast break": 3,
    "steal": 4,
    "block": 5,
    "dunk": 6,
}

CLIP_MIN_DURATION_SECONDS = 3.5


@dataclass
class EvaluationRow:
    clip_id: str
    expected_label: str
    source_ref: str
    notes: str = ""
    split: str = "train"
    source_duration_seconds: float | None = None


@dataclass
class PredictionRow:
    clip_id: str
    label: str
    confidence: float
    top_k_labels: list[str]
    clip_duration_seconds: float | None = None
    event_center_seconds: float | None = None
    pre_roll_seconds: float | None = None
    post_roll_seconds: float | None = None
    window_policy_version: str | None = None
    was_merged: bool = False
    source_event_count: int | None = None


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
                source_ref=str(item.get("sourceRef", "")),
                notes=str(item.get("notes", "")),
                split=str(item.get("split", "train")),
                source_duration_seconds=to_optional_float(item.get("sourceDurationSeconds")),
            )
        )
    return rows


def load_predictions(path: Path) -> dict[str, PredictionRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, PredictionRow] = {}
    for item in payload:
        clip_id = str(item["clipId"])
        top_k = [normalize_label(str(label)) for label in item.get("topKLabels", [])]
        result[clip_id] = PredictionRow(
            clip_id=clip_id,
            label=normalize_label(str(item["label"])),
            confidence=float(item.get("confidence", 0.0)),
            top_k_labels=top_k,
            clip_duration_seconds=to_optional_float(item.get("clipDurationSeconds")),
            event_center_seconds=to_optional_float(item.get("eventCenterSeconds")),
            pre_roll_seconds=to_optional_float(item.get("preRollSeconds")),
            post_roll_seconds=to_optional_float(item.get("postRollSeconds")),
            window_policy_version=str(item.get("windowPolicyVersion")) if item.get("windowPolicyVersion") else None,
            was_merged=bool(item.get("wasMerged", False)),
            source_event_count=to_optional_int(item.get("sourceEventCount")),
        )
    return result


def build_report(eval_rows: list[EvaluationRow], predictions: dict[str, PredictionRow]) -> dict[str, Any]:
    class_stats = {
        label: {
            "support": 0,
            "correct": 0,
            "predicted": 0,
            "topKHit": 0,
        }
        for label in CANONICAL_LABELS
    }
    confusion = Counter()
    failure_examples: list[dict[str, Any]] = []
    unknown_prediction_labels: Counter[str] = Counter()
    duration_samples: list[float] = []
    duration_by_label: dict[str, list[float]] = defaultdict(list)
    merged_by_label: Counter[str] = Counter()
    below_minimum_count = 0
    source_shorter_than_minimum_count = 0
    merged_clip_count = 0

    total = 0
    correct = 0
    top_k_hits = 0

    for row in eval_rows:
        prediction = predictions.get(row.clip_id)
        total += 1
        class_stats[row.expected_label]["support"] += 1

        if prediction is None:
            confusion[(row.expected_label, "missing")] += 1
            failure_examples.append(
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

        if prediction.clip_duration_seconds is not None:
            duration_samples.append(prediction.clip_duration_seconds)
            duration_by_label[prediction.label].append(prediction.clip_duration_seconds)
            if prediction.clip_duration_seconds < CLIP_MIN_DURATION_SECONDS:
                if row.source_duration_seconds is not None and row.source_duration_seconds < CLIP_MIN_DURATION_SECONDS:
                    source_shorter_than_minimum_count += 1
                else:
                    below_minimum_count += 1
        if prediction.was_merged:
            merged_clip_count += 1
            merged_by_label[prediction.label] += 1

        class_stats.setdefault(
            prediction.label,
            {
                "support": 0,
                "correct": 0,
                "predicted": 0,
                "topKHit": 0,
            },
        )
        class_stats[prediction.label]["predicted"] += 1
        if prediction.label not in CANONICAL_LABELS:
            unknown_prediction_labels[prediction.label] += 1
        if prediction.label == row.expected_label:
            correct += 1
            class_stats[row.expected_label]["correct"] += 1
        else:
            confusion[(row.expected_label, prediction.label)] += 1
            failure_examples.append(
                {
                    "clipId": row.clip_id,
                    "expectedLabel": row.expected_label,
                    "predictedLabel": prediction.label,
                    "confidence": prediction.confidence,
                    "reason": "label_mismatch",
                    "sourceRef": row.source_ref,
                }
            )

        if row.expected_label in prediction.top_k_labels:
            top_k_hits += 1
            class_stats[row.expected_label]["topKHit"] += 1

    per_class: dict[str, dict[str, float | int]] = {}
    for label in CANONICAL_LABELS:
        stats = class_stats[label]
        support = stats["support"]
        correct_count = stats["correct"]
        predicted_count = stats["predicted"]
        top_k_hit_count = stats["topKHit"]
        precision = (correct_count / predicted_count) if predicted_count else 0.0
        recall = (correct_count / support) if support else 0.0
        per_class[label] = {
            "support": support,
            "correct": correct_count,
            "predicted": predicted_count,
            "accuracy": recall,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "topKHitRate": round(top_k_hit_count / support if support else 0.0, 4),
        }

    confusion_rows = [
        {
            "expectedLabel": expected,
            "predictedLabel": predicted,
            "count": count,
        }
        for (expected, predicted), count in confusion.most_common()
    ]

    low_recall_labels = sorted(
        [
            (label, stats["recall"], stats["support"])
            for label, stats in per_class.items()
        ],
        key=lambda item: (
            item[1],
            -item[2],
            LABEL_PRIORITY_ORDER.get(item[0], len(LABEL_PRIORITY_ORDER)),
            item[0],
        ),
    )
    labeling_priorities = []
    for label, recall, support in low_recall_labels:
        if support == 0:
            continue
        labeling_priorities.append(
            {
                "label": label,
                "recall": recall,
                "support": support,
                "priorityReason": "low_recall" if recall < 0.85 else "monitor",
            }
        )

    report = {
        "summary": {
            "totalClips": total,
            "accuracy": round(correct / total if total else 0.0, 4),
            "topKHitRate": round(top_k_hits / total if total else 0.0, 4),
            "missingPredictions": sum(1 for example in failure_examples if example["reason"] == "missing_prediction"),
            "clipDurationStats": build_duration_summary(
                duration_samples,
                below_minimum_count=below_minimum_count,
                source_shorter_than_minimum_count=source_shorter_than_minimum_count,
                merged_clip_count=merged_clip_count,
            ),
        },
        "perClass": per_class,
        "perLabelDurationDistribution": {
            label: build_duration_distribution(values, merged_by_label.get(label, 0))
            for label, values in sorted(duration_by_label.items(), key=lambda item: item[0])
        },
        "confusions": confusion_rows,
        "failureExamples": sorted(
            failure_examples,
            key=lambda item: (item["confidence"], item["clipId"]),
        )[:8],
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
        "unknownPredictionLabels": dict(unknown_prediction_labels.most_common()),
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = report["summary"]
    lines.append("# Basketball Eval Report")
    lines.append("")
    lines.append(f"- Clips: {summary['totalClips']}")
    lines.append(f"- Accuracy: {summary['accuracy']:.4f}")
    lines.append(f"- Top-k hit rate: {summary['topKHitRate']:.4f}")
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
    lines.append("## Per Class")
    for label, stats in report["perClass"].items():
        lines.append(
            f"- {label}: support={stats['support']}, accuracy={stats['accuracy']:.4f}, precision={stats['precision']:.4f}, recall={stats['recall']:.4f}"
        )
    if report.get("perLabelDurationDistribution"):
        lines.append("")
        lines.append("## Per Label Duration Distribution")
        for label, stats in report["perLabelDurationDistribution"].items():
            lines.append(
                f"- {label}: count={stats['count']}, median={stats['medianSeconds']:.2f}s, p90={stats['p90Seconds']:.2f}s, merged={stats['mergedCount']}"
            )
    lines.append("")
    lines.append("## Failure Examples")
    for example in report["failureExamples"]:
        lines.append(
            f"- {example['clipId']}: expected {example['expectedLabel']}, got {example['predictedLabel'] or 'missing'} ({example['reason']})"
        )
    if report.get("manualReviewChecklist"):
        lines.append("")
        lines.append("## Manual Review Checklist")
        for item in report["manualReviewChecklist"]:
            lines.append(f"- {item['check']}: {item['question']} ({item['recommendedAnswer']})")
    lines.append("")
    lines.append("## Recommended Labeling Priorities")
    for item in report["recommendedLabelingPriorities"]:
        lines.append(f"- {item['label']} (recall {item['recall']:.4f}, support {item['support']})")
    if report.get("unknownPredictionLabels"):
        lines.append("")
        lines.append("## Unknown Prediction Labels")
        for label, count in report["unknownPredictionLabels"].items():
            lines.append(f"- {label}: {count}")
    return "\n".join(lines) + "\n"


def build_duration_summary(
    durations: list[float],
    *,
    below_minimum_count: int,
    source_shorter_than_minimum_count: int,
    merged_clip_count: int,
) -> dict[str, float | int]:
    if not durations:
        return {
            "clipCount": 0,
            "belowMinimumCount": 0,
            "belowMinimumPercentage": 0.0,
            "medianSeconds": 0.0,
            "p90Seconds": 0.0,
            "mergedClipCount": merged_clip_count,
            "sourceShorterThanMinimumCount": source_shorter_than_minimum_count,
        }

    return {
        "clipCount": len(durations),
        "belowMinimumCount": below_minimum_count,
        "belowMinimumPercentage": round(below_minimum_count / len(durations), 4),
        "medianSeconds": round(float(median(durations)), 4),
        "p90Seconds": round(percentile(durations, 0.9), 4),
        "mergedClipCount": merged_clip_count,
        "sourceShorterThanMinimumCount": source_shorter_than_minimum_count,
    }


def build_duration_distribution(durations: list[float], merged_count: int) -> dict[str, float | int]:
    if not durations:
        return {
            "count": 0,
            "minSeconds": 0.0,
            "medianSeconds": 0.0,
            "p90Seconds": 0.0,
            "mergedCount": merged_count,
        }

    return {
        "count": len(durations),
        "minSeconds": round(min(durations), 4),
        "medianSeconds": round(float(median(durations)), 4),
        "p90Seconds": round(percentile(durations, 0.9), 4),
        "mergedCount": merged_count,
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower_index = int(index)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    if lower_index == upper_index:
        return float(ordered[lower_index])
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    weight = index - lower_index
    return float(lower_value + (upper_value - lower_value) * weight)


def to_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_label(label: str) -> str:
    normalized = " ".join(label.strip().lower().replace("_", " ").replace("-", " ").split())
    return LABEL_SYNONYMS.get(normalized, normalized)


if __name__ == "__main__":
    raise SystemExit(main())

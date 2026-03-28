from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
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


@dataclass
class EvaluationRow:
    clip_id: str
    expected_label: str
    source_ref: str
    notes: str = ""
    split: str = "train"


@dataclass
class PredictionRow:
    clip_id: str
    label: str
    confidence: float
    top_k_labels: list[str]


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
        },
        "perClass": per_class,
        "confusions": confusion_rows,
        "failureExamples": sorted(
            failure_examples,
            key=lambda item: (item["confidence"], item["clipId"]),
        )[:8],
        "recommendedLabelingPriorities": labeling_priorities[:4],
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
    lines.append("")
    lines.append("## Per Class")
    for label, stats in report["perClass"].items():
        lines.append(
            f"- {label}: support={stats['support']}, accuracy={stats['accuracy']:.4f}, precision={stats['precision']:.4f}, recall={stats['recall']:.4f}"
        )
    lines.append("")
    lines.append("## Failure Examples")
    for example in report["failureExamples"]:
        lines.append(
            f"- {example['clipId']}: expected {example['expectedLabel']}, got {example['predictedLabel'] or 'missing'} ({example['reason']})"
        )
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


def normalize_label(label: str) -> str:
    normalized = " ".join(label.strip().lower().replace("_", " ").replace("-", " ").split())
    return LABEL_SYNONYMS.get(normalized, normalized)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

if __package__ is None or __package__ == "":
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[3]))

from services.inference.app.calibration import RUNTIME_CALIBRATION_SCHEMA_VERSION
from services.inference.app.labels import normalize_action_label


DEFAULT_GOLD_DATASET = Path(__file__).resolve().parents[1] / "datasets" / "gold_annotations.jsonl"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "evals" / "runtime_calibration.json"
REPO_ROOT = Path(__file__).resolve().parents[3]

BINS: tuple[tuple[float, float], ...] = (
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0),
)

DIMENSIONS: dict[str, dict[str, str]] = {
    "eventFamily": {
        "prediction_key": "eventFamily",
        "score_keys": ("eventFamilyConfidenceBeforeMapping", "confidenceBeforeMapping", "confidenceAfterMapping", "confidence"),
        "gold_key": "eventFamily",
        "normalizer": "event_family",
    },
    "outcome": {
        "prediction_key": "outcome",
        "score_keys": ("outcomeConfidenceBeforeMapping", "confidenceBeforeMapping", "confidenceAfterMapping", "confidence"),
        "gold_key": "outcome",
        "normalizer": "outcome",
    },
    "shotSubtype": {
        "prediction_key": "shotSubtype",
        "score_keys": ("shotSubtypeConfidenceBeforeMapping", "confidenceBeforeMapping", "confidenceAfterMapping", "confidence"),
        "gold_key": "shotSubtype",
        "normalizer": "shot_subtype",
    },
}


@dataclass(frozen=True)
class CalibrationExample:
    clip_id: str
    split: str
    dimension: str
    gold_label: str
    predicted_label: str
    confidence: float
    correct: bool


def main() -> int:
    args = parse_args()
    rows = load_jsonl(args.gold_dataset)
    calibration_rows, test_rows = split_rows(rows)
    artifact = build_runtime_calibration_artifact(
        calibration_rows,
        test_rows,
        source_dataset=relative_to_repo(args.gold_dataset),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")

    report_path = args.report_output or args.output.with_name(f"{args.output.stem}_report.md")
    report_path.write_text(render_report(artifact), encoding="utf-8")

    print(args.output)
    print(report_path)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a runtime calibration artifact from held-out gold data.")
    parser.add_argument("--gold-dataset", type=Path, default=DEFAULT_GOLD_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=None)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    calibration_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []
    for row in rows:
        split = split_for_clip(str(row["clipId"]))
        if split == "calibration":
            calibration_rows.append(row)
        elif split == "test":
            test_rows.append(row)
    return calibration_rows, test_rows


def split_for_clip(clip_id: str) -> str:
    bucket = int(hashlib.sha256(clip_id.encode("utf-8")).hexdigest(), 16) % 100
    if bucket < 40:
        return "train"
    if bucket < 80:
        return "calibration"
    return "test"


def build_runtime_calibration_artifact(
    calibration_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    *,
    source_dataset: str,
) -> dict[str, Any]:
    dimensions: dict[str, dict[str, Any]] = {}
    holdout_metrics: dict[str, Any] = {}

    for dimension, spec in DIMENSIONS.items():
        examples = collect_examples(calibration_rows, dimension, spec)
        dimensions[dimension] = build_dimension_calibration(examples)
        holdout_metrics[dimension] = evaluate_dimension(test_rows, dimension, spec, dimensions[dimension])

    return {
        "schemaVersion": RUNTIME_CALIBRATION_SCHEMA_VERSION,
        "sourceDataset": source_dataset,
        "splitStrategy": "hash:clipId:40-40-20(train-calibration-test)",
        "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
        "notes": [
            "Calibration fits only on held-out gold rows.",
            "Teacher outputs remain training-only and are not read at inference time.",
            "Calibration tables are monotonic bin lookups applied before uncertainty gating.",
        ],
        "dimensions": dimensions,
        "holdoutMetrics": holdout_metrics,
    }


def collect_examples(rows: list[dict[str, Any]], dimension: str, spec: dict[str, str]) -> list[CalibrationExample]:
    examples: list[CalibrationExample] = []
    for row in rows:
        runtime = dict(row.get("rawRuntimeOutputs") or {})
        predicted_label = normalize_dimension_label(dimension, runtime.get(spec["prediction_key"]))
        if predicted_label is None:
            continue
        gold_label = normalize_dimension_label(dimension, row.get(spec["gold_key"]))
        if gold_label is None:
            continue
        confidence = to_float_from_keys(runtime, spec["score_keys"])
        if confidence is None:
            continue
        examples.append(
            CalibrationExample(
                clip_id=str(row["clipId"]),
                split=split_for_clip(str(row["clipId"])),
                dimension=dimension,
                gold_label=gold_label,
                predicted_label=predicted_label,
                confidence=confidence,
                correct=predicted_label == gold_label,
            )
        )
    return examples


def build_dimension_calibration(examples: list[CalibrationExample]) -> dict[str, Any]:
    grouped: dict[str, list[CalibrationExample]] = defaultdict(list)
    for example in examples:
        grouped[example.predicted_label].append(example)

    dimension: dict[str, Any] = {}
    for label, label_examples in grouped.items():
        bins = []
        running_calibrated = 0.0
        support = len(label_examples)
        fallback_score = round((sum(1 for item in label_examples if item.correct) + 1) / (support + 2), 4)
        for low, high in BINS:
            bin_examples = [item for item in label_examples if in_bin(item.confidence, low, high)]
            count = len(bin_examples)
            positives = sum(1 for item in bin_examples if item.correct)
            if count > 0:
                calibrated_score = round((positives + 1) / (count + 2), 4)
                running_calibrated = max(running_calibrated, calibrated_score)
            else:
                calibrated_score = running_calibrated if running_calibrated > 0 else fallback_score
            bins.append(
                {
                    "minScore": low,
                    "maxScore": high,
                    "count": count,
                    "positives": positives,
                    "calibratedScore": round(min(max(calibrated_score, 0.0), 1.0), 4),
                }
            )
        dimension[label] = {
            "label": label,
            "bins": bins,
            "fallbackScore": fallback_score,
            "support": support,
        }
    return dimension


def evaluate_dimension(
    rows: list[dict[str, Any]],
    dimension: str,
    spec: dict[str, str],
    calibration: dict[str, Any],
) -> dict[str, Any]:
    examples = collect_examples(rows, dimension, spec)
    if not examples:
        return {"sampleCount": 0}

    raw_correct = 0
    raw_confidences: list[float] = []
    calibrated_confidences: list[float] = []
    bin_totals: dict[int, list[CalibrationExample]] = defaultdict(list)
    for example in examples:
        raw_correct += int(example.correct)
        raw_confidences.append(example.confidence)
        calibrated_confidences.append(calibrate_score(calibration, example.predicted_label, example.confidence))
        bin_totals[bucket_for_score(example.confidence)].append(example)

    ece = 0.0
    total = len(examples)
    for bucket_examples in bin_totals.values():
        bucket_confidence = mean(item.confidence for item in bucket_examples)
        bucket_accuracy = sum(1 for item in bucket_examples if item.correct) / len(bucket_examples)
        ece += (len(bucket_examples) / total) * abs(bucket_accuracy - bucket_confidence)

    return {
        "sampleCount": total,
        "accuracy": round(raw_correct / total, 4),
        "meanConfidence": round(mean(raw_confidences), 4),
        "meanCalibratedConfidence": round(mean(calibrated_confidences), 4),
        "expectedCalibrationError": round(ece, 4),
        "labelDistribution": dict(Counter(item.predicted_label for item in examples)),
        "goldDistribution": dict(Counter(item.gold_label for item in examples)),
    }


def calibrate_score(calibration: dict[str, Any], label: str, score: float) -> float:
    label_calibration = calibration.get(label)
    if not label_calibration:
        return round(min(max(score, 0.0), 1.0), 4)
    clamped = min(max(score, 0.0), 1.0)
    for bucket in label_calibration.get("bins", []):
        low = float(bucket.get("minScore", 0.0))
        high = float(bucket.get("maxScore", 1.0))
        if (low <= clamped <= high) or (clamped >= 1.0 and high >= 1.0):
            return round(min(max(float(bucket.get("calibratedScore", score)), 0.0), 1.0), 4)
    return round(min(max(float(label_calibration.get("fallbackScore", score)), 0.0), 1.0), 4)


def bucket_for_score(score: float) -> int:
    clamped = min(max(score, 0.0), 1.0)
    for index, (low, high) in enumerate(BINS):
        if (low <= clamped < high) or (index == len(BINS) - 1 and clamped <= high):
            return index
    return len(BINS) - 1


def in_bin(score: float, low: float, high: float) -> bool:
    if low <= score < high:
        return True
    if score >= 1.0 and high >= 1.0:
        return True
    return False


def normalize_dimension_label(dimension: str, value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if dimension == "eventFamily":
        if text in {"shot", "shot_attempt"}:
            return "shot_attempt"
        if text in {"defense", "defensive"}:
            return "defensive_event"
        return text.replace(" ", "_")
    if dimension == "outcome":
        if text in {"make", "made"}:
            return "made"
        if text in {"miss", "missed"}:
            return "missed"
        if text in {"block", "blocked"}:
            return "blocked"
        if text in {"uncertain", "unknown"}:
            return "uncertain"
        return text
    if dimension == "shotSubtype":
        if text in {"fast break", "fast_break"}:
            return "fast_break"
        return normalize_action_label(text)
    return text


def to_float_from_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def render_report(artifact: dict[str, Any]) -> str:
    lines = [
        "# Runtime Calibration Report",
        "",
        f"- Schema version: `{artifact['schemaVersion']}`",
        f"- Source dataset: `{artifact['sourceDataset']}`",
        f"- Split strategy: `{artifact['splitStrategy']}`",
        "",
        "## Holdout Metrics",
    ]
    for dimension, metrics in artifact.get("holdoutMetrics", {}).items():
        lines.append(f"### {dimension}")
        lines.append(f"- Sample count: `{metrics.get('sampleCount', 0)}`")
        if metrics.get("sampleCount", 0) > 0:
            lines.append(f"- Accuracy: `{metrics.get('accuracy')}`")
            lines.append(f"- Mean confidence: `{metrics.get('meanConfidence')}`")
            lines.append(f"- Mean calibrated confidence: `{metrics.get('meanCalibratedConfidence')}`")
            lines.append(f"- ECE: `{metrics.get('expectedCalibrationError')}`")
        lines.append("")
    lines.append("## Notes")
    for note in artifact.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

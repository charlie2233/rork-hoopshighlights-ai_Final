#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_TIOU = 0.5


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark HoopClips detection candidates with recall, macro F1, and mAP@tIoU.")
    parser.add_argument("--predictions", type=Path, help="JSON file with a predictions array.")
    parser.add_argument("--ground-truth", type=Path, help="JSON file with a groundTruth array.")
    parser.add_argument("--fixture", type=Path, help="JSON file containing both predictions and groundTruth arrays.")
    parser.add_argument("--tiou", type=float, default=DEFAULT_TIOU, help="Temporal IoU threshold for matching.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON only.")
    args = parser.parse_args()

    payload = load_payload(args)
    predictions = [normalize_item(item, is_prediction=True) for item in payload["predictions"]]
    ground_truth = [normalize_item(item, is_prediction=False) for item in payload["groundTruth"]]
    metrics = evaluate(predictions, ground_truth, tiou_threshold=args.tiou)

    if args.json:
        print(json.dumps(metrics, sort_keys=True))
    else:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


def load_payload(args: argparse.Namespace) -> dict[str, list[dict[str, Any]]]:
    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        return {
            "predictions": list(payload.get("predictions", [])),
            "groundTruth": list(payload.get("groundTruth", payload.get("ground_truth", []))),
        }
    if args.predictions or args.ground_truth:
        if not args.predictions or not args.ground_truth:
            raise SystemExit("--predictions and --ground-truth must be provided together.")
        return {
            "predictions": list(json.loads(args.predictions.read_text(encoding="utf-8")).get("predictions", [])),
            "groundTruth": list(json.loads(args.ground_truth.read_text(encoding="utf-8")).get("groundTruth", [])),
        }
    return sample_payload()


def normalize_item(item: dict[str, Any], *, is_prediction: bool) -> dict[str, Any]:
    start = float(item.get("startTime", item.get("start", 0.0)))
    end = float(item.get("endTime", item.get("end", start)))
    label = str(item.get("canonicalLabel") or item.get("label") or item.get("productLabel") or "highlight").strip().lower()
    score = float(item.get("score", item.get("rankScore", item.get("confidence", 1.0 if not is_prediction else 0.0))))
    return {
        "videoId": str(item.get("videoId") or item.get("jobId") or "default"),
        "startTime": min(start, end),
        "endTime": max(start, end),
        "label": label,
        "score": max(0.0, min(1.0, score)),
    }


def evaluate(predictions: list[dict[str, Any]], ground_truth: list[dict[str, Any]], *, tiou_threshold: float) -> dict[str, Any]:
    labels = sorted({item["label"] for item in predictions + ground_truth})
    matched_gt = greedy_match(predictions, ground_truth, tiou_threshold=tiou_threshold)
    recall = len(matched_gt) / len(ground_truth) if ground_truth else 0.0
    per_label = {
        label: label_metrics(predictions, ground_truth, label=label, tiou_threshold=tiou_threshold)
        for label in labels
    }
    macro_f1 = sum(metrics["f1"] for metrics in per_label.values()) / len(per_label) if per_label else 0.0
    map_tiou = sum(metrics["averagePrecision"] for metrics in per_label.values()) / len(per_label) if per_label else 0.0
    return {
        "metricVersion": "detection-benchmark-v1",
        "temporalIoUThreshold": tiou_threshold,
        "predictionCount": len(predictions),
        "groundTruthCount": len(ground_truth),
        "recall": round(recall, 6),
        "macroF1": round(macro_f1, 6),
        "mAP@tIoU": round(map_tiou, 6),
        "labels": per_label,
    }


def label_metrics(
    predictions: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    *,
    label: str,
    tiou_threshold: float,
) -> dict[str, float | int]:
    label_predictions = [item for item in predictions if item["label"] == label]
    label_ground_truth = [item for item in ground_truth if item["label"] == label]
    matched_gt = greedy_match(label_predictions, label_ground_truth, tiou_threshold=tiou_threshold)
    true_positive = len(matched_gt)
    false_positive = max(0, len(label_predictions) - true_positive)
    false_negative = max(0, len(label_ground_truth) - true_positive)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    average_precision = average_precision_at_tiou(label_predictions, label_ground_truth, tiou_threshold=tiou_threshold)
    return {
        "groundTruth": len(label_ground_truth),
        "predictions": len(label_predictions),
        "truePositive": true_positive,
        "falsePositive": false_positive,
        "falseNegative": false_negative,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "averagePrecision": round(average_precision, 6),
    }


def greedy_match(
    predictions: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    *,
    tiou_threshold: float,
) -> set[int]:
    matched: set[int] = set()
    scored_pairs: list[tuple[float, float, int]] = []
    for pred in sorted(predictions, key=lambda item: item["score"], reverse=True):
        for index, truth in enumerate(ground_truth):
            if index in matched or pred["videoId"] != truth["videoId"] or pred["label"] != truth["label"]:
                continue
            tiou = temporal_iou(pred, truth)
            if tiou >= tiou_threshold:
                scored_pairs.append((pred["score"], tiou, index))
    for _, _, index in sorted(scored_pairs, key=lambda item: (item[0], item[1]), reverse=True):
        matched.add(index)
    return matched


def average_precision_at_tiou(
    predictions: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    *,
    tiou_threshold: float,
) -> float:
    if not ground_truth:
        return 0.0
    matched: set[int] = set()
    true_positive_flags: list[int] = []
    false_positive_flags: list[int] = []
    for pred in sorted(predictions, key=lambda item: item["score"], reverse=True):
        match_index = best_unmatched_truth(pred, ground_truth, matched, tiou_threshold=tiou_threshold)
        if match_index is None:
            true_positive_flags.append(0)
            false_positive_flags.append(1)
        else:
            matched.add(match_index)
            true_positive_flags.append(1)
            false_positive_flags.append(0)

    precisions: list[float] = []
    tp = 0
    fp = 0
    for is_tp, is_fp in zip(true_positive_flags, false_positive_flags):
        tp += is_tp
        fp += is_fp
        if is_tp:
            precisions.append(tp / (tp + fp))
    return sum(precisions) / len(ground_truth) if ground_truth else 0.0


def best_unmatched_truth(
    prediction: dict[str, Any],
    ground_truth: list[dict[str, Any]],
    matched: set[int],
    *,
    tiou_threshold: float,
) -> int | None:
    best_index: int | None = None
    best_iou = 0.0
    for index, truth in enumerate(ground_truth):
        if index in matched or prediction["videoId"] != truth["videoId"] or prediction["label"] != truth["label"]:
            continue
        tiou = temporal_iou(prediction, truth)
        if tiou >= tiou_threshold and tiou > best_iou:
            best_iou = tiou
            best_index = index
    return best_index


def temporal_iou(left: dict[str, Any], right: dict[str, Any]) -> float:
    intersection = max(0.0, min(left["endTime"], right["endTime"]) - max(left["startTime"], right["startTime"]))
    union = max(left["endTime"], right["endTime"]) - min(left["startTime"], right["startTime"])
    return intersection / union if union > 0 else 0.0


def sample_payload() -> dict[str, list[dict[str, Any]]]:
    return {
        "groundTruth": [
            {"videoId": "sample", "startTime": 1.0, "endTime": 5.0, "label": "dunk"},
            {"videoId": "sample", "startTime": 10.0, "endTime": 14.0, "label": "steal"},
            {"videoId": "sample", "startTime": 18.0, "endTime": 23.0, "label": "three_pointer"},
        ],
        "predictions": [
            {"videoId": "sample", "startTime": 0.8, "endTime": 5.2, "label": "dunk", "score": 0.95},
            {"videoId": "sample", "startTime": 9.5, "endTime": 13.6, "label": "steal", "score": 0.74},
            {"videoId": "sample", "startTime": 18.3, "endTime": 22.7, "label": "three_pointer", "score": 0.81},
            {"videoId": "sample", "startTime": 27.0, "endTime": 30.0, "label": "dunk", "score": 0.35},
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())

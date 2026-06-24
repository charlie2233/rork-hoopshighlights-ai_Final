from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence


DEFAULT_TIOU = 0.5
DEFAULT_K_VALUES = (1, 3, 5)


def normalize_eval_item(item: dict[str, Any], *, is_prediction: bool) -> dict[str, Any]:
    start = float(item.get("startTime", item.get("start", 0.0)))
    end = float(item.get("endTime", item.get("end", start)))
    label = str(item.get("canonicalLabel") or item.get("label") or item.get("productLabel") or "highlight").strip().lower()
    score = float(item.get("score", item.get("rankScore", item.get("confidence", 1.0 if not is_prediction else 0.0))))
    tags = item.get("reviewFeedbackTags") or item.get("reviewTags") or []
    return {
        "videoId": str(item.get("videoId") or item.get("jobId") or item.get("analysisJobId") or "default"),
        "startTime": min(start, end),
        "endTime": max(start, end),
        "label": label,
        "teamId": item.get("teamId") or item.get("teamIdentity") or item.get("team"),
        "score": max(0.0, min(1.0, score)),
        "reviewFeedbackTags": [str(tag) for tag in tags if str(tag)],
    }


def evaluate_clip_rerank(
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    tiou_threshold: float = DEFAULT_TIOU,
    k_values: Iterable[int] = DEFAULT_K_VALUES,
) -> dict[str, Any]:
    normalized_predictions = [normalize_eval_item(item, is_prediction=True) for item in predictions]
    normalized_truth = [normalize_eval_item(item, is_prediction=False) for item in ground_truth]
    ranked_predictions = sorted(normalized_predictions, key=lambda item: item["score"], reverse=True)
    matches = match_predictions(ranked_predictions, normalized_truth, tiou_threshold=tiou_threshold)
    true_positive = sum(1 for match in matches if match["truthIndex"] is not None)
    false_positive = len(ranked_predictions) - true_positive
    false_negative = max(0, len(normalized_truth) - true_positive)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    sorted_k = sorted({max(1, int(value)) for value in k_values})
    return {
        "metricVersion": "clip-rerank-eval-v1",
        "temporalIoUThreshold": tiou_threshold,
        "predictionCount": len(ranked_predictions),
        "groundTruthCount": len(normalized_truth),
        "truePositive": true_positive,
        "falsePositive": false_positive,
        "falseNegative": false_negative,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "ndcg": round(ndcg(ranked_predictions, normalized_truth, tiou_threshold=tiou_threshold), 6),
        "mrr": round(mean_reciprocal_rank(ranked_predictions, normalized_truth, tiou_threshold=tiou_threshold), 6),
        "recallAtK": {
            str(k): round(recall_at_k(ranked_predictions, normalized_truth, k=k, tiou_threshold=tiou_threshold), 6)
            for k in sorted_k
        },
        "precisionAtK": {
            str(k): round(precision_at_k(ranked_predictions, normalized_truth, k=k, tiou_threshold=tiou_threshold), 6)
            for k in sorted_k
        },
        "errorBuckets": dict(error_buckets(matches, ranked_predictions, normalized_truth, tiou_threshold=tiou_threshold)),
    }


def match_predictions(
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    tiou_threshold: float,
) -> list[dict[str, Any]]:
    matched_truth: set[int] = set()
    results: list[dict[str, Any]] = []
    for prediction in predictions:
        match_index = best_unmatched_truth(prediction, ground_truth, matched_truth, tiou_threshold=tiou_threshold)
        if match_index is not None:
            matched_truth.add(match_index)
        results.append({"prediction": prediction, "truthIndex": match_index})
    return results


def precision_at_k(
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    k: int,
    tiou_threshold: float,
) -> float:
    if k <= 0:
        return 0.0
    matches = match_predictions(predictions[:k], ground_truth, tiou_threshold=tiou_threshold)
    return sum(1 for match in matches if match["truthIndex"] is not None) / k


def recall_at_k(
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    k: int,
    tiou_threshold: float,
) -> float:
    if not ground_truth or k <= 0:
        return 0.0
    matches = match_predictions(predictions[:k], ground_truth, tiou_threshold=tiou_threshold)
    return sum(1 for match in matches if match["truthIndex"] is not None) / len(ground_truth)


def mean_reciprocal_rank(
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    tiou_threshold: float,
) -> float:
    if not ground_truth:
        return 0.0
    reciprocal_ranks: list[float] = []
    for truth in ground_truth:
        for rank, prediction in enumerate(predictions, start=1):
            if _is_match(prediction, truth, tiou_threshold=tiou_threshold):
                reciprocal_ranks.append(1.0 / rank)
                break
        else:
            reciprocal_ranks.append(0.0)
    return sum(reciprocal_ranks) / len(ground_truth)


def ndcg(
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    tiou_threshold: float,
) -> float:
    if not predictions or not ground_truth:
        return 0.0
    matched_truth: set[int] = set()
    gains: list[float] = []
    for prediction in predictions:
        match_index = best_unmatched_truth(prediction, ground_truth, matched_truth, tiou_threshold=tiou_threshold)
        if match_index is None:
            gains.append(0.0)
        else:
            matched_truth.add(match_index)
            gains.append(1.0)
    dcg_value = discounted_cumulative_gain(gains)
    ideal_gains = [1.0] * min(len(ground_truth), len(predictions))
    ideal_value = discounted_cumulative_gain(ideal_gains)
    return dcg_value / ideal_value if ideal_value else 0.0


def discounted_cumulative_gain(gains: Sequence[float]) -> float:
    from math import log2

    return sum(gain / log2(index + 2) for index, gain in enumerate(gains))


def best_unmatched_truth(
    prediction: dict[str, Any],
    ground_truth: Sequence[dict[str, Any]],
    matched: set[int],
    *,
    tiou_threshold: float,
) -> int | None:
    best_index: int | None = None
    best_iou = 0.0
    for index, truth in enumerate(ground_truth):
        if index in matched or not _is_match(prediction, truth, tiou_threshold=tiou_threshold):
            continue
        tiou = temporal_iou(prediction, truth)
        if tiou > best_iou:
            best_iou = tiou
            best_index = index
    return best_index


def _is_match(prediction: dict[str, Any], truth: dict[str, Any], *, tiou_threshold: float) -> bool:
    return (
        prediction["videoId"] == truth["videoId"]
        and prediction["label"] == truth["label"]
        and temporal_iou(prediction, truth) >= tiou_threshold
    )


def error_buckets(
    matches: Sequence[dict[str, Any]],
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    tiou_threshold: float,
) -> Counter[str]:
    buckets: Counter[str] = Counter()
    matched_truth = {match["truthIndex"] for match in matches if match["truthIndex"] is not None}
    for match in matches:
        if match["truthIndex"] is not None:
            continue
        prediction = match["prediction"]
        tags = set(prediction.get("reviewFeedbackTags") or [])
        if "duplicate" in tags or _duplicates_prior_match(prediction, predictions, ground_truth, tiou_threshold=tiou_threshold):
            buckets["duplicate"] += 1
        elif "wrong_team" in tags or _team_mismatch(prediction, ground_truth):
            buckets["wrong_team"] += 1
        elif "bad_window" in tags or _has_label_overlap_below_threshold(prediction, ground_truth, tiou_threshold=tiou_threshold):
            buckets["bad_window"] += 1
        elif "wrong_label" in tags or _overlaps_wrong_label(prediction, ground_truth):
            buckets["wrong_label"] += 1
        elif "low_quality" in tags:
            buckets["low_quality"] += 1
        else:
            buckets["false_positive"] += 1
    missed = max(0, len(ground_truth) - len(matched_truth))
    if missed:
        buckets["missing_clip"] += missed
    return buckets


def _duplicates_prior_match(
    prediction: dict[str, Any],
    predictions: Sequence[dict[str, Any]],
    ground_truth: Sequence[dict[str, Any]],
    *,
    tiou_threshold: float,
) -> bool:
    prediction_index = list(predictions).index(prediction)
    earlier = predictions[:prediction_index]
    return any(
        _is_match(candidate, truth, tiou_threshold=tiou_threshold)
        and temporal_iou(candidate, prediction) >= 0.5
        for candidate in earlier
        for truth in ground_truth
    )


def _team_mismatch(prediction: dict[str, Any], ground_truth: Sequence[dict[str, Any]]) -> bool:
    team = prediction.get("teamId")
    if not team:
        return False
    return any(
        prediction["videoId"] == truth["videoId"]
        and temporal_iou(prediction, truth) > 0.25
        and truth.get("teamId")
        and truth.get("teamId") != team
        for truth in ground_truth
    )


def _has_label_overlap_below_threshold(
    prediction: dict[str, Any],
    ground_truth: Sequence[dict[str, Any]],
    *,
    tiou_threshold: float,
) -> bool:
    return any(
        prediction["videoId"] == truth["videoId"]
        and prediction["label"] == truth["label"]
        and 0.0 < temporal_iou(prediction, truth) < tiou_threshold
        for truth in ground_truth
    )


def _overlaps_wrong_label(prediction: dict[str, Any], ground_truth: Sequence[dict[str, Any]]) -> bool:
    return any(
        prediction["videoId"] == truth["videoId"]
        and prediction["label"] != truth["label"]
        and temporal_iou(prediction, truth) >= 0.35
        for truth in ground_truth
    )


def temporal_iou(left: dict[str, Any], right: dict[str, Any]) -> float:
    intersection = max(0.0, min(left["endTime"], right["endTime"]) - max(left["startTime"], right["startTime"]))
    union = max(left["endTime"], right["endTime"]) - min(left["startTime"], right["startTime"])
    return intersection / union if union > 0 else 0.0

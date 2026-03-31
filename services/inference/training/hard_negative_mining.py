from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


DEFAULT_HARD_NEGATIVE_DOMAINS = {
    "hard negative",
    "benchmark eval",
    "manual negative",
    "teacher pseudo",
}

DEFAULT_HARD_NEGATIVE_REASONS = {
    "hard negative",
    "runtime teacher disagree",
    "runtime teacher outcome disagreement",
    "miss vs made conflict",
    "miss vs made disagreement",
    "app facing label only highlight",
    "app facing highlight only",
    "strong ball hoop evidence null subtype",
    "high teacher low runtime",
}


def hard_example_signal(
    row: Mapping[str, Any] | None = None,
    *,
    source_kind: str | None = None,
    source_domain: str | None = None,
    priority_score: float | None = None,
    teacher_confidence: float | None = None,
    reasons: Iterable[str] = (),
) -> float:
    signal = 0.0
    kind = _normalize_text(source_kind)
    domain = _normalize_text(source_domain)
    reason_set = {_normalize_text(reason) for reason in reasons if _normalize_text(reason)}

    if row is not None:
        kind = kind or _normalize_text(row.get("sourceKind"))
        domain = domain or _normalize_text(row.get("sourceDomain"))
        priority_score = _first_float(row, "priorityScore", "priority_score", default=priority_score)
        teacher_confidence = _first_float(row, "teacherConfidence", "teacher_confidence", default=teacher_confidence)
        if priority_score is None:
            priority_score = _feature_float(row, "priorityScore", "priority_score")
        if teacher_confidence is None:
            teacher_confidence = _feature_float(row, "teacherConfidence", "teacher_confidence")
        reason_set |= _row_reason_set(row)

    if kind == "disagreement":
        signal += 0.45
    if domain in DEFAULT_HARD_NEGATIVE_DOMAINS or (domain and "hard_negative" in domain):
        signal += 0.3
    if priority_score is not None:
        signal += 0.2 * min(max(priority_score, 0.0), 1.0)
    if teacher_confidence is not None and teacher_confidence >= 0.9:
        signal += 0.15
    if reason_set & DEFAULT_HARD_NEGATIVE_REASONS:
        signal += 0.25
    if "miss" in reason_set and "made" in reason_set:
        signal += 0.1
    return float(min(max(signal, 0.0), 1.0))


def hard_example_multiplier(
    row: Mapping[str, Any] | None = None,
    *,
    base_multiplier: float = 1.6,
    source_kind: str | None = None,
    source_domain: str | None = None,
    priority_score: float | None = None,
    teacher_confidence: float | None = None,
    reasons: Iterable[str] = (),
) -> float:
    signal = hard_example_signal(
        row,
        source_kind=source_kind,
        source_domain=source_domain,
        priority_score=priority_score,
        teacher_confidence=teacher_confidence,
        reasons=reasons,
    )
    return float(1.0 + max(base_multiplier, 0.0) * signal)


def focal_reweighting(
    probabilities: np.ndarray,
    labels: Sequence[str],
    classes: Sequence[str],
    *,
    gamma: float = 1.5,
) -> np.ndarray:
    if probabilities.size == 0:
        return np.asarray([], dtype=np.float64)
    if probabilities.shape[0] != len(labels):
        raise ValueError("Probability rows and label count must match.")
    if gamma <= 0:
        return np.ones(probabilities.shape[0], dtype=np.float64)
    class_lookup = {str(label): index for index, label in enumerate(classes)}
    label_indices = np.asarray([class_lookup[str(label)] for label in labels], dtype=np.int64)
    chosen = probabilities[np.arange(len(probabilities)), label_indices]
    return np.asarray(np.power(np.clip(1.0 - chosen, 0.0, 1.0), gamma), dtype=np.float64)


def summarize_hard_examples(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    hard_rows = [row for row in rows if hard_example_signal(row) > 0.0]
    return {
        "rowCount": len(rows),
        "hardExampleCount": len(hard_rows),
        "hardExampleRate": round(len(hard_rows) / max(len(rows), 1), 4),
        "bySourceDomain": dict(Counter(_normalize_text(row.get("sourceDomain")) or "unknown" for row in hard_rows)),
        "bySourceKind": dict(Counter(_normalize_text(row.get("sourceKind")) or "unknown" for row in hard_rows)),
    }


def _row_reason_set(row: Mapping[str, Any]) -> set[str]:
    reasons: set[str] = set()
    features = row.get("features")
    if isinstance(features, Mapping):
        for key in features:
            if key.startswith("reason="):
                reasons.add(_normalize_text(key.removeprefix("reason=")))
    if isinstance(row.get("priorityReasons"), (list, tuple, set)):
        reasons |= {_normalize_text(reason) for reason in row["priorityReasons"] if _normalize_text(reason)}
    if isinstance(row.get("reasons"), (list, tuple, set)):
        reasons |= {_normalize_text(reason) for reason in row["reasons"] if _normalize_text(reason)}
    return reasons


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    return text or None


def _first_float(row: Mapping[str, Any], *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        if key in row and row[key] is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric.") from exc
    return default


def _feature_float(row: Mapping[str, Any], *keys: str) -> float | None:
    features = row.get("features")
    if not isinstance(features, Mapping):
        return None
    for key in keys:
        if key in features and features[key] is not None:
            try:
                return float(features[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric.") from exc
    return None

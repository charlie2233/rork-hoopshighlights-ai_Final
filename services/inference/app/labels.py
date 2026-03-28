from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

from .models import RawLabelScore


CANONICAL_ACTION_LABELS: tuple[str, ...] = (
    "dunk",
    "layup",
    "jumper",
    "three",
    "putback",
    "block",
    "steal",
    "fast break",
    "miss",
)

DISPLAY_ACTION_LABELS: dict[str, str] = {
    "dunk": "Dunk",
    "layup": "Layup",
    "jumper": "Made Shot",
    "three": "Three Pointer",
    "putback": "Made Shot",
    "block": "Block",
    "steal": "Steal",
    "fast break": "Fast Break",
    "miss": "Highlight",
    "uncertain": "Highlight",
}

XCLIP_PROMPTS: dict[str, str] = {
    "dunk": "a basketball dunk",
    "layup": "a basketball layup",
    "jumper": "a made basketball jump shot",
    "three": "a made basketball three pointer",
    "putback": "a basketball putback finish",
    "block": "a basketball block on defense",
    "steal": "a basketball steal on defense",
    "fast break": "a basketball fast break transition",
    "miss": "a missed basketball shot",
}

_ALIASES: tuple[tuple[str, str], ...] = (
    ("basketballdunk", "dunk"),
    ("slam dunk", "dunk"),
    ("posterize", "dunk"),
    ("layup", "layup"),
    ("finger roll", "layup"),
    ("putback", "putback"),
    ("tip in", "putback"),
    ("tip-in", "putback"),
    ("put back", "putback"),
    ("three pointer", "three"),
    ("3 pointer", "three"),
    ("3-point", "three"),
    ("3 point", "three"),
    ("three point", "three"),
    ("jump shot", "jumper"),
    ("jumper", "jumper"),
    ("block", "block"),
    ("steal", "steal"),
    ("fast break", "fast break"),
    ("transition", "fast break"),
    ("missed shot", "miss"),
    ("air ball", "miss"),
    ("miss", "miss"),
)


@dataclass
class CanonicalLabelScore:
    label: str
    confidence: float
    raw_label: str | None = None
    model_version: str | None = None


@dataclass(frozen=True)
class BasketballTaxonomy:
    canonical_label: str
    event_family: str
    event_subtype: str | None
    shot_subtype: str | None
    outcome: str
    event_type: str
    shot_type: str
    make_miss: str
    display_label: str
    is_uncertain: bool
    confidence_before_mapping: float
    confidence_after_mapping: float


def normalize_action_label(raw_label: str) -> str:
    normalized = _normalize_text(raw_label)
    for needle, canonical in _ALIASES:
        if needle in normalized:
            return canonical
    if "dunk" in normalized or "posterize" in normalized:
        return "dunk"
    if "layup" in normalized or "finger roll" in normalized:
        return "layup"
    if "putback" in normalized or "tip in" in normalized or "tip-in" in normalized:
        return "putback"
    if "three" in normalized or "3 point" in normalized or "3-point" in normalized:
        return "three"
    if "shot" in normalized or "shoot" in normalized or "jump" in normalized or "jumper" in normalized:
        return "jumper"
    if "block" in normalized:
        return "block"
    if "steal" in normalized:
        return "steal"
    if "break" in normalized or "transition" in normalized:
        return "fast break"
    if "miss" in normalized or "brick" in normalized:
        return "miss"
    return "uncertain"


def canonical_to_display_label(canonical_label: str) -> str:
    return DISPLAY_ACTION_LABELS.get(canonical_label, "Highlight")


def derive_basketball_taxonomy(
    canonical_label: str,
    confidence: float,
    top_labels: Sequence[CanonicalLabelScore] | None = None,
) -> BasketballTaxonomy:
    normalized_label = normalize_action_label(canonical_label)
    ranked_labels = [score for score in (top_labels or []) if score.confidence >= 0.0]
    if not ranked_labels:
        ranked_labels = [CanonicalLabelScore(label=normalized_label, confidence=confidence, raw_label=canonical_label)]

    best_confidence = min(max(float(confidence), 0.0), 1.0)
    second_confidence = _second_confidence(ranked_labels, normalized_label)
    margin = max(best_confidence - second_confidence, 0.0)
    low_confidence = best_confidence < 0.38
    ambiguous = margin < 0.08
    alternate_shot = _alternate_shot_subtype(ranked_labels, exclude={normalized_label, "miss", "uncertain"})

    if normalized_label == "dunk":
        outcome = "made" if not (low_confidence or ambiguous) else "uncertain"
        display_label = "Dunk"
        event_family = "shot"
        event_subtype = None
        shot_subtype = "dunk"
    elif normalized_label == "layup":
        outcome = "made" if not (low_confidence or ambiguous) else "uncertain"
        display_label = "Layup"
        event_family = "shot"
        event_subtype = None
        shot_subtype = "layup"
    elif normalized_label == "three":
        outcome = "made" if not (low_confidence or ambiguous or best_confidence < 0.58) else "uncertain"
        display_label = "Three Pointer" if not low_confidence else "Highlight"
        event_family = "shot"
        event_subtype = None
        shot_subtype = "three"
    elif normalized_label == "putback":
        outcome = "made" if not (low_confidence or ambiguous or best_confidence < 0.6) else "uncertain"
        display_label = "Made Shot" if outcome == "made" else "Highlight"
        event_family = "shot"
        event_subtype = None
        shot_subtype = "putback"
    elif normalized_label == "jumper":
        outcome = "made" if best_confidence >= 0.7 and margin >= 0.12 else "uncertain"
        display_label = "Made Shot" if outcome == "made" else "Highlight"
        event_family = "shot"
        event_subtype = None
        shot_subtype = "jumper"
    elif normalized_label == "miss":
        outcome = "missed"
        display_label = "Highlight"
        event_family = "shot"
        event_subtype = None
        shot_subtype = alternate_shot or "jumper"
    elif normalized_label == "block":
        outcome = "blocked"
        display_label = "Block"
        event_family = "defensive_event"
        event_subtype = "block"
        shot_subtype = alternate_shot
    elif normalized_label == "steal":
        outcome = "uncertain"
        display_label = "Steal"
        event_family = "turnover"
        event_subtype = "steal"
        shot_subtype = None
    elif normalized_label == "fast break":
        outcome = "uncertain"
        display_label = "Fast Break"
        event_family = "transition"
        event_subtype = "fast_break"
        shot_subtype = None
    else:
        outcome = "uncertain"
        display_label = "Highlight"
        event_family = "other"
        event_subtype = "uncertain"
        shot_subtype = alternate_shot

    is_uncertain = outcome == "uncertain" or normalized_label == "uncertain"
    calibrated_confidence = _calibrate_confidence(
        canonical_label=normalized_label,
        best_confidence=best_confidence,
        ambiguous=ambiguous,
        is_uncertain=is_uncertain,
    )

    return BasketballTaxonomy(
        canonical_label=normalized_label,
        event_family=event_family,
        event_subtype=event_subtype,
        shot_subtype=shot_subtype,
        outcome=outcome,
        event_type=event_family,
        shot_type=shot_subtype or event_subtype or "unknown",
        make_miss=_legacy_make_miss(outcome),
        display_label=display_label,
        is_uncertain=is_uncertain,
        confidence_before_mapping=best_confidence,
        confidence_after_mapping=calibrated_confidence,
    )


def build_xclip_prompts() -> list[str]:
    return [XCLIP_PROMPTS[label] for label in CANONICAL_ACTION_LABELS]


def canonical_label_for_prompt(prompt: str) -> str:
    normalized = _normalize_text(prompt)
    for canonical, candidate_prompt in XCLIP_PROMPTS.items():
        if _normalize_text(candidate_prompt) == normalized:
            return canonical
    return normalize_action_label(prompt)


def aggregate_label_scores(scores: Iterable[CanonicalLabelScore]) -> list[CanonicalLabelScore]:
    best_by_label: dict[str, CanonicalLabelScore] = {}
    for score in scores:
        current = best_by_label.get(score.label)
        if current is None or score.confidence > current.confidence:
            best_by_label[score.label] = score
    return sorted(best_by_label.values(), key=lambda item: item.confidence, reverse=True)


def aggregate_raw_label_scores(scores: Iterable[RawLabelScore]) -> list[RawLabelScore]:
    best_by_key: dict[tuple[str, str | None, str | None], RawLabelScore] = {}
    for score in scores:
        key = (_normalize_text(score.rawLabel), score.canonicalLabel, score.modelVersion)
        current = best_by_key.get(key)
        if current is None or score.confidence > current.confidence:
            best_by_key[key] = score
    return sorted(best_by_key.values(), key=lambda item: item.confidence, reverse=True)


def _alternate_shot_subtype(scores: Sequence[CanonicalLabelScore], exclude: set[str]) -> str | None:
    for score in scores:
        if score.label in exclude:
            continue
        if score.label in {"dunk", "layup", "jumper", "three", "putback"}:
            return score.label
    return None


def _second_confidence(scores: Sequence[CanonicalLabelScore], primary_label: str) -> float:
    for score in scores:
        if score.label != primary_label:
            return min(max(score.confidence, 0.0), 1.0)
    return 0.0


def _legacy_make_miss(outcome: str) -> str:
    if outcome == "made":
        return "make"
    if outcome == "missed":
        return "miss"
    return "unknown"


def _calibrate_confidence(
    *,
    canonical_label: str,
    best_confidence: float,
    ambiguous: bool,
    is_uncertain: bool,
) -> float:
    calibrated = min(max(best_confidence, 0.0), 1.0)
    if is_uncertain:
        ceiling = 0.46 if canonical_label in {"jumper", "three", "putback", "miss", "uncertain"} else 0.58
        calibrated = min(calibrated, ceiling)
    if ambiguous:
        calibrated = max(0.0, calibrated - 0.08)
    return round(min(max(calibrated, 0.0), 1.0), 4)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

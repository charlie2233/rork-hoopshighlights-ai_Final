from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


CANONICAL_ACTION_LABELS: tuple[str, ...] = (
    "dunk",
    "layup",
    "jumper",
    "block",
    "steal",
    "fast break",
    "miss",
)

DISPLAY_ACTION_LABELS: dict[str, str] = {
    "dunk": "Dunk",
    "layup": "Layup",
    "jumper": "Made Shot",
    "block": "Block",
    "steal": "Steal",
    "fast break": "Fast Break",
    "miss": "Highlight",
}

XCLIP_PROMPTS: dict[str, str] = {
    "dunk": "a basketball dunk",
    "layup": "a basketball layup",
    "jumper": "a basketball jump shot",
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
    ("jump shot", "jumper"),
    ("jumper", "jumper"),
    ("three pointer", "jumper"),
    ("3 pointer", "jumper"),
    ("three-point", "jumper"),
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


def normalize_action_label(raw_label: str) -> str:
    normalized = _normalize_text(raw_label)
    for needle, canonical in _ALIASES:
        if needle in normalized:
            return canonical
    if "dunk" in normalized or "posterize" in normalized:
        return "dunk"
    if "layup" in normalized or "finger roll" in normalized:
        return "layup"
    if "shot" in normalized or "jump" in normalized or "jumper" in normalized or "three" in normalized:
        return "jumper"
    if "block" in normalized:
        return "block"
    if "steal" in normalized:
        return "steal"
    if "break" in normalized or "transition" in normalized:
        return "fast break"
    if "miss" in normalized or "brick" in normalized:
        return "miss"
    return "jumper"


def canonical_to_display_label(canonical_label: str) -> str:
    return DISPLAY_ACTION_LABELS.get(canonical_label, "Highlight")


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


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

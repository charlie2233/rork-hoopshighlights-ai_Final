from __future__ import annotations

import re
from typing import Optional


JERSEY_COLOR_ALIASES = {
    "black": "black",
    "dark": "black",
    "navy": "blue",
    "blue": "blue",
    "teal": "blue",
    "red": "red",
    "maroon": "red",
    "white": "white",
    "light": "white",
    "yellow": "yellow",
    "gold": "yellow",
    "green": "green",
    "orange": "orange",
    "purple": "purple",
    "gray": "gray",
    "grey": "gray",
    "pink": "pink",
}


def clean_text(value: object, max_length: int = 80) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    return cleaned[:max_length]


def team_key(value: Optional[str]) -> Optional[str]:
    cleaned = clean_text(value)
    return cleaned.lower() if cleaned else None


def resolve_jersey_color(*values: object) -> Optional[str]:
    for value in values:
        cleaned = clean_text(value, max_length=120)
        if cleaned is None:
            continue
        words = re.findall(r"[a-z]+", cleaned.lower())
        for word in words:
            if word in JERSEY_COLOR_ALIASES:
                return JERSEY_COLOR_ALIASES[word]
    return None


def color_labeled_team_name(color_label: str, raw_label: Optional[str]) -> str:
    if raw_label and resolve_jersey_color(raw_label) == color_label:
        return raw_label
    return f"{color_label.title()} jerseys"


def team_identity_matches(
    *,
    selected_team_id: Optional[str],
    selected_color_label: Optional[str],
    selected_label: Optional[str] = None,
    candidate_team_id: Optional[str],
    candidate_color_label: Optional[str],
    candidate_label: Optional[str] = None,
) -> bool:
    if _team_id_color_conflicts_with_explicit_color(selected_team_id, selected_color_label, selected_label):
        return False
    if _team_id_color_conflicts_with_explicit_color(candidate_team_id, candidate_color_label, candidate_label):
        return False

    selected_team_key = team_key(selected_team_id)
    candidate_team_key = team_key(candidate_team_id)
    if selected_team_key and candidate_team_key and selected_team_key == candidate_team_key:
        return True

    selected_color = resolve_jersey_color(selected_color_label, selected_label, selected_team_id)
    candidate_color = resolve_jersey_color(candidate_color_label, candidate_label, candidate_team_id)
    if not selected_color or not candidate_color or selected_color != candidate_color:
        return False

    return True


def _team_id_color_conflicts_with_explicit_color(
    team_id: Optional[str],
    color_label: Optional[str],
    label: Optional[str],
) -> bool:
    team_id_color = resolve_jersey_color(team_id)
    explicit_color = resolve_jersey_color(color_label, label)
    return bool(team_id_color and explicit_color and team_id_color != explicit_color)

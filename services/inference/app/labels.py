from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Sequence

from .models import LabelScore, RawLabelScore


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

XCLIP_PROMPT_SET_VERSION = "xclip-bball-v2"


@dataclass(frozen=True)
class XClipPromptDefinition:
    canonical_label: str
    prompt: str
    kind: str = "positive"


XCLIP_PROMPT_DEFINITIONS: tuple[XClipPromptDefinition, ...] = (
    XClipPromptDefinition("dunk", "a powerful basketball dunk at the rim"),
    XClipPromptDefinition("dunk", "a basketball player rises and slams the ball through the hoop"),
    XClipPromptDefinition("dunk", "an alley-oop dunk finish in a basketball game"),
    XClipPromptDefinition("layup", "a driving basketball layup off the glass"),
    XClipPromptDefinition("layup", "a contested layup at the rim"),
    XClipPromptDefinition("layup", "a finger-roll layup finish in basketball"),
    XClipPromptDefinition("jumper", "a made mid-range basketball jump shot"),
    XClipPromptDefinition("jumper", "a catch-and-shoot jumper in a basketball game"),
    XClipPromptDefinition("jumper", "a step-back jumper in basketball"),
    XClipPromptDefinition("three", "a made basketball three-pointer"),
    XClipPromptDefinition("three", "a catch-and-shoot three from the wing"),
    XClipPromptDefinition("three", "a pull-up three point shot in basketball"),
    XClipPromptDefinition("putback", "a putback tip-in after an offensive rebound"),
    XClipPromptDefinition("putback", "a second-chance basket at the rim"),
    XClipPromptDefinition("putback", "a putback finish in traffic"),
    XClipPromptDefinition("block", "a shot block at the rim in basketball"),
    XClipPromptDefinition("block", "a help-side block in basketball"),
    XClipPromptDefinition("block", "a chasedown block in transition"),
    XClipPromptDefinition("steal", "a basketball steal leading to a fast break"),
    XClipPromptDefinition("steal", "an intercepted pass on defense in basketball"),
    XClipPromptDefinition("steal", "a strip steal in a basketball game"),
    XClipPromptDefinition("fast break", "a fast break transition basket in basketball"),
    XClipPromptDefinition("fast break", "a two-on-one fast break finish"),
    XClipPromptDefinition("fast break", "an open-court transition play in basketball"),
    XClipPromptDefinition("miss", "a missed basketball shot"),
    XClipPromptDefinition("miss", "an airball in a basketball game"),
    XClipPromptDefinition("miss", "a missed layup or three point attempt"),
    XClipPromptDefinition("uncertain", "basketball players jogging back or setting up the offense between plays", kind="background"),
    XClipPromptDefinition("uncertain", "basketball crowd celebration or bench reaction without the live play", kind="background"),
    XClipPromptDefinition("uncertain", "a basketball timeout, replay, or dead-ball stoppage", kind="background"),
    XClipPromptDefinition("uncertain", "a generic basketball hype clip without a clear shot or defensive play", kind="background"),
)

_XCLIP_PROMPT_LOOKUP: dict[str, XClipPromptDefinition] = {
    definition.prompt: definition for definition in XCLIP_PROMPT_DEFINITIONS
}
XCLIP_PROMPT_SET_HASH = hashlib.sha256(
    "\n".join(
        sorted(
            f"{definition.canonical_label}|{definition.kind}|{definition.prompt}"
            for definition in XCLIP_PROMPT_DEFINITIONS
        )
    ).encode("utf-8")
).hexdigest()[:12]

_FAMILY_FOR_LABEL: dict[str, str] = {
    "dunk": "shot",
    "layup": "shot",
    "jumper": "shot",
    "three": "shot",
    "putback": "shot",
    "miss": "shot",
    "block": "defensive_event",
    "steal": "turnover",
    "fast break": "transition",
    "uncertain": "other",
}

_OUTCOME_FOR_LABEL: dict[str, str] = {
    "dunk": "made",
    "layup": "made",
    "jumper": "made",
    "three": "made",
    "putback": "made",
    "miss": "missed",
    "block": "blocked",
    "steal": "uncertain",
    "fast break": "uncertain",
    "uncertain": "uncertain",
}

_SHOT_SUBTYPE_FOR_LABEL: dict[str, str | None] = {
    "dunk": "dunk",
    "layup": "layup",
    "jumper": "jumper",
    "three": "three",
    "putback": "putback",
    "miss": None,
    "block": None,
    "steal": None,
    "fast break": None,
    "uncertain": None,
}

_ALIASES: tuple[tuple[str, str], ...] = (
    ("basketballdunk", "dunk"),
    ("slam dunk", "dunk"),
    ("dunking basketball", "dunk"),
    ("posterize", "dunk"),
    ("layup", "layup"),
    ("lay up", "layup"),
    ("finger roll", "layup"),
    ("putback", "putback"),
    ("tip in", "putback"),
    ("tip-in", "putback"),
    ("put back", "putback"),
    ("three pointer", "three"),
    ("three-pointer", "three"),
    ("3 pointer", "three"),
    ("3-point", "three"),
    ("3 point", "three"),
    ("three point", "three"),
    ("jump shot", "jumper"),
    ("jumper", "jumper"),
    ("mid range jumper", "jumper"),
    ("midrange jumper", "jumper"),
    ("shooting basketball", "jumper"),
    ("block", "block"),
    ("chasedown block", "block"),
    ("steal", "steal"),
    ("strip steal", "steal"),
    ("passing lane steal", "steal"),
    ("fast break", "fast break"),
    ("fastbreak", "fast break"),
    ("transition", "fast break"),
    ("coast to coast", "fast break"),
    ("missed shot", "miss"),
    ("missed basketball shot", "miss"),
    ("air ball", "miss"),
    ("airball", "miss"),
    ("miss", "miss"),
    ("brick", "miss"),
    ("playing basketball", "uncertain"),
    ("dribbling basketball", "uncertain"),
    ("crowd reaction", "uncertain"),
    ("celebration", "uncertain"),
    ("timeout", "uncertain"),
    ("replay", "uncertain"),
)


@dataclass
class CanonicalLabelScore:
    label: str
    confidence: float
    raw_label: str | None = None
    model_version: str | None = None


@dataclass(frozen=True)
class HierarchicalConfidence:
    label: str | None
    confidence_before_mapping: float
    confidence_after_mapping: float
    margin: float
    is_uncertain: bool


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
    event_family_confidence_before_mapping: float
    event_family_confidence_after_mapping: float
    shot_subtype_confidence_before_mapping: float | None
    shot_subtype_confidence_after_mapping: float | None
    outcome_confidence_before_mapping: float
    outcome_confidence_after_mapping: float
    prompt_set_version: str | None = None


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
    if "miss" in normalized or "brick" in normalized or "airball" in normalized:
        return "miss"
    return "uncertain"


def canonical_to_display_label(canonical_label: str) -> str:
    return DISPLAY_ACTION_LABELS.get(canonical_label, "Highlight")


def derive_basketball_taxonomy(
    canonical_label: str,
    confidence: float,
    top_labels: Sequence[CanonicalLabelScore | LabelScore] | None = None,
    *,
    raw_top_labels: Sequence[RawLabelScore] | None = None,
    prompt_set_version: str | None = None,
) -> BasketballTaxonomy:
    ranked_labels = _normalize_ranked_labels(top_labels, canonical_label, confidence)
    primary_label = ranked_labels[0].label
    confidence_before_mapping = min(
        max(float(confidence if confidence > 0 else ranked_labels[0].confidence), 0.0),
        1.0,
    )

    family_confidence = _calibrate_dimension(
        _normalize_distribution(_score_dimension(ranked_labels, _family_key_for_label)),
        uncertainty_label="other",
        min_confidence=0.34,
        min_margin=0.06,
        uncertain_cap=0.48,
    )
    event_family = family_confidence.label or "other"

    shot_confidence: HierarchicalConfidence | None = None
    shot_subtype: str | None = None
    if event_family == "shot":
        shot_confidence = _calibrate_dimension(
            _normalize_distribution(_score_shot_subtypes(ranked_labels)),
            uncertainty_label=None,
            min_confidence=0.28,
            min_margin=0.05,
            uncertain_cap=0.52,
        )
        shot_subtype = shot_confidence.label or _alternate_shot_subtype(ranked_labels, exclude={"miss", "uncertain"})

    outcome_confidence = _calibrate_dimension(
        _normalize_distribution(_score_outcomes(ranked_labels, event_family=event_family)),
        uncertainty_label="uncertain",
        min_confidence=0.38,
        min_margin=0.08,
        uncertain_cap=0.46,
    )
    outcome = _resolve_outcome(event_family, outcome_confidence.label)

    event_subtype = _resolve_event_subtype(event_family)
    canonical = _resolve_canonical_label(
        primary_label=primary_label,
        event_family=event_family,
        shot_subtype=shot_subtype,
        outcome=outcome,
    )
    display_label = _resolve_display_label(
        event_family=event_family,
        shot_subtype=shot_subtype,
        outcome=outcome,
        shot_confidence=shot_confidence,
        outcome_confidence=outcome_confidence,
    )
    event_type = _resolve_event_type(event_family, shot_subtype)
    shot_type = shot_subtype or event_subtype or "unknown"
    is_uncertain = (
        event_family == "other"
        or (shot_confidence.is_uncertain if shot_confidence else False)
        or outcome_confidence.is_uncertain
        or canonical == "uncertain"
    )
    confidence_after_mapping = _resolve_display_confidence(
        display_label=display_label,
        family_confidence=family_confidence,
        shot_confidence=shot_confidence,
        outcome_confidence=outcome_confidence,
        is_uncertain=is_uncertain,
    )

    return BasketballTaxonomy(
        canonical_label=canonical,
        event_family=event_family,
        event_subtype=event_subtype,
        shot_subtype=shot_subtype,
        outcome=outcome,
        event_type=event_type,
        shot_type=shot_type,
        make_miss=_legacy_make_miss(outcome),
        display_label=display_label,
        is_uncertain=is_uncertain,
        confidence_before_mapping=round(confidence_before_mapping, 4),
        confidence_after_mapping=round(confidence_after_mapping, 4),
        event_family_confidence_before_mapping=family_confidence.confidence_before_mapping,
        event_family_confidence_after_mapping=family_confidence.confidence_after_mapping,
        shot_subtype_confidence_before_mapping=shot_confidence.confidence_before_mapping if shot_confidence else None,
        shot_subtype_confidence_after_mapping=shot_confidence.confidence_after_mapping if shot_confidence else None,
        outcome_confidence_before_mapping=outcome_confidence.confidence_before_mapping,
        outcome_confidence_after_mapping=outcome_confidence.confidence_after_mapping,
        prompt_set_version=prompt_set_version,
    )


def build_xclip_prompts() -> list[str]:
    return [definition.prompt for definition in XCLIP_PROMPT_DEFINITIONS]


def canonical_label_for_prompt(prompt: str) -> str:
    definition = _XCLIP_PROMPT_LOOKUP.get(prompt)
    if definition is not None:
        return definition.canonical_label
    return normalize_action_label(prompt)


def xclip_prompt_set_version() -> str:
    return XCLIP_PROMPT_SET_VERSION


def xclip_prompt_set_hash() -> str:
    return XCLIP_PROMPT_SET_HASH


def aggregate_label_scores(scores: Iterable[CanonicalLabelScore]) -> list[CanonicalLabelScore]:
    best_by_label: dict[str, CanonicalLabelScore] = {}
    for score in scores:
        current = best_by_label.get(score.label)
        if current is None or score.confidence > current.confidence:
            best_by_label[score.label] = score
    return sorted(best_by_label.values(), key=lambda item: item.confidence, reverse=True)


def sum_label_scores(scores: Iterable[LabelScore | CanonicalLabelScore]) -> list[LabelScore]:
    totals: dict[str, float] = {}
    exemplar: dict[str, tuple[str | None, str | None, float]] = {}
    for score in scores:
        label = normalize_action_label(getattr(score, "label", "uncertain"))
        totals[label] = totals.get(label, 0.0) + min(max(float(score.confidence), 0.0), 1.0)
        current_raw, current_model, current_best = exemplar.get(label, (None, None, -1.0))
        if current_raw is None or float(score.confidence) >= current_best:
            exemplar[label] = (
                getattr(score, "rawLabel", None) or getattr(score, "raw_label", None),
                getattr(score, "modelVersion", None) or getattr(score, "model_version", None),
                float(score.confidence),
            )
        else:
            exemplar[label] = (current_raw, current_model, current_best)

    return sorted(
        [
            LabelScore(
                label=label,
                confidence=round(min(max(value, 0.0), 1.0), 4),
                rawLabel=exemplar[label][0],
                modelVersion=exemplar[label][1],
            )
            for label, value in totals.items()
        ],
        key=lambda item: item.confidence,
        reverse=True,
    )


def blend_label_scores(weighted_scores: Iterable[tuple[float, Sequence[LabelScore | CanonicalLabelScore]]]) -> list[LabelScore]:
    totals: dict[str, float] = {}
    exemplars: dict[str, tuple[str | None, str | None, float]] = {}
    total_weight = 0.0
    for weight, scores in weighted_scores:
        safe_weight = max(float(weight), 0.0)
        if safe_weight <= 0:
            continue
        total_weight += safe_weight
        for score in scores:
            label = normalize_action_label(getattr(score, "label", "uncertain"))
            totals[label] = totals.get(label, 0.0) + (safe_weight * min(max(float(score.confidence), 0.0), 1.0))
            current = exemplars.get(label)
            if current is None or float(score.confidence) > current[2]:
                exemplars[label] = (
                    getattr(score, "rawLabel", None) or getattr(score, "raw_label", None),
                    getattr(score, "modelVersion", None) or getattr(score, "model_version", None),
                    float(score.confidence),
                )

    if total_weight <= 0:
        return []

    return sorted(
        [
            LabelScore(
                label=label,
                confidence=round(min(max(value / total_weight, 0.0), 1.0), 4),
                rawLabel=exemplars.get(label, (None, None, 0.0))[0],
                modelVersion=exemplars.get(label, (None, None, 0.0))[1],
            )
            for label, value in totals.items()
        ],
        key=lambda item: item.confidence,
        reverse=True,
    )


def aggregate_raw_label_scores(scores: Iterable[RawLabelScore]) -> list[RawLabelScore]:
    best_by_key: dict[tuple[str, str | None, str | None], RawLabelScore] = {}
    for score in scores:
        key = (_normalize_text(score.rawLabel), score.canonicalLabel, score.modelVersion)
        current = best_by_key.get(key)
        if current is None or score.confidence > current.confidence:
            best_by_key[key] = score
    return sorted(best_by_key.values(), key=lambda item: item.confidence, reverse=True)


def blend_raw_label_scores(weighted_scores: Iterable[tuple[float, Sequence[RawLabelScore]]]) -> list[RawLabelScore]:
    totals: dict[tuple[str, str | None, str | None], float] = {}
    total_weight = 0.0
    for weight, scores in weighted_scores:
        safe_weight = max(float(weight), 0.0)
        if safe_weight <= 0:
            continue
        total_weight += safe_weight
        for score in scores:
            key = (score.rawLabel, score.canonicalLabel, score.modelVersion)
            totals[key] = totals.get(key, 0.0) + (safe_weight * min(max(score.confidence, 0.0), 1.0))

    if total_weight <= 0:
        return []

    blended = [
        RawLabelScore(
            rawLabel=raw_label,
            canonicalLabel=canonical_label,
            modelVersion=model_version,
            confidence=round(min(max(value / total_weight, 0.0), 1.0), 4),
        )
        for (raw_label, canonical_label, model_version), value in totals.items()
    ]
    return sorted(blended, key=lambda item: item.confidence, reverse=True)


def _normalize_ranked_labels(
    top_labels: Sequence[CanonicalLabelScore | LabelScore] | None,
    fallback_label: str,
    fallback_confidence: float,
) -> list[CanonicalLabelScore]:
    normalized_scores: list[CanonicalLabelScore] = []
    for score in top_labels or []:
        normalized_scores.append(
            CanonicalLabelScore(
                label=normalize_action_label(getattr(score, "label", fallback_label)),
                confidence=min(max(float(score.confidence), 0.0), 1.0),
                raw_label=getattr(score, "rawLabel", None) or getattr(score, "raw_label", None),
                model_version=getattr(score, "modelVersion", None) or getattr(score, "model_version", None),
            )
        )

    if not normalized_scores:
        normalized_scores.append(
            CanonicalLabelScore(
                label=normalize_action_label(fallback_label),
                confidence=min(max(float(fallback_confidence), 0.0), 1.0),
                raw_label=fallback_label,
            )
        )

    ranked = aggregate_label_scores(normalized_scores)
    if ranked:
        return ranked
    return [
        CanonicalLabelScore(
            label=normalize_action_label(fallback_label),
            confidence=min(max(float(fallback_confidence), 0.0), 1.0),
            raw_label=fallback_label,
        )
    ]


def _score_dimension(
    scores: Sequence[CanonicalLabelScore],
    key_resolver,
) -> dict[str, float]:
    totals: dict[str, float] = {}
    for score in scores:
        key = key_resolver(score.label)
        totals[key] = totals.get(key, 0.0) + min(max(score.confidence, 0.0), 1.0)
    return totals


def _score_shot_subtypes(scores: Sequence[CanonicalLabelScore]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for score in scores:
        subtype = _SHOT_SUBTYPE_FOR_LABEL.get(score.label)
        if subtype is None:
            continue
        totals[subtype] = totals.get(subtype, 0.0) + min(max(score.confidence, 0.0), 1.0)
    return totals


def _score_outcomes(scores: Sequence[CanonicalLabelScore], *, event_family: str) -> dict[str, float]:
    totals: dict[str, float] = {"uncertain": 0.0}
    for score in scores:
        label = score.label
        outcome = _OUTCOME_FOR_LABEL.get(label, "uncertain")
        family = _family_key_for_label(label)
        if event_family == "shot":
            if family == "shot":
                totals[outcome] = totals.get(outcome, 0.0) + min(max(score.confidence, 0.0), 1.0)
            else:
                totals["uncertain"] = totals.get("uncertain", 0.0) + (0.35 * min(max(score.confidence, 0.0), 1.0))
        elif event_family == "defensive_event":
            if label == "block":
                totals["blocked"] = totals.get("blocked", 0.0) + min(max(score.confidence, 0.0), 1.0)
            else:
                totals["uncertain"] = totals.get("uncertain", 0.0) + (0.35 * min(max(score.confidence, 0.0), 1.0))
        else:
            totals["uncertain"] = totals.get("uncertain", 0.0) + min(max(score.confidence, 0.0), 1.0)
    return totals


def _normalize_distribution(scores: dict[str, float]) -> dict[str, float]:
    filtered = {key: min(max(value, 0.0), 1.0) for key, value in scores.items() if value > 0}
    total = sum(filtered.values())
    if total <= 0:
        return {}
    return {
        key: round(min(max(value / total, 0.0), 1.0), 4)
        for key, value in filtered.items()
    }


def _calibrate_dimension(
    distribution: dict[str, float],
    *,
    uncertainty_label: str | None,
    min_confidence: float,
    min_margin: float,
    uncertain_cap: float,
) -> HierarchicalConfidence:
    if not distribution:
        return HierarchicalConfidence(
            label=uncertainty_label,
            confidence_before_mapping=0.0,
            confidence_after_mapping=0.0,
            margin=0.0,
            is_uncertain=True,
        )

    ranked = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
    top_label, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = round(max(top_score - second_score, 0.0), 4)
    uncertain = top_score < min_confidence or margin < min_margin or top_label == uncertainty_label
    calibrated = top_score
    if margin < min_margin:
        calibrated = max(0.0, calibrated - (min_margin - margin))
    if uncertain:
        calibrated = min(calibrated, uncertain_cap)
    chosen_label = uncertainty_label if uncertain and uncertainty_label is not None else top_label

    return HierarchicalConfidence(
        label=chosen_label,
        confidence_before_mapping=round(min(max(top_score, 0.0), 1.0), 4),
        confidence_after_mapping=round(min(max(calibrated, 0.0), 1.0), 4),
        margin=margin,
        is_uncertain=uncertain,
    )


def _resolve_event_subtype(event_family: str) -> str | None:
    if event_family == "defensive_event":
        return "block"
    if event_family == "turnover":
        return "steal"
    if event_family == "transition":
        return "fast_break"
    if event_family == "other":
        return "uncertain"
    return None


def _resolve_outcome(event_family: str, chosen_outcome: str | None) -> str:
    if event_family == "defensive_event":
        return "blocked"
    if event_family != "shot":
        return "uncertain"
    return chosen_outcome or "uncertain"


def _resolve_canonical_label(
    *,
    primary_label: str,
    event_family: str,
    shot_subtype: str | None,
    outcome: str,
) -> str:
    if event_family == "shot":
        if outcome == "missed":
            return "miss"
        if shot_subtype:
            return shot_subtype
        return primary_label if primary_label in {"jumper", "three", "dunk", "layup", "putback"} else "uncertain"
    if event_family == "defensive_event":
        return "block"
    if event_family == "turnover":
        return "steal"
    if event_family == "transition":
        return "fast break"
    return "uncertain"


def _resolve_display_label(
    *,
    event_family: str,
    shot_subtype: str | None,
    outcome: str,
    shot_confidence: HierarchicalConfidence | None,
    outcome_confidence: HierarchicalConfidence,
) -> str:
    if event_family == "defensive_event":
        return "Block"
    if event_family == "turnover":
        return "Steal"
    if event_family == "transition":
        return "Fast Break"
    if event_family != "shot":
        return "Highlight"

    shot_after = shot_confidence.confidence_after_mapping if shot_confidence else 0.0
    if shot_subtype == "dunk" and shot_after >= 0.3:
        return "Dunk"
    if shot_subtype == "layup" and shot_after >= 0.3:
        return "Layup"
    if shot_subtype == "three" and shot_after >= 0.34 and outcome != "missed":
        return "Three Pointer"
    if shot_subtype in {"jumper", "putback"} and outcome == "made" and outcome_confidence.confidence_after_mapping >= 0.38:
        return "Made Shot"
    return "Highlight"


def _resolve_event_type(event_family: str, shot_subtype: str | None) -> str:
    if event_family == "shot":
        if shot_subtype in {"three", "jumper"}:
            return "perimeter_shot"
        if shot_subtype in {"dunk", "layup", "putback"}:
            return "rim_finish"
        return "shot"
    if event_family == "defensive_event":
        return "shot_contest"
    if event_family == "turnover":
        return "live_ball_turnover"
    if event_family == "transition":
        return "transition_play"
    return "other"


def _resolve_display_confidence(
    *,
    display_label: str,
    family_confidence: HierarchicalConfidence,
    shot_confidence: HierarchicalConfidence | None,
    outcome_confidence: HierarchicalConfidence,
    is_uncertain: bool,
) -> float:
    family_after = family_confidence.confidence_after_mapping
    shot_after = shot_confidence.confidence_after_mapping if shot_confidence else 0.0
    outcome_after = outcome_confidence.confidence_after_mapping

    if display_label in {"Block", "Steal", "Fast Break"}:
        confidence = family_after
    elif display_label in {"Dunk", "Layup", "Three Pointer"}:
        confidence = max(family_after, shot_after)
    elif display_label == "Made Shot":
        confidence = min(max(family_after, shot_after), max(outcome_after, 0.3))
    else:
        confidence = max(family_after, shot_after, outcome_after)

    if is_uncertain and display_label == "Highlight":
        confidence = min(confidence, 0.46)
    return round(min(max(confidence, 0.0), 1.0), 4)


def _alternate_shot_subtype(scores: Sequence[CanonicalLabelScore], exclude: set[str]) -> str | None:
    for score in scores:
        if score.label in exclude:
            continue
        if score.label in {"dunk", "layup", "jumper", "three", "putback"}:
            return score.label
    return None


def _family_key_for_label(label: str) -> str:
    return _FAMILY_FOR_LABEL.get(label, "other")


def _legacy_make_miss(outcome: str) -> str:
    if outcome == "made":
        return "make"
    if outcome == "missed":
        return "miss"
    return "unknown"


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

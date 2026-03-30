from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .models import ActionPrediction, LabelScore


RUNTIME_FUSION_SCHEMA_VERSION = "runtime-fusion-v1"
RUNTIME_FUSION_PATH = Path(__file__).resolve().parents[1] / "models" / "runtime_fusion_v1.json"
MAX_RUNTIME_TOPK = 3

EVENT_FAMILIES = ("shot_attempt", "turnover", "defensive_event", "transition", "other")
OUTCOMES = ("made", "missed", "blocked", "uncertain")
SHOT_SUBTYPES = ("dunk", "layup", "jumper", "three", "putback", "null")


@dataclass(frozen=True)
class RuntimeTargetPrediction:
    label: str
    confidence: float
    margin: float
    distribution: dict[str, float]
    top_labels: tuple[LabelScore, ...]
    is_uncertain: bool


@dataclass(frozen=True)
class RuntimeFusionPrediction:
    model_version: str
    event_family: str
    outcome: str
    shot_subtype: str | None
    canonical_label: str
    display_label: str
    confidence_before_mapping: float
    confidence_after_mapping: float
    event_family_confidence_before_mapping: float
    event_family_confidence_after_mapping: float
    shot_subtype_confidence_before_mapping: float | None
    shot_subtype_confidence_after_mapping: float | None
    outcome_confidence_before_mapping: float
    outcome_confidence_after_mapping: float
    is_uncertain: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RuntimeTargetModel:
    name: str
    classes: tuple[str, ...]
    intercept: tuple[float, ...]
    coefficients: tuple[tuple[float, ...], ...]
    temperature: float
    uncertainty_threshold: float
    margin_threshold: float
    top_k: int = MAX_RUNTIME_TOPK

    def predict(self, feature_vector: np.ndarray) -> RuntimeTargetPrediction:
        logits = np.matmul(np.asarray(self.coefficients, dtype=np.float64), feature_vector) + np.asarray(
            self.intercept,
            dtype=np.float64,
        )
        probabilities = _softmax(logits / max(self.temperature, 1e-3))
        ranked_indices = list(np.argsort(probabilities)[::-1])
        top_index = ranked_indices[0]
        second_probability = float(probabilities[ranked_indices[1]]) if len(ranked_indices) > 1 else 0.0
        top_probability = float(probabilities[top_index])
        margin = max(top_probability - second_probability, 0.0)
        is_uncertain = top_probability < self.uncertainty_threshold or margin < self.margin_threshold
        distribution = {
            str(label): round(float(probabilities[index]), 4)
            for index, label in enumerate(self.classes)
        }
        top_labels = tuple(
            LabelScore(label=str(self.classes[index]), confidence=round(float(probabilities[index]), 4))
            for index in ranked_indices[: self.top_k]
        )
        return RuntimeTargetPrediction(
            label=str(self.classes[top_index]),
            confidence=round(top_probability, 4),
            margin=round(margin, 4),
            distribution=distribution,
            top_labels=top_labels,
            is_uncertain=is_uncertain,
        )


@dataclass(frozen=True)
class RuntimeFusionBundle:
    schema_version: str
    feature_schema_version: str
    model_version: str
    trained_at: str
    source_dataset: str
    notes: tuple[str, ...]
    feature_names: tuple[str, ...]
    feature_index: dict[str, int]
    targets: dict[str, RuntimeTargetModel]

    def vectorize(self, feature_dict: dict[str, float]) -> np.ndarray:
        vector = np.zeros(len(self.feature_names), dtype=np.float64)
        for feature_name, value in feature_dict.items():
            index = self.feature_index.get(feature_name)
            if index is None:
                continue
            vector[index] = float(value)
        return vector

    def predict_from_snapshot(self, snapshot: dict[str, Any]) -> RuntimeFusionPrediction:
        feature_dict = build_runtime_feature_dict(snapshot)
        vector = self.vectorize(feature_dict)
        family_prediction = self.targets["eventFamily"].predict(vector)
        outcome_prediction = self.targets["outcome"].predict(vector)
        subtype_prediction = self.targets["shotSubtype"].predict(vector)

        event_family = family_prediction.label
        if family_prediction.is_uncertain:
            event_family = "other"

        outcome = _resolve_runtime_outcome(event_family, outcome_prediction)
        shot_subtype: str | None = None
        if event_family == "shot_attempt" and not subtype_prediction.is_uncertain and subtype_prediction.label != "null":
            shot_subtype = subtype_prediction.label

        canonical_label, display_label = derive_runtime_display_label(
            event_family=event_family,
            outcome=outcome,
            shot_subtype=shot_subtype,
        )
        is_uncertain = (
            family_prediction.is_uncertain
            or outcome_prediction.is_uncertain
            or (event_family == "shot_attempt" and shot_subtype is None and outcome != "made")
            or display_label == "Highlight"
        )
        confidence_before_mapping = family_prediction.confidence
        confidence_after_mapping = _resolve_runtime_confidence(
            display_label=display_label,
            family_prediction=family_prediction,
            outcome_prediction=outcome_prediction,
            subtype_prediction=subtype_prediction,
            is_uncertain=is_uncertain,
        )

        metadata = {
            "runtime_fusion_model_version": self.model_version,
            "runtime_fusion_schema_version": self.schema_version,
            "runtime_fusion_feature_schema_version": self.feature_schema_version,
            "runtime_fusion_family_distribution": family_prediction.distribution,
            "runtime_fusion_outcome_distribution": outcome_prediction.distribution,
            "runtime_fusion_subtype_distribution": subtype_prediction.distribution,
            "runtime_fusion_family_top_labels": [item.model_dump(mode="json") for item in family_prediction.top_labels],
            "runtime_fusion_outcome_top_labels": [item.model_dump(mode="json") for item in outcome_prediction.top_labels],
            "runtime_fusion_subtype_top_labels": [item.model_dump(mode="json") for item in subtype_prediction.top_labels],
            "runtime_fusion_snapshot": summarize_runtime_snapshot(snapshot),
        }
        return RuntimeFusionPrediction(
            model_version=self.model_version,
            event_family=event_family,
            outcome=outcome,
            shot_subtype=shot_subtype,
            canonical_label=canonical_label,
            display_label=display_label,
            confidence_before_mapping=round(confidence_before_mapping, 4),
            confidence_after_mapping=round(confidence_after_mapping, 4),
            event_family_confidence_before_mapping=family_prediction.confidence,
            event_family_confidence_after_mapping=round(
                min(max(max(family_prediction.confidence - (0.0 if not family_prediction.is_uncertain else 0.08), 0.0), 0.0), 1.0),
                4,
            ),
            shot_subtype_confidence_before_mapping=subtype_prediction.confidence if shot_subtype is not None else None,
            shot_subtype_confidence_after_mapping=(
                round(max(subtype_prediction.confidence - (0.0 if not subtype_prediction.is_uncertain else 0.06), 0.0), 4)
                if shot_subtype is not None
                else None
            ),
            outcome_confidence_before_mapping=outcome_prediction.confidence,
            outcome_confidence_after_mapping=round(
                max(outcome_prediction.confidence - (0.0 if not outcome_prediction.is_uncertain else 0.06), 0.0),
                4,
            ),
            is_uncertain=is_uncertain,
            metadata=metadata,
        )


def build_runtime_snapshot(
    *,
    action: ActionPrediction,
    structured_signals: dict[str, Any],
    primary_action: ActionPrediction | None = None,
    comparison_action: ActionPrediction | None = None,
    source_kind: str | None = None,
    source_domain: str | None = None,
    source_set: str | None = None,
    source_ref: str | None = None,
    human_verified: bool = False,
    ball_visible: bool | None = None,
    hoop_visible: bool | None = None,
    priority_score: float | None = None,
    reasons: Sequence[str] = (),
    clip_duration_seconds: float | None = None,
    event_center_seconds: float | None = None,
    pre_roll_seconds: float | None = None,
    post_roll_seconds: float | None = None,
    source_event_count: int | None = None,
    was_merged: bool | None = None,
) -> dict[str, Any]:
    return {
        "label": action.label,
        "canonicalLabel": action.canonicalLabel,
        "confidence": action.confidence,
        "eventFamily": action.eventFamily,
        "outcome": action.outcome,
        "shotSubtype": action.shotSubtype,
        "isUncertain": action.isUncertain,
        "promptSetVersion": action.promptSetVersion,
        "clipDurationSeconds": clip_duration_seconds,
        "eventCenterSeconds": event_center_seconds,
        "preRollSeconds": pre_roll_seconds,
        "postRollSeconds": post_roll_seconds,
        "sourceEventCount": source_event_count,
        "wasMerged": was_merged,
        "sourceKind": source_kind,
        "sourceDomain": source_domain,
        "sourceSet": source_set,
        "sourceRef": source_ref,
        "humanVerified": human_verified,
        "ballVisible": ball_visible,
        "hoopVisible": hoop_visible,
        "priorityScore": priority_score,
        "reasons": list(reasons),
        "structuredSignals": dict(structured_signals),
        "topKLabels": [item.label for item in list(action.topLabels)[:MAX_RUNTIME_TOPK]],
        "videoMAE": {
            "modelVersion": getattr(primary_action, "modelVersion", None),
            "topK": [item.model_dump(mode="json") for item in list(getattr(primary_action, "topLabels", []))[:MAX_RUNTIME_TOPK]],
        },
        "xclip": {
            "modelVersion": getattr(comparison_action, "modelVersion", None),
            "topK": [item.model_dump(mode="json") for item in list(getattr(comparison_action, "topLabels", []))[:MAX_RUNTIME_TOPK]],
        },
    }


def build_runtime_feature_dict(snapshot: dict[str, Any]) -> dict[str, float]:
    structured_signals = snapshot.get("structuredSignals") or {}
    source_domain = snapshot.get("sourceDomain")
    source_set = snapshot.get("sourceSet")
    source_kind = snapshot.get("sourceKind")
    source_ref = snapshot.get("sourceRef")
    ball_visible = snapshot.get("ballVisible")
    hoop_visible = snapshot.get("hoopVisible")
    reasons = snapshot.get("reasons") or []
    features: dict[str, float] = {
        "sourceRefPresent": 1.0 if source_ref else 0.0,
        "humanVerified": 1.0 if snapshot.get("humanVerified") else 0.0,
        "ballVisible": 1.0 if ball_visible else 0.0,
        "hoopVisible": 1.0 if hoop_visible else 0.0,
        "runtimeConfidence": _coerce_float(snapshot.get("confidence"), default=0.0),
        "runtimeTopCount": float(len(snapshot.get("topKLabels") or [])),
        "clipDurationSeconds": _coerce_float(snapshot.get("clipDurationSeconds"), default=0.0),
        "eventCenterSeconds": _coerce_float(snapshot.get("eventCenterSeconds"), default=0.0),
        "preRollSeconds": _coerce_float(snapshot.get("preRollSeconds"), default=0.0),
        "postRollSeconds": _coerce_float(snapshot.get("postRollSeconds"), default=0.0),
        "sourceEventCount": _coerce_float(snapshot.get("sourceEventCount"), default=1.0),
        "wasMerged": 1.0 if snapshot.get("wasMerged") else 0.0,
    }
    for key, value in sorted(structured_signals.items()):
        features[key] = _coerce_float(value, default=0.0)

    _add_training_feature_categorical(features, "sourceDomain", source_domain)
    _add_training_feature_categorical(features, "sourceSet", source_set)
    _add_training_feature_categorical(features, "sourceKind", source_kind)
    _add_training_feature_categorical(features, "runtimeLabel", snapshot.get("label"))
    _add_training_feature_categorical(features, "runtimeEventFamily", snapshot.get("eventFamily"))
    _add_training_feature_categorical(features, "runtimeOutcome", snapshot.get("outcome"))
    _add_training_feature_categorical(features, "runtimeShotSubtype", snapshot.get("shotSubtype") or "null")

    runtime_topk = snapshot.get("topKLabels") or []
    _add_training_feature_categorical(features, "runtimeTop1", _top_label(runtime_topk))
    _add_training_feature_categorical(features, "runtimeVideoMAE", _top_label((snapshot.get("videoMAE") or {}).get("topK") or []))
    _add_training_feature_categorical(features, "runtimeXCLIP", _top_label((snapshot.get("xclip") or {}).get("topK") or []))

    for reason in reasons:
        _add_training_feature_categorical(features, "reason", reason)

    _add_ranked_labels(features, "runtime_topk", runtime_topk)
    _add_ranked_labels(features, "videomae_topk", (snapshot.get("videoMAE") or {}).get("topK") or [])
    _add_ranked_labels(features, "xclip_topk", (snapshot.get("xclip") or {}).get("topK") or [])

    runtime_top1 = _top_label(runtime_topk)
    videomae_top1 = _top_label((snapshot.get("videoMAE") or {}).get("topK") or [])
    xclip_top1 = _top_label((snapshot.get("xclip") or {}).get("topK") or [])
    features["runtime_videomae_top1_match"] = 1.0 if runtime_top1 and runtime_top1 == videomae_top1 else 0.0
    features["runtime_xclip_top1_match"] = 1.0 if runtime_top1 and runtime_top1 == xclip_top1 else 0.0
    features["videomae_xclip_top1_match"] = 1.0 if videomae_top1 and videomae_top1 == xclip_top1 else 0.0
    return features


def summarize_runtime_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": snapshot.get("label"),
        "canonicalLabel": snapshot.get("canonicalLabel"),
        "eventFamily": snapshot.get("eventFamily"),
        "outcome": snapshot.get("outcome"),
        "shotSubtype": snapshot.get("shotSubtype"),
        "confidence": round(_coerce_float(snapshot.get("confidence"), default=0.0), 4),
        "clipDurationSeconds": round(_coerce_float(snapshot.get("clipDurationSeconds"), default=0.0), 4),
        "structuredSignals": {
            key: round(_coerce_float(value, default=0.0), 4)
            for key, value in (snapshot.get("structuredSignals") or {}).items()
        },
        "topKLabels": list(snapshot.get("topKLabels") or [])[:MAX_RUNTIME_TOPK],
        "videoMAE": (snapshot.get("videoMAE") or {}).get("topK") or [],
        "xclip": (snapshot.get("xclip") or {}).get("topK") or [],
    }


def derive_runtime_display_label(
    *,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
) -> tuple[str, str]:
    if event_family == "turnover":
        return "steal", "Steal"
    if event_family == "transition":
        return "fast break", "Fast Break"
    if event_family == "defensive_event":
        return ("block", "Block") if outcome == "blocked" else ("uncertain", "Highlight")
    if event_family != "shot_attempt":
        return "uncertain", "Highlight"

    if outcome == "missed":
        return "miss", "Highlight"
    if outcome == "blocked":
        return "block", "Block"
    if shot_subtype == "dunk" and outcome == "made":
        return "dunk", "Dunk"
    if shot_subtype == "layup" and outcome == "made":
        return "layup", "Layup"
    if shot_subtype == "three" and outcome == "made":
        return "three", "Three Pointer"
    if shot_subtype == "putback" and outcome == "made":
        return "putback", "Made Shot"
    if outcome == "made":
        return shot_subtype or "jumper", "Made Shot"
    return shot_subtype or "uncertain", "Highlight"


def load_runtime_fusion_bundle(path: Path | None = None) -> RuntimeFusionBundle:
    bundle_path = path or RUNTIME_FUSION_PATH
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    feature_names = tuple(str(item) for item in payload.get("featureNames", []))
    targets: dict[str, RuntimeTargetModel] = {}
    for target_name, target_payload in (payload.get("targets") or {}).items():
        targets[str(target_name)] = RuntimeTargetModel(
            name=str(target_name),
            classes=tuple(str(item) for item in target_payload.get("classes", [])),
            intercept=tuple(float(item) for item in target_payload.get("intercept", [])),
            coefficients=tuple(tuple(float(value) for value in row) for row in target_payload.get("coefficients", [])),
            temperature=float(target_payload.get("temperature", 1.0)),
            uncertainty_threshold=float(target_payload.get("uncertaintyThreshold", 0.45)),
            margin_threshold=float(target_payload.get("marginThreshold", 0.05)),
            top_k=int(target_payload.get("topK", MAX_RUNTIME_TOPK)),
        )
    return RuntimeFusionBundle(
        schema_version=str(payload.get("schemaVersion", RUNTIME_FUSION_SCHEMA_VERSION)),
        feature_schema_version=str(payload.get("featureSchemaVersion", "runtime-feature-v1")),
        model_version=str(payload.get("modelVersion", "runtime-fusion-v1")),
        trained_at=str(payload.get("trainedAt", "")),
        source_dataset=str(payload.get("sourceDataset", "")),
        notes=tuple(str(item) for item in payload.get("notes", []) if item is not None),
        feature_names=feature_names,
        feature_index={name: index for index, name in enumerate(feature_names)},
        targets=targets,
    )


@lru_cache(maxsize=1)
def get_runtime_fusion_bundle(path: str | None = None) -> RuntimeFusionBundle | None:
    bundle_path = Path(path) if path else RUNTIME_FUSION_PATH
    if not bundle_path.exists():
        return None
    return load_runtime_fusion_bundle(bundle_path)


def _resolve_runtime_outcome(event_family: str, prediction: RuntimeTargetPrediction) -> str:
    if event_family == "defensive_event":
        return "blocked" if prediction.label == "blocked" and not prediction.is_uncertain else "uncertain"
    if event_family != "shot_attempt":
        return "uncertain"
    if prediction.is_uncertain:
        return "uncertain"
    return prediction.label


def _resolve_runtime_confidence(
    *,
    display_label: str,
    family_prediction: RuntimeTargetPrediction,
    outcome_prediction: RuntimeTargetPrediction,
    subtype_prediction: RuntimeTargetPrediction,
    is_uncertain: bool,
) -> float:
    confidence = family_prediction.confidence
    if display_label in {"Dunk", "Layup", "Three Pointer"}:
        confidence = max(confidence, subtype_prediction.confidence)
    elif display_label == "Made Shot":
        confidence = min(max(confidence, subtype_prediction.confidence), max(outcome_prediction.confidence, 0.3))
    elif display_label == "Block":
        confidence = max(confidence, outcome_prediction.confidence)
    if is_uncertain and display_label == "Highlight":
        confidence = min(confidence, 0.46)
    return min(max(confidence, 0.0), 1.0)


def _add_training_feature_categorical(features: dict[str, float], prefix: str, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if not text:
        return
    features[f"{prefix}={_normalize_training_label(text)}"] = 1.0


def _add_ranked_labels(features: dict[str, float], prefix: str, items: Sequence[Any]) -> None:
    for index, item in enumerate(list(items)[:MAX_RUNTIME_TOPK]):
        label = _item_label(item)
        confidence = _item_confidence(item)
        if label is None:
            continue
        features[f"{prefix}:{index + 1}={label}"] = 1.0
        features[f"{prefix}:{index + 1}:confidence"] = confidence


def _item_label(item: Any) -> str | None:
    if item is None:
        return None
    if isinstance(item, str):
        return item.strip().lower() or None
    if isinstance(item, dict):
        candidate = item.get("label") or item.get("canonicalLabel") or item.get("rawLabel")
        return str(candidate).strip().lower() if candidate else None
    return None


def _item_confidence(item: Any) -> float:
    if isinstance(item, dict):
        return _coerce_float(item.get("confidence"), default=0.0)
    return 0.0


def _top_label(items: Sequence[Any]) -> str | None:
    if not items:
        return None
    return _item_label(items[0])


def _normalize_training_label(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exponentials = np.exp(shifted)
    total = np.sum(exponentials)
    if total <= 0:
        return np.zeros_like(values)
    return exponentials / total

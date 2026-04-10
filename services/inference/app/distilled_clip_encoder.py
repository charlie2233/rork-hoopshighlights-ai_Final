from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np


DISTILLED_CLIP_ENCODER_SCHEMA_VERSION = "distilled-clip-encoder-v1"
DISTILLED_CLIP_ENCODER_FEATURE_VERSION = "distilled-clip-features-v1"
DISTILLED_CLIP_ENCODER_MODEL_VERSION = "distilled-clip-encoder-v1"
DISTILLED_CLIP_ENCODER_SOURCE_DATASET = "services/inference/datasets/gold_set.json + silver_set.json + disagreement_queue.jsonl"
DISTILLED_CLIP_ENCODER_BUNDLE_PATH = Path(__file__).resolve().parents[1] / "models" / "distilled_clip_encoder_v1.json"

EVENT_FAMILY_LABELS = ("shot_attempt", "turnover", "defensive_event", "transition", "other")
OUTCOME_LABELS = ("made", "missed", "blocked", "uncertain")
SHOT_SUBTYPE_LABELS = ("dunk", "layup", "jumper", "three", "putback", "null")


@dataclass(frozen=True)
class DistilledClipLabelSpaces:
    event_family: tuple[str, ...] = EVENT_FAMILY_LABELS
    outcome: tuple[str, ...] = OUTCOME_LABELS
    shot_subtype: tuple[str, ...] = SHOT_SUBTYPE_LABELS


@dataclass(frozen=True)
class DistilledTargetPrediction:
    label: str
    confidence: float
    margin: float
    distribution: dict[str, float]
    top_labels: tuple[tuple[str, float], ...]
    is_uncertain: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DistilledClipEncoderPrediction:
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
    raw_head_predictions: dict[str, DistilledTargetPrediction]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["raw_head_predictions"] = {
            key: value.as_dict() for key, value in self.raw_head_predictions.items()
        }
        return payload


@dataclass(frozen=True)
class DistilledEncoderHead:
    labels: tuple[str, ...]
    coefficients: tuple[tuple[float, ...], ...]
    intercept: tuple[float, ...]
    temperature: float = 1.0
    uncertainty_threshold: float = 0.55
    margin_threshold: float = 0.12
    top_k: int = 3

    def predict(self, feature_vector: np.ndarray) -> DistilledTargetPrediction:
        coefficients = np.asarray(self.coefficients, dtype=np.float64)
        intercept = np.asarray(self.intercept, dtype=np.float64)
        if coefficients.ndim != 2:
            raise ValueError("Head coefficients must be a matrix.")
        logits = np.matmul(feature_vector, coefficients) + intercept
        probabilities = _softmax(logits / max(float(self.temperature), 1e-3))
        ranked_indices = list(np.argsort(probabilities)[::-1])
        top_index = int(ranked_indices[0])
        top_probability = float(probabilities[top_index])
        second_probability = float(probabilities[ranked_indices[1]]) if len(ranked_indices) > 1 else 0.0
        margin = max(top_probability - second_probability, 0.0)
        is_uncertain = top_probability < self.uncertainty_threshold or margin < self.margin_threshold
        distribution = {
            str(label): round(float(probabilities[index]), 4)
            for index, label in enumerate(self.labels)
        }
        top_labels = tuple(
            (str(self.labels[index]), round(float(probabilities[index]), 4))
            for index in ranked_indices[: self.top_k]
        )
        return DistilledTargetPrediction(
            label=str(self.labels[top_index]),
            confidence=round(top_probability, 4),
            margin=round(margin, 4),
            distribution=distribution,
            top_labels=top_labels,
            is_uncertain=is_uncertain,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "labels": list(self.labels),
            "coefficients": [list(row) for row in self.coefficients],
            "intercept": list(self.intercept),
            "temperature": self.temperature,
            "uncertaintyThreshold": self.uncertainty_threshold,
            "marginThreshold": self.margin_threshold,
            "topK": self.top_k,
        }


@dataclass(frozen=True)
class DistilledClipEncoderBundle:
    schema_version: str
    feature_version: str
    model_version: str
    trained_at: str
    source_dataset: str
    notes: tuple[str, ...]
    label_spaces: DistilledClipLabelSpaces
    feature_names: tuple[str, ...]
    feature_means: tuple[float, ...]
    feature_scales: tuple[float, ...]
    heads: dict[str, DistilledEncoderHead]

    @property
    def feature_index(self) -> dict[str, int]:
        return {name: index for index, name in enumerate(self.feature_names)}

    def vectorize(self, feature_dict: dict[str, float]) -> np.ndarray:
        vector = np.zeros(len(self.feature_names), dtype=np.float64)
        index = self.feature_index
        for feature_name, value in feature_dict.items():
            location = index.get(feature_name)
            if location is None:
                continue
            vector[location] = float(value)
        means = np.asarray(self.feature_means, dtype=np.float64)
        scales = np.asarray(self.feature_scales, dtype=np.float64)
        return (vector - means) / scales

    def predict_from_snapshot(self, snapshot: dict[str, Any]) -> DistilledClipEncoderPrediction:
        feature_dict = build_distilled_clip_feature_dict(snapshot)
        feature_vector = self.vectorize(feature_dict)
        family_prediction = self.heads["eventFamily"].predict(feature_vector)
        outcome_prediction = self.heads["outcome"].predict(feature_vector)
        subtype_prediction = self.heads["shotSubtype"].predict(feature_vector)

        event_family = family_prediction.label
        if family_prediction.is_uncertain:
            event_family = "other"

        outcome = _resolve_outcome(event_family, outcome_prediction)
        shot_subtype: str | None = None
        if event_family == "shot_attempt" and not subtype_prediction.is_uncertain and subtype_prediction.label != "null":
            shot_subtype = subtype_prediction.label

        canonical_label, display_label = derive_display_label(
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
        confidence_after_mapping = _mapped_confidence(
            display_label=display_label,
            family_prediction=family_prediction,
            outcome_prediction=outcome_prediction,
            subtype_prediction=subtype_prediction,
            is_uncertain=is_uncertain,
        )
        return DistilledClipEncoderPrediction(
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
                max(family_prediction.confidence - (0.08 if family_prediction.is_uncertain else 0.0), 0.0),
                4,
            ),
            shot_subtype_confidence_before_mapping=subtype_prediction.confidence if shot_subtype is not None else None,
            shot_subtype_confidence_after_mapping=(
                round(max(subtype_prediction.confidence - (0.06 if subtype_prediction.is_uncertain else 0.0), 0.0), 4)
                if shot_subtype is not None
                else None
            ),
            outcome_confidence_before_mapping=outcome_prediction.confidence,
            outcome_confidence_after_mapping=round(
                max(outcome_prediction.confidence - (0.06 if outcome_prediction.is_uncertain else 0.0), 0.0),
                4,
            ),
            is_uncertain=is_uncertain,
            raw_head_predictions={
                "eventFamily": family_prediction,
                "outcome": outcome_prediction,
                "shotSubtype": subtype_prediction,
            },
            metadata={
                "distilledClipEncoderSchemaVersion": self.schema_version,
                "distilledClipEncoderFeatureVersion": self.feature_version,
                "distilledClipEncoderSourceDataset": self.source_dataset,
                "distilledClipEncoderSnapshot": summarize_distilled_snapshot(snapshot),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "featureVersion": self.feature_version,
            "modelVersion": self.model_version,
            "trainedAt": self.trained_at,
            "sourceDataset": self.source_dataset,
            "notes": list(self.notes),
            "labelSpaces": {
                "eventFamily": list(self.label_spaces.event_family),
                "outcome": list(self.label_spaces.outcome),
                "shotSubtype": list(self.label_spaces.shot_subtype),
            },
            "featureNames": list(self.feature_names),
            "featureMeans": list(self.feature_means),
            "featureScales": list(self.feature_scales),
            "heads": {name: head.as_dict() for name, head in self.heads.items()},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DistilledClipEncoderBundle":
        label_spaces = payload.get("labelSpaces") or {}
        heads = {
            name: DistilledEncoderHead(
                labels=tuple(str(label) for label in head_payload.get("labels", [])),
                coefficients=tuple(
                    tuple(float(value) for value in row)
                    for row in head_payload.get("coefficients", [])
                ),
                intercept=tuple(float(value) for value in head_payload.get("intercept", [])),
                temperature=float(head_payload.get("temperature", 1.0)),
                uncertainty_threshold=float(head_payload.get("uncertaintyThreshold", 0.55)),
                margin_threshold=float(head_payload.get("marginThreshold", 0.12)),
                top_k=int(head_payload.get("topK", 3)),
            )
            for name, head_payload in (payload.get("heads") or {}).items()
        }
        return cls(
            schema_version=str(payload.get("schemaVersion") or DISTILLED_CLIP_ENCODER_SCHEMA_VERSION),
            feature_version=str(payload.get("featureVersion") or DISTILLED_CLIP_ENCODER_FEATURE_VERSION),
            model_version=str(payload.get("modelVersion") or DISTILLED_CLIP_ENCODER_MODEL_VERSION),
            trained_at=str(payload.get("trainedAt") or ""),
            source_dataset=str(payload.get("sourceDataset") or DISTILLED_CLIP_ENCODER_SOURCE_DATASET),
            notes=tuple(str(item) for item in payload.get("notes", [])),
            label_spaces=DistilledClipLabelSpaces(
                event_family=tuple(str(item) for item in label_spaces.get("eventFamily", EVENT_FAMILY_LABELS)),
                outcome=tuple(str(item) for item in label_spaces.get("outcome", OUTCOME_LABELS)),
                shot_subtype=tuple(str(item) for item in label_spaces.get("shotSubtype", SHOT_SUBTYPE_LABELS)),
            ),
            feature_names=tuple(str(item) for item in payload.get("featureNames", [])),
            feature_means=tuple(float(item) for item in payload.get("featureMeans", [])),
            feature_scales=tuple(float(item) for item in payload.get("featureScales", [])),
            heads=heads,
        )

    @classmethod
    def load(cls, path: Path) -> "DistilledClipEncoderBundle":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def build_distilled_clip_feature_dict(snapshot: dict[str, Any]) -> dict[str, float]:
    features: dict[str, float] = {}

    def put_numeric(key: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, bool):
            features[key] = 1.0 if value else 0.0
            return
        try:
            features[key] = float(value)
        except (TypeError, ValueError):
            return

    def put_categorical(prefix: str, value: Any) -> None:
        if value is None:
            return
        text = _normalize_label(value)
        if not text:
            return
        features[f"{prefix}={text}"] = 1.0

    structured = snapshot.get("structuredSignals") or snapshot.get("structured_signals") or {}
    raw_runtime = snapshot.get("rawRuntimeOutputs") or {}

    for key in (
        "ballVisible",
        "hoopVisible",
        "ballNearRim",
        "ballThroughHoopLikelihood",
        "possessionChangeLikelihood",
        "transitionLikelihood",
        "transitionSpeedScore",
        "ballCarrierSpeed",
        "defenderProximityAtShot",
        "shotReleaseCandidate",
        "samePlayContinuityScore",
        "clipDurationSeconds",
        "eventCenterSeconds",
        "preRollSeconds",
        "postRollSeconds",
        "sourceEventCount",
        "wasMerged",
        "priorityScore",
        "humanVerified",
    ):
        put_numeric(key, snapshot.get(key))
        put_numeric(key, structured.get(key))

    for key in ("sourceKind", "sourceDomain", "sourceSet", "sourceRefKind"):
        put_categorical(key, snapshot.get(key))

    for key in ("runtimeLabel", "runtimeEventFamily", "runtimeOutcome", "runtimeShotSubtype", "runtimeModelVersion"):
        source_key = key.replace("runtime", "")
        put_categorical(key, snapshot.get(source_key))
        put_categorical(key, raw_runtime.get(source_key[0].lower() + source_key[1:]))

    put_categorical("runtimeLabel", raw_runtime.get("label"))
    put_categorical("runtimeEventFamily", raw_runtime.get("eventFamily"))
    put_categorical("runtimeOutcome", raw_runtime.get("outcome"))
    put_categorical("runtimeShotSubtype", raw_runtime.get("shotSubtype"))
    put_categorical("runtimeModelVersion", raw_runtime.get("modelVersion"))

    top_labels = raw_runtime.get("topKLabels") or raw_runtime.get("rawTopLabels") or []
    for index, item in enumerate(top_labels[:8]):
        if isinstance(item, dict):
            put_categorical(f"runtimeTopK[{index}]", item.get("label") or item.get("rawLabel") or item.get("canonicalLabel"))
        else:
            put_categorical(f"runtimeTopK[{index}]", item)

    comparison = snapshot.get("comparisonRawTopLabels") or []
    for index, item in enumerate(comparison[:4]):
        if isinstance(item, dict):
            put_categorical(f"comparisonTopK[{index}]", item.get("label") or item.get("rawLabel") or item.get("canonicalLabel"))
        else:
            put_categorical(f"comparisonTopK[{index}]", item)

    return features


def summarize_distilled_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    raw_runtime = snapshot.get("rawRuntimeOutputs") or {}
    return {
        "sourceKind": snapshot.get("sourceKind"),
        "sourceDomain": snapshot.get("sourceDomain"),
        "sourceSet": snapshot.get("sourceSet"),
        "clipDurationSeconds": snapshot.get("clipDurationSeconds"),
        "eventCenterSeconds": snapshot.get("eventCenterSeconds"),
        "runtimeLabel": raw_runtime.get("label"),
        "runtimeEventFamily": raw_runtime.get("eventFamily"),
        "runtimeOutcome": raw_runtime.get("outcome"),
        "runtimeShotSubtype": raw_runtime.get("shotSubtype"),
    }


def derive_display_label(event_family: str, outcome: str, shot_subtype: str | None) -> tuple[str, str]:
    if event_family == "transition":
        return "transition", "Fast Break"
    if event_family == "turnover":
        return "turnover", "Steal"
    if event_family == "defensive_event":
        if outcome == "blocked":
            return "block", "Block"
        return "defensive_event", "Highlight"
    if event_family == "other":
        return "other", "Highlight"
    if outcome == "missed":
        return "miss", "Highlight"
    if shot_subtype == "dunk":
        return "dunk", "Dunk"
    if shot_subtype == "layup":
        return "layup", "Layup"
    if shot_subtype == "three":
        return "three", "Three Pointer"
    if shot_subtype == "putback":
        return "putback", "Made Shot"
    return "made", "Made Shot"


def _resolve_outcome(event_family: str, prediction: DistilledTargetPrediction) -> str:
    if event_family == "transition":
        return "uncertain"
    if event_family == "turnover":
        return "uncertain"
    if event_family == "defensive_event" and prediction.label not in {"blocked", "uncertain"}:
        return "uncertain"
    if prediction.is_uncertain:
        return "uncertain"
    if prediction.label in OUTCOME_LABELS:
        return prediction.label
    return "uncertain"


def _mapped_confidence(
    *,
    display_label: str,
    family_prediction: DistilledTargetPrediction,
    outcome_prediction: DistilledTargetPrediction,
    subtype_prediction: DistilledTargetPrediction,
    is_uncertain: bool,
) -> float:
    confidence = family_prediction.confidence
    confidence = min(confidence, outcome_prediction.confidence)
    if display_label not in {"Highlight", "Fast Break", "Steal", "Block"} and subtype_prediction.label != "null":
        confidence = min(confidence, subtype_prediction.confidence)
    if is_uncertain:
        confidence = max(confidence - 0.08, 0.0)
    return min(max(confidence, 0.0), 1.0)


def _softmax(logits: np.ndarray) -> np.ndarray:
    logits = np.asarray(logits, dtype=np.float64)
    if logits.size == 0:
        return logits
    shifted = logits - np.max(logits)
    exp_logits = np.exp(shifted)
    denominator = float(np.sum(exp_logits))
    if denominator <= 0.0:
        return np.full_like(exp_logits, 1.0 / float(exp_logits.size))
    return exp_logits / denominator


def _normalize_label(value: Any) -> str:
    if value is None:
        return "null"
    return str(value).strip().lower().replace(" ", "_")


@lru_cache(maxsize=1)
def get_distilled_clip_encoder_bundle(path: str | None = None) -> DistilledClipEncoderBundle | None:
    bundle_path = Path(path) if path else DISTILLED_CLIP_ENCODER_BUNDLE_PATH
    if not bundle_path.exists():
        return None
    return DistilledClipEncoderBundle.load(bundle_path)

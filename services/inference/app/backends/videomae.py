from __future__ import annotations

from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..features import sample_video_frames
from ..interfaces import VideoFeatures
from ..labels import derive_basketball_taxonomy, normalize_action_label, sum_label_scores
from ..models import ActionPrediction, CandidateWindow, LabelScore, RawLabelScore


@dataclass
class VideoMAEActionRecognizer:
    model_name: str
    device: str = "auto"
    top_k: int = 5
    frame_count: int = 16
    lora_bundle_path: str | None = None

    def resolved_model_version(self) -> str:
        if self.lora_bundle_path:
            return f"videomae-rslora:{self.model_name}"
        return f"videomae:{self.model_name}"

    def recognize(self, candidate: CandidateWindow, features: VideoFeatures) -> ActionPrediction:
        if self.lora_bundle_path:
            return self._recognize_lora(candidate, features)
        model_version = self.resolved_model_version()
        try:
            import torch

            processor, model, runtime_device = _load_backend(self.model_name, self.device)
            frames = sample_video_frames(
                features.source_path,
                frame_count=self.frame_count,
                start_seconds=candidate.startTime,
                end_seconds=candidate.endTime,
            )
            if not frames:
                raise RuntimeError("no_frames_sampled")

            inputs = processor(images=frames, return_tensors="pt")
            inputs = _move_inputs(inputs, runtime_device)
            model = model.to(runtime_device)
            model.eval()

            with torch.inference_mode():
                outputs = model(**inputs)
                probabilities = torch.softmax(outputs.logits[0], dim=-1)

            raw_ranked, ranked = _build_ranked_labels(probabilities, model.config.id2label, model_version, self.top_k)
            if not ranked:
                raise RuntimeError("empty_predictions")

            best = ranked[0]
            taxonomy = derive_basketball_taxonomy(best.label, best.confidence, ranked)
            return ActionPrediction(
                label=taxonomy.display_label,
                canonicalLabel=taxonomy.canonical_label,
                confidence=taxonomy.confidence_after_mapping,
                modelVersion=model_version,
                promptSetVersion=None,
                detectionMethod="videomae",
                topLabels=ranked,
                rawTopLabels=raw_ranked,
                eventFamily=taxonomy.event_family,
                eventSubtype=taxonomy.event_subtype,
                shotSubtype=taxonomy.shot_subtype,
                outcome=taxonomy.outcome,
                confidenceBeforeMapping=taxonomy.confidence_before_mapping,
                confidenceAfterMapping=taxonomy.confidence_after_mapping,
                eventFamilyConfidenceBeforeMapping=taxonomy.event_family_confidence_before_mapping,
                eventFamilyConfidenceAfterMapping=taxonomy.event_family_confidence_after_mapping,
                shotSubtypeConfidenceBeforeMapping=taxonomy.shot_subtype_confidence_before_mapping,
                shotSubtypeConfidenceAfterMapping=taxonomy.shot_subtype_confidence_after_mapping,
                outcomeConfidenceBeforeMapping=taxonomy.outcome_confidence_before_mapping,
                outcomeConfidenceAfterMapping=taxonomy.outcome_confidence_after_mapping,
                isUncertain=taxonomy.is_uncertain,
                metadata={
                    "candidate_id": candidate.candidateId,
                    "frame_count": len(frames),
                    "raw_prediction_labels": [item.rawLabel for item in raw_ranked if item.rawLabel],
                    "source_model": self.model_name,
                    "calibration_version": taxonomy.calibration_version,
                    "calibrated_confidence": taxonomy.confidence_after_mapping,
                },
            )
        except Exception as exc:
            return self._fallback(candidate, model_version, f"inference_failed:{exc.__class__.__name__}")

    def _recognize_lora(self, candidate: CandidateWindow, features: VideoFeatures) -> ActionPrediction:
        model_version = self.resolved_model_version()
        try:
            runtime_bundle, runtime_device = _load_lora_runtime_backend(self.lora_bundle_path or "", self.device)
            prediction = _predict_lora_window(
                runtime_bundle=runtime_bundle,
                source_path=features.source_path,
                clip_id=candidate.candidateId,
                source_kind="runtime",
                source_domain="live_runtime",
                source_set="runtime_inference",
                start_seconds=candidate.startTime,
                end_seconds=candidate.endTime,
            )
            raw_top_labels = _build_lora_raw_top_labels(prediction, model_version)
            top_labels = _build_lora_ranked_labels(prediction, model_version)
            return ActionPrediction(
                label=str(prediction["displayLabel"]),
                canonicalLabel=str(prediction["canonicalLabel"]),
                confidence=float(prediction["confidenceAfterMapping"]),
                modelVersion=str(prediction.get("modelVersion") or runtime_bundle.runtime_metadata.get("modelVersion") or model_version),
                promptSetVersion=None,
                detectionMethod="videomae_lora",
                topLabels=top_labels,
                rawTopLabels=raw_top_labels,
                eventFamily=str(prediction["eventFamily"]),
                eventSubtype=_event_subtype_for_lora_prediction(prediction),
                shotSubtype=prediction.get("shotSubtype"),
                outcome=str(prediction["outcome"]),
                confidenceBeforeMapping=float(prediction["confidenceBeforeMapping"]),
                confidenceAfterMapping=float(prediction["confidenceAfterMapping"]),
                eventFamilyConfidenceBeforeMapping=_head_confidence(prediction, "rawEventFamily"),
                eventFamilyConfidenceAfterMapping=_head_confidence(prediction, "rawEventFamily"),
                shotSubtypeConfidenceBeforeMapping=_head_confidence(prediction, "rawShotSubtype", present=prediction.get("shotSubtype") is not None),
                shotSubtypeConfidenceAfterMapping=_head_confidence(prediction, "rawShotSubtype", present=prediction.get("shotSubtype") is not None),
                outcomeConfidenceBeforeMapping=_head_confidence(prediction, "rawOutcome"),
                outcomeConfidenceAfterMapping=_head_confidence(prediction, "rawOutcome"),
                isUncertain=bool(prediction["isUncertain"]),
                metadata={
                    "candidate_id": candidate.candidateId,
                    "frame_count": int(runtime_bundle.runtime_metadata.get("frameCount") or self.frame_count),
                    "source_model": self.model_name,
                    "lora_bundle_path": self.lora_bundle_path,
                    "lora_runtime_device": str(runtime_device),
                    "lora_temperature": prediction.get("temperature") or runtime_bundle.temperature,
                    "lora_head_top_labels": prediction.get("rawTopLabels") or {},
                },
            )
        except Exception as exc:
            return self._fallback(candidate, model_version, f"lora_inference_failed:{exc.__class__.__name__}")

    def _fallback(self, candidate: CandidateWindow, model_version: str, failure_reason: str) -> ActionPrediction:
        if candidate.score >= 0.8:
            canonical_label = "dunk"
            confidence = 0.52
        elif candidate.score >= 0.66:
            canonical_label = "layup"
            confidence = 0.44
        elif candidate.score >= 0.52:
            canonical_label = "fast break"
            confidence = 0.39
        else:
            canonical_label = "uncertain"
            confidence = 0.24
        taxonomy = derive_basketball_taxonomy(canonical_label, confidence)
        top_labels = [
            LabelScore(
                label=taxonomy.canonical_label,
                confidence=confidence,
                rawLabel=canonical_label,
                modelVersion=model_version,
            )
        ]
        raw_top_labels = [
            RawLabelScore(
                rawLabel=canonical_label,
                canonicalLabel=taxonomy.canonical_label,
                confidence=confidence,
                modelVersion=model_version,
            )
        ]
        return ActionPrediction(
            label=taxonomy.display_label,
            canonicalLabel=taxonomy.canonical_label,
            confidence=taxonomy.confidence_after_mapping,
            modelVersion=model_version,
            promptSetVersion=None,
            detectionMethod="heuristic_fallback",
            failureReason=failure_reason,
            topLabels=top_labels,
            rawTopLabels=raw_top_labels,
            eventFamily=taxonomy.event_family,
            eventSubtype=taxonomy.event_subtype,
            shotSubtype=taxonomy.shot_subtype,
            outcome=taxonomy.outcome,
            confidenceBeforeMapping=taxonomy.confidence_before_mapping,
            confidenceAfterMapping=taxonomy.confidence_after_mapping,
            eventFamilyConfidenceBeforeMapping=taxonomy.event_family_confidence_before_mapping,
            eventFamilyConfidenceAfterMapping=taxonomy.event_family_confidence_after_mapping,
            shotSubtypeConfidenceBeforeMapping=taxonomy.shot_subtype_confidence_before_mapping,
            shotSubtypeConfidenceAfterMapping=taxonomy.shot_subtype_confidence_after_mapping,
            outcomeConfidenceBeforeMapping=taxonomy.outcome_confidence_before_mapping,
            outcomeConfidenceAfterMapping=taxonomy.outcome_confidence_after_mapping,
            isUncertain=taxonomy.is_uncertain,
            metadata={
                "candidate_id": candidate.candidateId,
                "calibration_version": taxonomy.calibration_version,
                "calibrated_confidence": taxonomy.confidence_after_mapping,
            },
        )


@lru_cache(maxsize=4)
def _load_backend(model_name: str, device: str) -> tuple[object, object, Any]:
    from transformers import VideoMAEForVideoClassification, VideoMAEImageProcessor  # type: ignore

    processor = VideoMAEImageProcessor.from_pretrained(model_name)
    model = VideoMAEForVideoClassification.from_pretrained(model_name)
    runtime_device = _resolve_device(device)
    return processor, model, runtime_device


def _resolve_device(device: str):
    import torch

    if device == "cpu":
        return torch.device("cpu")
    if device == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    if device == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _move_inputs(inputs: dict[str, Any], device) -> dict[str, Any]:
    return {key: value.to(device) for key, value in inputs.items()}


@lru_cache(maxsize=2)
def _load_lora_runtime_backend(bundle_path: str, device: str) -> tuple[Any, Any]:
    runtime_device = _resolve_device(device)
    from services.inference.training.videomae_lora import load_runtime_bundle

    bundle = load_runtime_bundle(Path(bundle_path), device=str(runtime_device))
    return bundle, runtime_device


def _predict_lora_window(
    *,
    runtime_bundle: Any,
    source_path: Path,
    clip_id: str,
    source_kind: str,
    source_domain: str,
    source_set: str,
    start_seconds: float | None,
    end_seconds: float | None,
) -> dict[str, Any]:
    from services.inference.training.videomae_lora import predict_source_path

    return predict_source_path(
        runtime_bundle=runtime_bundle,
        source_path=source_path,
        clip_id=clip_id,
        source_kind=source_kind,
        source_domain=source_domain,
        source_set=source_set,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )


def _build_ranked_labels(
    probabilities,
    id2label: dict[int, str],
    model_version: str,
    top_k: int,
) -> tuple[list[RawLabelScore], list[LabelScore]]:
    import torch

    top_k = min(max(top_k, 1), int(probabilities.shape[-1]))
    values, indices = torch.topk(probabilities, k=top_k)

    raw_ranked: list[RawLabelScore] = []
    ranked: list[LabelScore] = []
    for raw_score, index in zip(values.tolist(), indices.tolist(), strict=False):
        raw_label = str(id2label.get(int(index), f"class-{index}"))
        canonical_label = normalize_action_label(raw_label)
        raw_ranked.append(
            RawLabelScore(
                rawLabel=raw_label,
                canonicalLabel=canonical_label,
                confidence=min(max(float(raw_score), 0.0), 1.0),
                modelVersion=model_version,
            )
        )
        ranked.append(
            LabelScore(
                label=canonical_label,
                confidence=min(max(float(raw_score), 0.0), 1.0),
                rawLabel=raw_label,
                modelVersion=model_version,
            )
        )

    return raw_ranked, sum_label_scores(ranked)


def _build_lora_ranked_labels(prediction: dict[str, Any], model_version: str) -> list[LabelScore]:
    canonical_label = str(prediction.get("canonicalLabel") or "uncertain")
    confidence = min(max(float(prediction.get("confidenceAfterMapping") or prediction.get("confidence") or 0.0), 0.0), 1.0)
    raw_family = ((prediction.get("rawEventFamily") or {}).get("topLabels") or [])
    extra: list[LabelScore] = [
        LabelScore(
            label=canonical_label,
            confidence=confidence,
            rawLabel=canonical_label,
            modelVersion=model_version,
        )
    ]
    for item in raw_family[:2]:
        label = str(item.get("label") or "other")
        if label == canonical_label:
            continue
        extra.append(
            LabelScore(
                label=label,
                confidence=min(max(float(item.get("confidence") or 0.0), 0.0), 1.0),
                rawLabel=f"eventFamily:{label}",
                modelVersion=model_version,
            )
        )
    return extra


def _build_lora_raw_top_labels(prediction: dict[str, Any], model_version: str) -> list[RawLabelScore]:
    rows: list[RawLabelScore] = []
    for head_key, prefix in (
        ("rawEventFamily", "eventFamily"),
        ("rawOutcome", "outcome"),
        ("rawShotSubtype", "shotSubtype"),
    ):
        top_labels = ((prediction.get(head_key) or {}).get("topLabels") or [])[:3]
        for item in top_labels:
            label = str(item.get("label") or "unknown")
            rows.append(
                RawLabelScore(
                    rawLabel=f"{prefix}:{label}",
                    canonicalLabel=label,
                    confidence=min(max(float(item.get("confidence") or 0.0), 0.0), 1.0),
                    modelVersion=model_version,
                )
            )
    return rows


def _head_confidence(prediction: dict[str, Any], head_key: str, *, present: bool = True) -> float | None:
    if not present:
        return None
    try:
        return float((prediction.get(head_key) or {}).get("confidence"))
    except (TypeError, ValueError):
        return None


def _event_subtype_for_lora_prediction(prediction: dict[str, Any]) -> str | None:
    event_family = str(prediction.get("eventFamily") or "other")
    shot_subtype = prediction.get("shotSubtype")
    outcome = str(prediction.get("outcome") or "uncertain")
    if event_family == "shot_attempt" and shot_subtype:
        return str(shot_subtype)
    if event_family == "defensive_event":
        return "block" if outcome == "blocked" else "defensive_event"
    if event_family == "turnover":
        return "steal"
    if event_family == "transition":
        return "fast_break"
    return None

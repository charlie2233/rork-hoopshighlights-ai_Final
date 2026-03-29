from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ..features import sample_video_frames
from ..interfaces import VideoFeatures
from ..labels import (
    build_xclip_prompts,
    canonical_label_for_prompt,
    derive_basketball_taxonomy,
    sum_label_scores,
    xclip_prompt_set_hash,
    xclip_prompt_set_version,
)
from ..models import ActionPrediction, CandidateWindow, LabelScore, RawLabelScore


@dataclass
class XClipActionRecognizer:
    model_name: str
    device: str = "auto"
    top_k: int = 5
    frame_count: int = 8

    def recognize(self, candidate: CandidateWindow, features: VideoFeatures) -> ActionPrediction:
        import torch

        model_version = f"xclip:{self.model_name}"
        try:
            processor, model, runtime_device = _load_backend(self.model_name, self.device)
            frames = sample_video_frames(features.source_path, frame_count=self.frame_count)
            if not frames:
                raise RuntimeError("no_frames_sampled")

            prompts = build_xclip_prompts()
            prompt_set_version = xclip_prompt_set_version()
            inputs = processor(text=prompts, images=frames, return_tensors="pt", padding=True)
            inputs = _move_inputs(inputs, runtime_device)
            model = model.to(runtime_device)
            model.eval()

            with torch.inference_mode():
                outputs = model(**inputs)
                probabilities = torch.softmax(outputs.logits_per_video[0], dim=-1)

            raw_ranked, ranked = _build_ranked_labels(probabilities, prompts, model_version, self.top_k)
            if not ranked:
                raise RuntimeError("empty_predictions")

            best = ranked[0]
            taxonomy = derive_basketball_taxonomy(
                best.label,
                best.confidence,
                ranked,
                raw_top_labels=raw_ranked,
                prompt_set_version=prompt_set_version,
            )
            return ActionPrediction(
                label=taxonomy.display_label,
                canonicalLabel=taxonomy.canonical_label,
                confidence=taxonomy.confidence_after_mapping,
                modelVersion=model_version,
                promptSetVersion=prompt_set_version,
                detectionMethod="xclip",
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
                    "raw_prediction_prompts": [item.rawLabel for item in raw_ranked if item.rawLabel],
                    "source_model": self.model_name,
                    "prompt_set_version": prompt_set_version,
                    "prompt_set_hash": xclip_prompt_set_hash(),
                },
            )
        except Exception as exc:
            return self._fallback(candidate, model_version, f"inference_failed:{exc.__class__.__name__}")

    def _fallback(self, candidate: CandidateWindow, model_version: str, failure_reason: str) -> ActionPrediction:
        if candidate.score >= 0.72:
            canonical_label = "three"
            confidence = 0.37
        elif candidate.score >= 0.48:
            canonical_label = "fast break"
            confidence = 0.33
        else:
            canonical_label = "uncertain"
            confidence = 0.22
        prompt_set_version = xclip_prompt_set_version()
        taxonomy = derive_basketball_taxonomy(
            canonical_label,
            confidence,
            prompt_set_version=prompt_set_version,
        )
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
            promptSetVersion=prompt_set_version,
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
                "prompt_set_version": prompt_set_version,
                "prompt_set_hash": xclip_prompt_set_hash(),
            },
        )


@lru_cache(maxsize=4)
def _load_backend(model_name: str, device: str) -> tuple[object, object, torch.device]:
    import torch
    from transformers import AutoModel, AutoProcessor  # type: ignore

    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
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


def _build_ranked_labels(
    probabilities,
    prompts: list[str],
    model_version: str,
    top_k: int,
) -> tuple[list[RawLabelScore], list[LabelScore]]:
    import torch

    top_k = min(max(top_k, 1), int(probabilities.shape[-1]))
    values, indices = torch.topk(probabilities, k=top_k)

    raw_ranked: list[RawLabelScore] = []
    ranked: list[LabelScore] = []
    for raw_score, index in zip(values.tolist(), indices.tolist(), strict=False):
        prompt = str(prompts[int(index)])
        canonical_label = canonical_label_for_prompt(prompt)
        raw_ranked.append(
            RawLabelScore(
                rawLabel=prompt,
                canonicalLabel=canonical_label,
                confidence=min(max(float(raw_score), 0.0), 1.0),
                modelVersion=model_version,
            )
        )
        ranked.append(
            LabelScore(
                label=canonical_label,
                confidence=min(max(float(raw_score), 0.0), 1.0),
                rawLabel=prompt,
                modelVersion=model_version,
            )
        )

    return raw_ranked, sum_label_scores(ranked)

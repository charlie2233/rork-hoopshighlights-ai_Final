from __future__ import annotations

from functools import lru_cache
from dataclasses import dataclass
from typing import Any

from ..features import sample_video_frames
from ..interfaces import VideoFeatures
from ..labels import aggregate_label_scores, canonical_to_display_label, normalize_action_label
from ..models import ActionPrediction, CandidateWindow, LabelScore


@dataclass
class VideoMAEActionRecognizer:
    model_name: str
    device: str = "auto"
    top_k: int = 5
    frame_count: int = 16

    def recognize(self, candidate: CandidateWindow, features: VideoFeatures) -> ActionPrediction:
        model_version = f"videomae:{self.model_name}"
        try:
            import torch

            processor, model, runtime_device = _load_backend(self.model_name, self.device)
            frames = sample_video_frames(features.source_path, frame_count=self.frame_count)
            if not frames:
                raise RuntimeError("no_frames_sampled")

            inputs = processor(videos=frames, return_tensors="pt")
            inputs = _move_inputs(inputs, runtime_device)
            model = model.to(runtime_device)
            model.eval()

            with torch.inference_mode():
                outputs = model(**inputs)
                probabilities = torch.softmax(outputs.logits[0], dim=-1)

            ranked = _build_ranked_labels(probabilities, model.config.id2label, model_version, self.top_k)
            if not ranked:
                raise RuntimeError("empty_predictions")

            best = ranked[0]
            return ActionPrediction(
                label=canonical_to_display_label(best.label),
                canonicalLabel=best.label,
                confidence=min(max(best.confidence, 0.0), 1.0),
                modelVersion=model_version,
                detectionMethod="videomae",
                topLabels=ranked,
                metadata={
                    "candidate_id": candidate.candidateId,
                    "frame_count": len(frames),
                    "raw_prediction_labels": [item.raw_label for item in ranked if item.raw_label],
                    "source_model": self.model_name,
                },
            )
        except Exception as exc:
            return self._fallback(candidate, model_version, f"inference_failed:{exc.__class__.__name__}")

    def _fallback(self, candidate: CandidateWindow, model_version: str, failure_reason: str) -> ActionPrediction:
        canonical_label = "dunk" if candidate.score >= 0.65 else "jumper"
        confidence = 0.48 if canonical_label == "dunk" else 0.35
        top_labels = [
            LabelScore(
                label=canonical_label,
                confidence=confidence,
                rawLabel=canonical_label,
                modelVersion=model_version,
            )
        ]
        return ActionPrediction(
            label=canonical_to_display_label(canonical_label),
            canonicalLabel=canonical_label,
            confidence=confidence,
            modelVersion=model_version,
            detectionMethod="heuristic_fallback",
            failureReason=failure_reason,
            topLabels=top_labels,
            metadata={"candidate_id": candidate.candidateId},
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


def _build_ranked_labels(
    probabilities,
    id2label: dict[int, str],
    model_version: str,
    top_k: int,
) -> list[LabelScore]:
    import torch

    top_k = min(max(top_k, 1), int(probabilities.shape[-1]))
    values, indices = torch.topk(probabilities, k=top_k)

    ranked: list[LabelScore] = []
    for raw_score, index in zip(values.tolist(), indices.tolist(), strict=False):
        raw_label = str(id2label.get(int(index), f"class-{index}"))
        canonical_label = normalize_action_label(raw_label)
        ranked.append(
            LabelScore(
                label=canonical_label,
                confidence=min(max(float(raw_score), 0.0), 1.0),
                rawLabel=raw_label,
                modelVersion=model_version,
            )
        )

    return aggregate_label_scores(ranked)

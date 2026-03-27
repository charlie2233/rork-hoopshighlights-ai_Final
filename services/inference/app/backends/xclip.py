from __future__ import annotations

from dataclasses import dataclass

from ..interfaces import VideoFeatures
from ..models import ActionPrediction, CandidateWindow


@dataclass(slots=True)
class XClipActionRecognizer:
    model_name: str
    device: str = "cpu"
    top_k: int = 5

    def recognize(self, candidate: CandidateWindow, features: VideoFeatures) -> ActionPrediction:
        model_version = f"xclip:{self.model_name}"
        try:
            from transformers import pipeline as hf_pipeline  # type: ignore
        except Exception as exc:
            return self._fallback(candidate, model_version, f"transformers_unavailable:{exc.__class__.__name__}")

        try:
            predictor = hf_pipeline(
                task="zero-shot-video-classification",
                model=self.model_name,
                device=-1 if self.device == "cpu" else 0,
                top_k=self.top_k,
            )
            labels = ["dunk", "layup", "three pointer", "block", "steal", "fast break"]
            predictions = predictor(str(features.source_path), candidate_labels=labels)
            best = predictions[0] if isinstance(predictions, list) and predictions else None
            if best is None:
                raise RuntimeError("empty_predictions")
            label = str(best.get("label") or "Highlight")
            confidence = float(best.get("score") or 0.0)
            return ActionPrediction(
                label=label,
                confidence=min(max(confidence, 0.0), 1.0),
                modelVersion=model_version,
                detectionMethod="xclip",
                metadata={"candidate_id": candidate.candidateId, "prediction_count": len(predictions)},
            )
        except Exception as exc:
            return self._fallback(candidate, model_version, f"inference_failed:{exc.__class__.__name__}")

    def _fallback(self, candidate: CandidateWindow, model_version: str, failure_reason: str) -> ActionPrediction:
        label = "Fast Break" if candidate.score < 0.5 else "Highlight"
        confidence = 0.28 if label == "Fast Break" else 0.31
        return ActionPrediction(
            label=label,
            confidence=confidence,
            modelVersion=model_version,
            detectionMethod="heuristic_fallback",
            failureReason=failure_reason,
            metadata={"candidate_id": candidate.candidateId},
        )

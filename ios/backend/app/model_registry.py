from __future__ import annotations

from dataclasses import dataclass
import hashlib
from time import perf_counter
from typing import Iterable, Protocol, Sequence

from .classifier import classify_window
from .models import CandidateWindow, CloudClip, clamp


@dataclass(frozen=True)
class ModelDescriptor:
    model_id: str
    family: str
    adapter: str
    version: str
    status: str = "available"


@dataclass(frozen=True)
class EmbeddingRerankResult:
    index: int
    score: float
    rank: int
    prompt_label: str
    model: ModelDescriptor
    fallback_reason: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True)
class ClassificationResult:
    clip: CloudClip
    raw_label: str
    confidence: float
    model: ModelDescriptor
    top_labels: tuple[tuple[str, float], ...]


class VideoClassifierAdapter(Protocol):
    descriptor: ModelDescriptor

    def classify(self, window: CandidateWindow) -> ClassificationResult:
        ...


class EmbeddingAdapter(Protocol):
    descriptor: ModelDescriptor

    def rerank(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[EmbeddingRerankResult]:
        ...


class BaselineR2Plus1DAdapter:
    descriptor = ModelDescriptor(
        model_id="r2plus1d-baseline",
        family="video_classifier",
        adapter="r2plus1d",
        version="r2plus1d-baseline-v1",
    )

    def classify(self, window: CandidateWindow) -> ClassificationResult:
        clip = classify_window(window)
        label_scores = _label_scores_for_clip(clip, self.descriptor.version)
        return ClassificationResult(
            clip=clip,
            raw_label=clip.label,
            confidence=clip.confidence,
            model=self.descriptor,
            top_labels=label_scores,
        )


class CLIPLikeEmbeddingAdapter:
    def __init__(self, descriptor: ModelDescriptor, *, batch_size: int = 32, cache_size: int = 4096) -> None:
        self.descriptor = descriptor
        self.batch_size = max(1, batch_size)
        self.cache_size = max(0, cache_size)
        self._score_cache: dict[str, float] = {}

    def rerank(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[EmbeddingRerankResult]:
        started_at = perf_counter()
        if not windows:
            return []
        prompts = list(labels) or ["Highlight"]
        scored: list[tuple[int, float, str]] = []
        for batch_start in range(0, len(windows), self.batch_size):
            for index, window in enumerate(windows[batch_start : batch_start + self.batch_size], start=batch_start):
                best_label = prompts[0]
                best_score = 0.0
                for label in prompts:
                    score = self._score(window, label)
                    if score > best_score:
                        best_score = score
                        best_label = label
                scored.append((index, best_score, best_label))
        scored.sort(key=lambda item: item[1], reverse=True)
        latency_ms = max(0, int((perf_counter() - started_at) * 1000))
        return [
            EmbeddingRerankResult(
                index=index,
                score=round(clamp(score, 0.0, 1.0), 4),
                rank=rank,
                prompt_label=label,
                model=self.descriptor,
                latency_ms=latency_ms,
            )
            for rank, (index, score, label) in enumerate(scored, start=1)
        ]

    def _score(self, window: CandidateWindow, label: str) -> float:
        cache_key = (
            f"{self.descriptor.model_id}|{self.descriptor.version}|{label}|"
            f"{window.start_time:.2f}|{window.end_time:.2f}|{window.peak_time:.2f}|"
            f"{window.audio_score:.4f}|{window.visual_score:.4f}|{window.motion_score:.4f}|"
            f"{window.combined_score:.4f}|{window.event_context_score:.4f}|{window.audio_pop_score:.4f}"
        )
        if cache_key in self._score_cache:
            return self._score_cache[cache_key]
        label_key = label.lower()
        semantic_prior = 0.0
        if any(token in label_key for token in ("shot", "three", "dunk", "layup")):
            semantic_prior += window.event_context_score * 0.28
            semantic_prior += window.visual_score * 0.16
        if any(token in label_key for token in ("steal", "block", "defensive", "turnover")):
            semantic_prior += window.motion_score * 0.22
            semantic_prior += max(window.visual_score - 0.25, 0.0) * 0.1
        if any(token in label_key for token in ("crowd", "reaction", "audio")):
            semantic_prior += window.audio_pop_score * 0.26
            semantic_prior += window.audio_score * 0.18
        hashed = _stable_unit_interval(
            f"{self.descriptor.model_id}|{label}|{window.start_time:.2f}|{window.peak_time:.2f}|{window.combined_score:.4f}"
        )
        score = (window.combined_score * 0.46) + semantic_prior + (hashed * 0.08)
        score = clamp(score, 0.0, 1.0)
        if self.cache_size > 0:
            if len(self._score_cache) >= self.cache_size:
                self._score_cache.pop(next(iter(self._score_cache)))
            self._score_cache[cache_key] = score
        return score


class NullEmbeddingAdapter:
    descriptor = ModelDescriptor(
        model_id="semantic-rerank-disabled",
        family="embedding",
        adapter="none",
        version="semantic-rerank-disabled-v1",
        status="fallback",
    )

    def rerank(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[EmbeddingRerankResult]:
        started_at = perf_counter()
        latency_ms = max(0, int((perf_counter() - started_at) * 1000))
        return [
            EmbeddingRerankResult(
                index=index,
                score=round(clamp(window.combined_score, 0.0, 1.0), 4),
                rank=index + 1,
                prompt_label=labels[0] if labels else "Highlight",
                model=self.descriptor,
                fallback_reason="embedding_adapter_unavailable",
                latency_ms=latency_ms,
            )
            for index, window in enumerate(windows)
        ]


class ModelRegistry:
    def __init__(
        self,
        *,
        classifier: VideoClassifierAdapter | None = None,
        embedding: EmbeddingAdapter | None = None,
    ) -> None:
        self._classifier = classifier or BaselineR2Plus1DAdapter()
        self._embedding = embedding or CLIPLikeEmbeddingAdapter(
            ModelDescriptor(
                model_id="openclip-adapter",
                family="embedding",
                adapter="openclip",
                version="openclip-siglip-compatible-v1",
            )
        )

    @property
    def classifier(self) -> VideoClassifierAdapter:
        return self._classifier

    @property
    def embedding(self) -> EmbeddingAdapter:
        return self._embedding

    def model_versions(self) -> dict[str, str]:
        return {
            "classifier": self._classifier.descriptor.version,
            "embedding": self._embedding.descriptor.version,
        }


def default_model_registry() -> ModelRegistry:
    return ModelRegistry()


def model_registry_for_settings(settings: object) -> ModelRegistry:
    enabled = bool(getattr(settings, "semantic_rerank_enabled", True))
    provider = str(getattr(settings, "semantic_rerank_provider", "openclip") or "openclip").strip().lower()
    model_id = str(getattr(settings, "semantic_rerank_model_id", provider) or provider)
    batch_size = int(getattr(settings, "semantic_rerank_batch_size", 32) or 32)
    cache_size = int(getattr(settings, "semantic_rerank_cache_size", 4096) or 4096)
    if not enabled or provider in {"disabled", "none", "off"}:
        return ModelRegistry(embedding=disabled_embedding_adapter())
    if provider == "siglip":
        return ModelRegistry(embedding=siglip_embedding_adapter(model_id=model_id, batch_size=batch_size, cache_size=cache_size))
    return ModelRegistry(embedding=openclip_embedding_adapter(model_id=model_id, batch_size=batch_size, cache_size=cache_size))


def openclip_embedding_adapter(model_id: str = "openclip-adapter", *, batch_size: int = 32, cache_size: int = 4096) -> EmbeddingAdapter:
    return CLIPLikeEmbeddingAdapter(
        ModelDescriptor(
            model_id=model_id,
            family="embedding",
            adapter="openclip",
            version="openclip-adapter-interface-v1",
        ),
        batch_size=batch_size,
        cache_size=cache_size,
    )


def siglip_embedding_adapter(model_id: str = "siglip-adapter", *, batch_size: int = 32, cache_size: int = 4096) -> EmbeddingAdapter:
    return CLIPLikeEmbeddingAdapter(
        ModelDescriptor(
            model_id=model_id,
            family="embedding",
            adapter="siglip",
            version="siglip-adapter-interface-v1",
        ),
        batch_size=batch_size,
        cache_size=cache_size,
    )


def disabled_embedding_adapter() -> EmbeddingAdapter:
    return NullEmbeddingAdapter()


def _label_scores_for_clip(clip: CloudClip, model_version: str) -> tuple[tuple[str, float], ...]:
    primary = (clip.label, clip.confidence)
    alternates: list[tuple[str, float]] = []
    normalized = clip.label.lower()
    if "dunk" in normalized:
        alternates = [("Made Shot", clip.confidence * 0.78), ("Layup", clip.confidence * 0.52)]
    elif "three" in normalized:
        alternates = [("Made Shot", clip.confidence * 0.82), ("Shot Attempt", clip.confidence * 0.62)]
    elif "shot" in normalized:
        alternates = [("Made Shot", clip.confidence * 0.66), ("Missed Shot", clip.confidence * 0.58)]
    elif "break" in normalized:
        alternates = [("Layup", clip.confidence * 0.56), ("Highlight", clip.confidence * 0.48)]
    elif "reaction" in normalized:
        alternates = [("Highlight", clip.confidence * 0.52), ("Made Shot", clip.confidence * 0.4)]
    else:
        alternates = [("Highlight", clip.confidence * 0.5)]
    return tuple((label, round(clamp(score, 0.0, 1.0), 4)) for label, score in [primary, *alternates])


def _stable_unit_interval(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF

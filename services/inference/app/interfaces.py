from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .models import ActionPrediction, CandidateWindow, EventPrediction, RankedClip


@dataclass
class VideoFeatures:
    source_path: Path
    duration_seconds: float
    fps: float
    frame_count: int
    frame_energy_profile: list[float] = field(default_factory=list)
    audio_energy_profile: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CandidateProposer(ABC):
    @abstractmethod
    def propose(self, features: VideoFeatures) -> list[CandidateWindow]:
        raise NotImplementedError


class ActionRecognizer(ABC):
    @abstractmethod
    def recognize(self, candidate: CandidateWindow, features: VideoFeatures) -> ActionPrediction:
        raise NotImplementedError


class EventInferencer(ABC):
    @abstractmethod
    def infer(self, candidate: CandidateWindow, action: ActionPrediction, features: VideoFeatures) -> EventPrediction:
        raise NotImplementedError


class Reranker(ABC):
    @abstractmethod
    def rerank(self, clips: Sequence[RankedClip]) -> list[RankedClip]:
        raise NotImplementedError


class ArtifactWriter(ABC):
    @abstractmethod
    def write_manifest(self, manifest: dict[str, Any], job_id: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    def write_artifact(self, job_id: str, name: str, content: bytes, media_type: str = "application/octet-stream") -> Path:
        raise NotImplementedError

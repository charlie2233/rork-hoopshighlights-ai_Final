from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Protocol, Sequence

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


@dataclass(frozen=True)
class ClassificationResult:
    clip: CloudClip
    raw_label: str
    confidence: float
    model: ModelDescriptor
    top_labels: tuple[tuple[str, float], ...]


class ModelRuntimeUnavailable(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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
    def __init__(self, descriptor: ModelDescriptor) -> None:
        self.descriptor = descriptor

    def rerank(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[EmbeddingRerankResult]:
        if not windows:
            return []
        prompts = list(labels) or ["Highlight"]
        scored: list[tuple[int, float, str]] = []
        for index, window in enumerate(windows):
            best_label = prompts[0]
            best_score = 0.0
            for label in prompts:
                score = self._score(window, label)
                if score > best_score:
                    best_score = score
                    best_label = label
            scored.append((index, best_score, best_label))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            EmbeddingRerankResult(
                index=index,
                score=round(clamp(score, 0.0, 1.0), 4),
                rank=rank,
                prompt_label=label,
                model=self.descriptor,
            )
            for rank, (index, score, label) in enumerate(scored, start=1)
        ]

    def _score(self, window: CandidateWindow, label: str) -> float:
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
        return clamp(score, 0.0, 1.0)


class RuntimeEmbeddingAdapter:
    def __init__(
        self,
        descriptor: ModelDescriptor,
        *,
        frame_width: int = 224,
        fallback_descriptor: ModelDescriptor | None = None,
    ) -> None:
        self.descriptor = descriptor
        self._frame_width = frame_width
        self._fallback = CLIPLikeEmbeddingAdapter(
            fallback_descriptor
            or ModelDescriptor(
                model_id=f"{descriptor.model_id}-fallback",
                family="embedding",
                adapter=descriptor.adapter,
                version=f"{descriptor.version}-deterministic-fallback",
                status="fallback",
            )
        )

    def rerank(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[EmbeddingRerankResult]:
        if not windows:
            return []
        prompts = list(labels) or ["Highlight"]
        try:
            scored = self._runtime_label_scores(windows, prompts)
        except ModelRuntimeUnavailable as error:
            return _fallback_rerank(windows, prompts, self._fallback, error.reason)
        except Exception:
            return _fallback_rerank(windows, prompts, self._fallback, f"{self.descriptor.adapter}_runtime_failed")

        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            EmbeddingRerankResult(
                index=index,
                score=round(clamp(score, 0.0, 1.0), 4),
                rank=rank,
                prompt_label=label,
                model=self.descriptor,
            )
            for rank, (index, score, label) in enumerate(scored, start=1)
        ]

    def _runtime_label_scores(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[tuple[int, float, str]]:
        raise ModelRuntimeUnavailable(f"{self.descriptor.adapter}_runtime_not_implemented")

    def _extract_frame_paths(self, windows: Sequence[CandidateWindow]) -> tuple[tempfile.TemporaryDirectory[str], list[Path]]:
        source_path = _shared_source_path(windows)
        if source_path is None:
            raise ModelRuntimeUnavailable("source_path_missing")
        temp_dir = tempfile.TemporaryDirectory(prefix="hoops-detection-frames-")
        temp_path = Path(temp_dir.name)
        frame_paths: list[Path] = []
        try:
            for index, window in enumerate(windows):
                output_path = temp_path / f"window_{index:04d}.jpg"
                _extract_frame(
                    source_path,
                    timestamp=window.peak_time,
                    output_path=output_path,
                    width=self._frame_width,
                )
                frame_paths.append(output_path)
        except Exception:
            temp_dir.cleanup()
            raise
        return temp_dir, frame_paths


class OpenCLIPRuntimeEmbeddingAdapter(RuntimeEmbeddingAdapter):
    def __init__(
        self,
        model_id: str = "ViT-B-32",
        *,
        pretrained: str = "laion2b_s34b_b79k",
        device: str | None = None,
        frame_width: int = 224,
    ) -> None:
        super().__init__(
            ModelDescriptor(
                model_id=model_id,
                family="embedding",
                adapter="openclip",
                version=f"openclip-runtime-{model_id}-{pretrained}",
            ),
            frame_width=frame_width,
        )
        self._pretrained = pretrained
        self._device = device or os.getenv("HOOPS_DETECTION_MODEL_DEVICE", "cpu")
        self._runtime: tuple[object, object, object, object] | None = None

    def _runtime_label_scores(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[tuple[int, float, str]]:
        temp_dir, frame_paths = self._extract_frame_paths(windows)
        try:
            model, preprocess, tokenizer, torch = self._load_runtime()
            from PIL import Image

            tokenized = tokenizer(labels).to(self._device)
            with torch.no_grad():
                text_features = model.encode_text(tokenized)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                scored: list[tuple[int, float, str]] = []
                for index, frame_path in enumerate(frame_paths):
                    image = preprocess(Image.open(frame_path).convert("RGB")).unsqueeze(0).to(self._device)
                    image_features = model.encode_image(image)
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                    similarities = (image_features @ text_features.T)[0]
                    best_index = int(torch.argmax(similarities).item())
                    score = float(((similarities[best_index] + 1.0) / 2.0).clamp(0.0, 1.0).item())
                    scored.append((index, score, labels[best_index]))
                return scored
        finally:
            temp_dir.cleanup()

    def _load_runtime(self):
        if self._runtime is not None:
            return self._runtime
        try:
            import open_clip
            import torch
            from PIL import Image  # noqa: F401
        except ImportError as error:
            raise ModelRuntimeUnavailable("openclip_runtime_unavailable") from error
        model, _train_preprocess, preprocess = open_clip.create_model_and_transforms(
            self.descriptor.model_id,
            pretrained=self._pretrained,
            device=self._device,
        )
        model.eval()
        tokenizer = open_clip.get_tokenizer(self.descriptor.model_id)
        self._runtime = (model, preprocess, tokenizer, torch)
        return self._runtime


class SigLIPRuntimeEmbeddingAdapter(RuntimeEmbeddingAdapter):
    def __init__(
        self,
        model_id: str = "google/siglip-base-patch16-224",
        *,
        device: str | None = None,
        frame_width: int = 224,
    ) -> None:
        super().__init__(
            ModelDescriptor(
                model_id=model_id,
                family="embedding",
                adapter="siglip",
                version=f"siglip-runtime-{model_id}",
            ),
            frame_width=frame_width,
        )
        self._device = device or os.getenv("HOOPS_DETECTION_MODEL_DEVICE", "cpu")
        self._runtime: tuple[object, object, object] | None = None

    def _runtime_label_scores(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[tuple[int, float, str]]:
        temp_dir, frame_paths = self._extract_frame_paths(windows)
        try:
            model, processor, torch = self._load_runtime()
            from PIL import Image

            scored: list[tuple[int, float, str]] = []
            with torch.no_grad():
                for index, frame_path in enumerate(frame_paths):
                    image = Image.open(frame_path).convert("RGB")
                    inputs = processor(text=labels, images=image, padding=True, return_tensors="pt")
                    inputs = {key: value.to(self._device) for key, value in inputs.items()}
                    outputs = model(**inputs)
                    logits = getattr(outputs, "logits_per_image", None)
                    if logits is None:
                        raise ModelRuntimeUnavailable("siglip_logits_missing")
                    scores = logits[0].sigmoid()
                    best_index = int(torch.argmax(scores).item())
                    scored.append((index, float(scores[best_index].clamp(0.0, 1.0).item()), labels[best_index]))
            return scored
        finally:
            temp_dir.cleanup()

    def _load_runtime(self):
        if self._runtime is not None:
            return self._runtime
        try:
            import torch
            from PIL import Image  # noqa: F401
            from transformers import AutoModel, AutoProcessor
        except ImportError as error:
            raise ModelRuntimeUnavailable("siglip_runtime_unavailable") from error
        processor = AutoProcessor.from_pretrained(self.descriptor.model_id)
        model = AutoModel.from_pretrained(self.descriptor.model_id).to(self._device)
        model.eval()
        self._runtime = (model, processor, torch)
        return self._runtime


class NullEmbeddingAdapter:
    descriptor = ModelDescriptor(
        model_id="semantic-rerank-disabled",
        family="embedding",
        adapter="none",
        version="semantic-rerank-disabled-v1",
        status="fallback",
    )

    def rerank(self, windows: Sequence[CandidateWindow], labels: Sequence[str]) -> list[EmbeddingRerankResult]:
        return [
            EmbeddingRerankResult(
                index=index,
                score=round(clamp(window.combined_score, 0.0, 1.0), 4),
                rank=index + 1,
                prompt_label=labels[0] if labels else "Highlight",
                model=self.descriptor,
                fallback_reason="embedding_adapter_unavailable",
            )
            for index, window in enumerate(windows)
        ]


class TorchvisionR2Plus1DAdapter:
    def __init__(
        self,
        model_id: str = "r2plus1d_18",
        *,
        weights_path: str | None = None,
        pretrained: bool = True,
        device: str | None = None,
        frame_count: int = 16,
        frame_size: int = 112,
    ) -> None:
        self.descriptor = ModelDescriptor(
            model_id=model_id,
            family="video_classifier",
            adapter="r2plus1d",
            version=f"r2plus1d-runtime-{Path(weights_path).name if weights_path else 'kinetics400'}",
        )
        self._weights_path = weights_path
        self._pretrained = pretrained
        self._device = device or os.getenv("HOOPS_DETECTION_MODEL_DEVICE", "cpu")
        self._frame_count = max(1, frame_count)
        self._frame_size = max(64, frame_size)
        self._fallback = BaselineR2Plus1DAdapter()
        self._runtime: tuple[object, object, tuple[str, ...]] | None = None

    def classify(self, window: CandidateWindow) -> ClassificationResult:
        try:
            label, confidence, top_labels = self._runtime_classify(window)
        except ModelRuntimeUnavailable:
            return self._fallback.classify(window)
        except Exception:
            return self._fallback.classify(window)

        baseline = classify_window(window)
        clip = baseline.model_copy(
            update={
                "label": label,
                "action": label,
                "confidence": confidence,
                "combinedScore": round(clamp((baseline.combinedScore * 0.58) + (confidence * 0.42), 0.0, 1.0), 4),
            }
        )
        return ClassificationResult(
            clip=clip,
            raw_label=label,
            confidence=confidence,
            model=self.descriptor,
            top_labels=top_labels,
        )

    def _runtime_classify(self, window: CandidateWindow) -> tuple[str, float, tuple[tuple[str, float], ...]]:
        if window.source_path is None:
            raise ModelRuntimeUnavailable("source_path_missing")
        temp_dir = tempfile.TemporaryDirectory(prefix="hoops-r2plus1d-frames-")
        try:
            frame_paths = _extract_clip_frame_paths(
                window.source_path,
                start_time=window.start_time,
                end_time=window.end_time,
                frame_count=self._frame_count,
                output_dir=Path(temp_dir.name),
                size=self._frame_size,
            )
            model, torch, categories = self._load_runtime()
            video = self._video_tensor(frame_paths, torch)
            with torch.no_grad():
                logits = model(video)
                probabilities = logits.softmax(dim=1)[0]
                top_count = min(5, int(probabilities.numel()))
                values, indexes = probabilities.topk(top_count)
            top_labels = tuple(
                (
                    _category_for_index(categories, int(index.item())),
                    round(float(value.item()), 4),
                )
                for value, index in zip(values, indexes)
            )
            if not top_labels:
                raise ModelRuntimeUnavailable("r2plus1d_empty_output")
            return top_labels[0][0], top_labels[0][1], top_labels
        finally:
            temp_dir.cleanup()

    def _load_runtime(self):
        if self._runtime is not None:
            return self._runtime
        try:
            import torch
            from PIL import Image  # noqa: F401
            from torchvision.models.video import R2Plus1D_18_Weights, r2plus1d_18
        except ImportError as error:
            raise ModelRuntimeUnavailable("r2plus1d_runtime_unavailable") from error

        categories: tuple[str, ...] = ()
        if self._weights_path:
            model = r2plus1d_18(weights=None)
            state = torch.load(self._weights_path, map_location=self._device)
            state_dict = state.get("state_dict", state) if isinstance(state, dict) else state
            model.load_state_dict(state_dict)
        else:
            weights = R2Plus1D_18_Weights.KINETICS400_V1 if self._pretrained else None
            model = r2plus1d_18(weights=weights)
            if weights is not None:
                categories = tuple(weights.meta.get("categories", ()))
        model.to(self._device)
        model.eval()
        self._runtime = (model, torch, categories)
        return self._runtime

    def _video_tensor(self, frame_paths: Sequence[Path], torch):
        try:
            from PIL import Image
            from torchvision.transforms import functional as transforms
        except ImportError as error:
            raise ModelRuntimeUnavailable("r2plus1d_preprocess_unavailable") from error
        frames = []
        for frame_path in frame_paths:
            image = Image.open(frame_path).convert("RGB")
            tensor = transforms.to_tensor(image)
            tensor = transforms.normalize(
                tensor,
                mean=[0.43216, 0.394666, 0.37645],
                std=[0.22803, 0.22145, 0.216989],
            )
            frames.append(tensor)
        if not frames:
            raise ModelRuntimeUnavailable("r2plus1d_no_frames")
        video = torch.stack(frames, dim=1).unsqueeze(0).to(self._device)
        return video


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
    return ModelRegistry(
        classifier=_classifier_adapter_from_env(),
        embedding=_embedding_adapter_from_env(),
    )


def openclip_embedding_adapter(model_id: str = "openclip-adapter", *, runtime: bool | None = None) -> EmbeddingAdapter:
    if runtime is None:
        runtime = _env_flag("HOOPS_DETECTION_OPENCLIP_RUNTIME", False)
    if runtime:
        return OpenCLIPRuntimeEmbeddingAdapter(
            model_id=os.getenv("HOOPS_DETECTION_OPENCLIP_MODEL", "ViT-B-32"),
            pretrained=os.getenv("HOOPS_DETECTION_OPENCLIP_PRETRAINED", "laion2b_s34b_b79k"),
        )
    return CLIPLikeEmbeddingAdapter(
        ModelDescriptor(
            model_id=model_id,
            family="embedding",
            adapter="openclip",
            version="openclip-adapter-interface-v1",
        )
    )


def siglip_embedding_adapter(model_id: str = "siglip-adapter", *, runtime: bool | None = None) -> EmbeddingAdapter:
    if runtime is None:
        runtime = _env_flag("HOOPS_DETECTION_SIGLIP_RUNTIME", False)
    if runtime:
        return SigLIPRuntimeEmbeddingAdapter(model_id=os.getenv("HOOPS_DETECTION_SIGLIP_MODEL", "google/siglip-base-patch16-224"))
    return CLIPLikeEmbeddingAdapter(
        ModelDescriptor(
            model_id=model_id,
            family="embedding",
            adapter="siglip",
            version="siglip-adapter-interface-v1",
        )
    )


def disabled_embedding_adapter() -> EmbeddingAdapter:
    return NullEmbeddingAdapter()


def r2plus1d_classifier_adapter(*, runtime: bool | None = None) -> VideoClassifierAdapter:
    if runtime is None:
        runtime = _env_flag("HOOPS_DETECTION_R2PLUS1D_RUNTIME", False)
    if runtime:
        return TorchvisionR2Plus1DAdapter(
            weights_path=os.getenv("HOOPS_DETECTION_R2PLUS1D_WEIGHTS") or None,
            pretrained=_env_flag("HOOPS_DETECTION_R2PLUS1D_PRETRAINED", True),
        )
    return BaselineR2Plus1DAdapter()


def _embedding_adapter_from_env() -> EmbeddingAdapter | None:
    adapter = os.getenv("HOOPS_DETECTION_EMBEDDING_ADAPTER", "").strip().lower()
    if adapter in {"none", "disabled"}:
        return disabled_embedding_adapter()
    if adapter in {"openclip-runtime", "openclip_runtime", "openclip-real"}:
        return openclip_embedding_adapter(runtime=True)
    if adapter in {"siglip-runtime", "siglip_runtime", "siglip-real"}:
        return siglip_embedding_adapter(runtime=True)
    if adapter == "siglip":
        return siglip_embedding_adapter(runtime=False)
    if adapter == "openclip":
        return openclip_embedding_adapter(runtime=False)
    if _env_flag("HOOPS_DETECTION_OPENCLIP_RUNTIME", False):
        return openclip_embedding_adapter(runtime=True)
    if _env_flag("HOOPS_DETECTION_SIGLIP_RUNTIME", False):
        return siglip_embedding_adapter(runtime=True)
    return None


def _classifier_adapter_from_env() -> VideoClassifierAdapter | None:
    adapter = os.getenv("HOOPS_DETECTION_CLASSIFIER_ADAPTER", "").strip().lower()
    if adapter in {"r2plus1d-runtime", "r2plus1d_runtime", "r2plus1d-real"}:
        return r2plus1d_classifier_adapter(runtime=True)
    if adapter in {"baseline", "r2plus1d"}:
        return r2plus1d_classifier_adapter(runtime=False)
    if _env_flag("HOOPS_DETECTION_R2PLUS1D_RUNTIME", False):
        return r2plus1d_classifier_adapter(runtime=True)
    return None


def _fallback_rerank(
    windows: Sequence[CandidateWindow],
    labels: Sequence[str],
    fallback: CLIPLikeEmbeddingAdapter,
    reason: str,
) -> list[EmbeddingRerankResult]:
    results = fallback.rerank(windows, labels)
    return [
        EmbeddingRerankResult(
            index=result.index,
            score=result.score,
            rank=result.rank,
            prompt_label=result.prompt_label,
            model=fallback.descriptor,
            fallback_reason=reason,
        )
        for result in results
    ]


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


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _shared_source_path(windows: Sequence[CandidateWindow]) -> Path | None:
    paths = {window.source_path for window in windows if window.source_path is not None}
    if not paths:
        return None
    if len(paths) > 1:
        raise ModelRuntimeUnavailable("mixed_source_paths")
    source_path = next(iter(paths))
    if not source_path.exists():
        raise ModelRuntimeUnavailable("source_path_missing")
    return source_path


def _extract_frame(source_path: Path, *, timestamp: float, output_path: Path, width: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(timestamp, 0.0):.3f}",
        "-i",
        str(source_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:-2",
        "-y",
        str(output_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ModelRuntimeUnavailable("frame_extraction_failed") from error
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise ModelRuntimeUnavailable("frame_extraction_empty")


def _extract_clip_frame_paths(
    source_path: Path,
    *,
    start_time: float,
    end_time: float,
    frame_count: int,
    output_dir: Path,
    size: int,
) -> list[Path]:
    duration = max(end_time - start_time, 0.001)
    frame_paths: list[Path] = []
    for index in range(max(1, frame_count)):
        fraction = (index + 0.5) / max(1, frame_count)
        timestamp = start_time + (duration * fraction)
        output_path = output_dir / f"clip_{index:04d}.jpg"
        _extract_frame(source_path, timestamp=timestamp, output_path=output_path, width=size)
        frame_paths.append(output_path)
    return frame_paths


def _category_for_index(categories: Sequence[str], index: int) -> str:
    if 0 <= index < len(categories):
        return categories[index]
    return f"r2plus1d_class_{index}"

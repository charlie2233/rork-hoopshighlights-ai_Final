from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from services.inference.app.features import sample_video_frames
from services.inference.app.runtime_model import derive_runtime_display_label
from services.inference.datasets.annotations import ANNOTATION_SCHEMA_VERSION, load_annotation_rows
from services.inference.datasets.runtime_training import load_disagreement_rows


VIDEO_LORA_SCHEMA_VERSION = "videomae-lora-v1"
VIDEO_LORA_FEATURE_SCHEMA_VERSION = "videomae-lora-features-v1"
VIDEO_LORA_TARGET_MODULES = "all-linear"
VIDEO_LORA_USE_RSLORA = True
DEFAULT_FRAME_COUNT = 8
DEFAULT_IMAGE_SIZE = 224
DEFAULT_BASELINE_MODEL_NAME = "frozen"
DEFAULT_RSLORA_MODEL_NAME = "videomae-rslora"


@dataclass(frozen=True)
class BasketballClipExample:
    clip_id: str
    source_kind: str
    source_domain: str
    source_set: str
    source_ref: str | None
    source_path: str | None
    split: str
    weight: float
    ignored: bool
    video_available: bool
    event_family: str
    outcome: str
    shot_subtype: str | None
    teacher_confidence: float | None
    human_verified: bool
    reviewer_notes: str
    raw_runtime_outputs: dict[str, Any]
    raw_teacher_outputs: dict[str, Any] | None
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        payload = dataclasses.asdict(self)
        payload["source_path"] = self.source_path
        return payload


@dataclass(frozen=True)
class BasketballLabelSpaces:
    event_family: tuple[str, ...]
    outcome: tuple[str, ...]
    shot_subtype: tuple[str, ...]


@dataclass(frozen=True)
class LoraRunArtifact:
    name: str
    path: Path
    media_type: str = "application/json"
    size_bytes: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class LoraRunResult:
    schema_version: str
    feature_schema_version: str
    model_version: str
    source_dataset: str
    trained_at: str
    tiny_smoke: bool
    label_spaces: BasketballLabelSpaces
    manifest: dict[str, Any]
    baseline_metrics: dict[str, Any]
    rslora_metrics: dict[str, Any]
    artifacts: tuple[LoraRunArtifact, ...]


@dataclass(frozen=True)
class VideoBatch:
    pixel_values: torch.Tensor
    targets: dict[str, torch.Tensor]
    weight: torch.Tensor
    clip_ids: list[str]
    source_paths: list[str | None]
    metadata: list[dict[str, Any]]


class HierarchicalVideoMAELabeler(nn.Module):
    def __init__(self, backbone: nn.Module, label_spaces: BasketballLabelSpaces, dropout: float = 0.1) -> None:
        super().__init__()
        self.backbone = backbone
        self.label_spaces = label_spaces
        hidden_size = int(getattr(backbone.config, "hidden_size"))
        self.dropout = nn.Dropout(dropout)
        self.event_family_head = nn.Linear(hidden_size, len(label_spaces.event_family))
        self.outcome_head = nn.Linear(hidden_size, len(label_spaces.outcome))
        self.shot_subtype_head = nn.Linear(hidden_size, len(label_spaces.shot_subtype))

    def forward(self, pixel_values: torch.Tensor) -> dict[str, torch.Tensor]:
        outputs = self.backbone(pixel_values=pixel_values, return_dict=True)
        if hasattr(outputs, "last_hidden_state"):
            pooled = outputs.last_hidden_state[:, 0]
        elif hasattr(outputs, "pooler_output"):
            pooled = outputs.pooler_output
        else:
            raise RuntimeError("VideoMAE backbone did not return a usable hidden state.")
        pooled = self.dropout(pooled)
        return {
            "eventFamily": self.event_family_head(pooled),
            "outcome": self.outcome_head(pooled),
            "shotSubtype": self.shot_subtype_head(pooled),
        }


def build_videomae_lora_examples(repo_root: Path) -> tuple[list[BasketballClipExample], BasketballLabelSpaces]:
    dataset_dir = repo_root / "services" / "inference" / "datasets"
    gold_rows = load_annotation_rows(dataset_dir / "gold_set.json")
    silver_rows = load_annotation_rows(dataset_dir / "silver_set.json")
    disagreement_rows = load_disagreement_rows(dataset_dir / "disagreement_queue.jsonl")

    examples: list[BasketballClipExample] = []
    for source_kind, source_set, rows in (
        ("gold", "gold_set", gold_rows),
        ("silver", "silver_set", silver_rows),
    ):
        for row in rows:
            source_path = _resolve_source_path(repo_root, row.sourceRef)
            split = _assign_split(
                source_kind=source_kind,
                clip_id=row.clipId,
                event_family=row.eventFamily,
                outcome=row.outcome,
                shot_subtype=row.shotSubtype,
                teacher_confidence=row.teacherConfidence,
            )
            weight, ignored = _weight_and_ignored(source_kind, row.teacherConfidence, source_path is None)
            examples.append(
                BasketballClipExample(
                    clip_id=row.clipId,
                    source_kind=source_kind,
                    source_domain=row.sourceDomain,
                    source_set=source_set,
                    source_ref=row.sourceRef,
                    source_path=str(source_path) if source_path is not None else None,
                    split=split,
                    weight=weight,
                    ignored=ignored,
                    video_available=source_path is not None,
                    event_family=row.eventFamily,
                    outcome=row.outcome,
                    shot_subtype=row.shotSubtype,
                    teacher_confidence=row.teacherConfidence,
                    human_verified=row.humanVerified,
                    reviewer_notes=row.reviewerNotes,
                    raw_runtime_outputs=row.rawRuntimeOutputs or {},
                    raw_teacher_outputs=row.rawTeacherOutputs,
                    schema_version=row.schemaVersion or ANNOTATION_SCHEMA_VERSION,
                )
            )

    for row in disagreement_rows:
        gold = row.get("gold", {})
        teacher = row.get("teacher", {})
        clip_id = str(row.get("clipId"))
        split = _assign_split(
            source_kind="disagreement",
            clip_id=clip_id,
            event_family=str(gold.get("eventFamily") or "other"),
            outcome=str(gold.get("outcome") or "uncertain"),
            shot_subtype=gold.get("shotSubtype"),
            teacher_confidence=_coerce_optional_float(teacher.get("confidence")),
        )
        weight, ignored = _weight_and_ignored("disagreement", teacher.get("confidence"), True)
        examples.append(
            BasketballClipExample(
                clip_id=clip_id,
                source_kind="disagreement",
                source_domain=str(row.get("sourceDomain") or "disagreement_queue"),
                source_set="disagreement_queue",
                source_ref=None,
                source_path=None,
                split=split,
                weight=weight,
                ignored=True or ignored,
                video_available=False,
                event_family=str(gold.get("eventFamily") or "other"),
                outcome=str(gold.get("outcome") or "uncertain"),
                shot_subtype=gold.get("shotSubtype"),
                teacher_confidence=_coerce_optional_float(teacher.get("confidence")),
                human_verified=False,
                reviewer_notes=str(row.get("reviewerNotes") or ""),
                raw_runtime_outputs=row.get("runtime") or {},
                raw_teacher_outputs=row.get("teacher") or None,
                schema_version=str(row.get("schemaVersion") or ANNOTATION_SCHEMA_VERSION),
            )
        )

    label_spaces = build_basketball_label_spaces(examples)
    return examples, label_spaces


def build_basketball_label_spaces(examples: Sequence[BasketballClipExample]) -> BasketballLabelSpaces:
    event_family = _ordered_labels(examples, "event_family", fallback=("other",))
    outcome = _ordered_labels(examples, "outcome", fallback=("uncertain",))
    shot_subtype = tuple(
        _dedupe_preserve_order(
            ["null"]
            + [example.shot_subtype for example in examples if example.shot_subtype]
            + ["dunk", "layup", "jumper", "three", "putback"]
        )
    )
    return BasketballLabelSpaces(event_family=event_family, outcome=outcome, shot_subtype=shot_subtype)


def build_videomae_lora_manifest(
    *,
    repo_root: Path,
    examples: Sequence[BasketballClipExample],
    label_spaces: BasketballLabelSpaces,
) -> dict[str, Any]:
    split_counts = {"train": 0, "val": 0, "test": 0}
    source_counts = {"gold": 0, "silver": 0, "disagreement": 0}
    video_available = 0
    weighted_examples = 0
    for example in examples:
        split_counts[example.split] = split_counts.get(example.split, 0) + 1
        source_counts[example.source_kind] = source_counts.get(example.source_kind, 0) + 1
        video_available += int(example.video_available)
        weighted_examples += int(example.weight > 0.0 and not example.ignored)
    return {
        "schemaVersion": VIDEO_LORA_SCHEMA_VERSION,
        "featureSchemaVersion": VIDEO_LORA_FEATURE_SCHEMA_VERSION,
        "sourceDataset": _display_path(repo_root / "services" / "inference" / "datasets"),
        "modelVersion": DEFAULT_RSLORA_MODEL_NAME,
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "labelSpaces": {
            "eventFamily": list(label_spaces.event_family),
            "outcome": list(label_spaces.outcome),
            "shotSubtype": list(label_spaces.shot_subtype),
        },
        "summary": {
            "totalExamples": len(examples),
            "weightedExamples": weighted_examples,
            "videoAvailableExamples": video_available,
            "splitCounts": split_counts,
            "sourceCounts": source_counts,
        },
        "notes": [
            "Gold clips remain the calibration/evaluation anchor.",
            "Silver clips are weighted by teacher confidence.",
            "Disagreement rows are retained for audit and downstream fusion, but are excluded from video training when source video is unavailable.",
            "X-CLIP remains frozen; LoRA applies only to the VideoMAE backbone.",
        ],
    }


def load_videomae_lora_export(repo_root: Path) -> tuple[list[BasketballClipExample], dict[str, Any]]:
    export_dir = repo_root / "services" / "inference" / "datasets" / "runtime_training" / "videomae_lora_v1"
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    examples: list[BasketballClipExample] = []
    for line in (export_dir / "all_records.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        examples.append(
            BasketballClipExample(
                clip_id=str(record["clipId"]),
                source_kind=str(record["sourceKind"]),
                source_domain=str(record["sourceDomain"]),
                source_set=str(record["sourceSet"]),
                source_ref=None if record.get("sourceRef") is None else str(record["sourceRef"]),
                source_path=None if record.get("resolvedSourcePath") is None else str(record["resolvedSourcePath"]),
                split=str(record["split"]),
                weight=float(record.get("sampleWeight", 1.0)),
                ignored=bool(record.get("ignored", False)),
                video_available=bool(record.get("trainingEligible", False)) and bool(record.get("sourcePathExists", False)),
                event_family=str(record["eventFamily"]),
                outcome=str(record["outcome"]),
                shot_subtype=None if record.get("shotSubtype") is None else str(record["shotSubtype"]),
                teacher_confidence=_coerce_optional_float(record.get("teacherConfidence")),
                human_verified=bool(record.get("humanVerified", False)),
                reviewer_notes=str(record.get("reviewerNotes") or ""),
                raw_runtime_outputs=dict(record.get("rawRuntimeOutputs") or {}),
                raw_teacher_outputs=record.get("rawTeacherOutputs"),
                schema_version=str(record.get("schemaVersion") or ANNOTATION_SCHEMA_VERSION),
            )
        )
    return examples, manifest


def create_videomae_backbone(
    *,
    model_name: str | None = None,
    tiny_smoke: bool = False,
    frame_count: int = DEFAULT_FRAME_COUNT,
    image_size: int = DEFAULT_IMAGE_SIZE,
) -> tuple[nn.Module, Any]:
    try:
        from transformers import VideoMAEConfig, VideoMAEModel  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency errors are surfaced at runtime
        raise RuntimeError("transformers with VideoMAE support is required") from exc

    if tiny_smoke:
        config = VideoMAEConfig(
            image_size=image_size,
            num_frames=frame_count,
            tubelet_size=2,
            hidden_size=64,
            intermediate_size=128,
            num_hidden_layers=2,
            num_attention_heads=4,
            qkv_bias=True,
            use_mean_pooling=False,
        )
        backbone = VideoMAEModel(config)
        processor = None
        return backbone, processor

    if not model_name:
        raise ValueError("model_name is required unless tiny_smoke is enabled")
    backbone = VideoMAEModel.from_pretrained(model_name)
    processor = None
    return backbone, processor


def apply_rslora_to_backbone(
    backbone: nn.Module,
    *,
    r: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
) -> tuple[nn.Module, dict[str, Any]]:
    try:
        from peft import LoraConfig, TaskType, get_peft_model  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency errors are surfaced at runtime
        raise RuntimeError("peft is required for rsLoRA training") from exc

    config = LoraConfig(
        task_type=TaskType.FEATURE_EXTRACTION,
        target_modules=VIDEO_LORA_TARGET_MODULES,
        use_rslora=VIDEO_LORA_USE_RSLORA,
        r=r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
    )
    adapted = get_peft_model(backbone, config)
    return adapted, {
        "targetModules": VIDEO_LORA_TARGET_MODULES,
        "useRslora": VIDEO_LORA_USE_RSLORA,
        "r": r,
        "loraAlpha": lora_alpha,
        "loraDropout": lora_dropout,
    }


def train_hierarchical_labeler(
    *,
    model: HierarchicalVideoMAELabeler,
    examples: Sequence[BasketballClipExample],
    label_spaces: BasketballLabelSpaces,
    frame_count: int = DEFAULT_FRAME_COUNT,
    batch_size: int = 1,
    epochs: int = 1,
    learning_rate: float = 2e-4,
    device: str = "cpu",
    image_size: int = DEFAULT_IMAGE_SIZE,
) -> dict[str, Any]:
    if not examples:
        raise ValueError("No examples available for training")
    device_t = torch.device(device)
    model = model.to(device_t)
    model.train()

    optimizer = torch.optim.AdamW((param for param in model.parameters() if param.requires_grad), lr=learning_rate)
    label_lookup = {
        "event_family": {label: index for index, label in enumerate(label_spaces.event_family)},
        "outcome": {label: index for index, label in enumerate(label_spaces.outcome)},
        "shot_subtype": {label: index for index, label in enumerate(label_spaces.shot_subtype)},
    }
    losses: list[float] = []

    train_examples = [example for example in examples if example.video_available and example.source_path and not example.ignored and example.split == "train"]
    if not train_examples:
        train_examples = [example for example in examples if example.video_available and example.source_path and not example.ignored]
    if not train_examples:
        raise ValueError("No video-backed training examples available")

    for epoch in range(epochs):
        for example in train_examples:
            frames = sample_video_frames(Path(example.source_path), frame_count=frame_count)
            if not frames:
                continue
            pixel_values = _frames_to_tensor(frames, image_size=image_size).to(device_t)
            outputs = model(pixel_values=pixel_values)
            targets = {
                "eventFamily": torch.tensor([label_lookup["event_family"][example.event_family]], device=device_t),
                "outcome": torch.tensor([label_lookup["outcome"][example.outcome]], device=device_t),
                "shotSubtype": torch.tensor(
                    [label_lookup["shot_subtype"][_normalize_shot_subtype(example.shot_subtype)]],
                    device=device_t,
                ),
            }
            loss = _hierarchical_loss(outputs, targets, label_lookup, example.weight)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))

    return {
        "trainExamples": len(train_examples),
        "epochs": epochs,
        "meanLoss": round(float(np.mean(losses)) if losses else 0.0, 6),
        "finalLoss": round(losses[-1], 6) if losses else 0.0,
        "device": str(device_t),
    }


@torch.no_grad()
def predict_with_model(
    model: HierarchicalVideoMAELabeler,
    example: BasketballClipExample,
    *,
    label_spaces: BasketballLabelSpaces,
    frame_count: int = DEFAULT_FRAME_COUNT,
    image_size: int = DEFAULT_IMAGE_SIZE,
    device: str = "cpu",
    temperature: dict[str, float] | None = None,
) -> dict[str, Any]:
    device_t = torch.device(device)
    model = model.to(device_t)
    model.eval()

    if not example.video_available or not example.source_path:
        raise ValueError(f"Example {example.clip_id} does not have a video source")
    frames = sample_video_frames(Path(example.source_path), frame_count=frame_count)
    if not frames:
        raise RuntimeError(f"No frames sampled for {example.clip_id}")
    pixel_values = _frames_to_tensor(frames, image_size=image_size).to(device_t)
    outputs = model(pixel_values=pixel_values)

    family = _prediction_from_logits(
        outputs["eventFamily"],
        classes=label_spaces.event_family,
        temperature=temperature.get("eventFamily") if temperature else None,
    )
    outcome = _prediction_from_logits(
        outputs["outcome"],
        classes=label_spaces.outcome,
        temperature=temperature.get("outcome") if temperature else None,
    )
    subtype = _prediction_from_logits(
        outputs["shotSubtype"],
        classes=label_spaces.shot_subtype,
        temperature=temperature.get("shotSubtype") if temperature else None,
    )

    event_family = family["label"]
    if family["is_uncertain"]:
        event_family = "other"
    resolved_outcome = _resolve_outcome(event_family, outcome)
    shot_subtype = None
    if event_family == "shot_attempt" and not subtype["is_uncertain"] and subtype["label"] != "null":
        shot_subtype = subtype["label"]

    canonical_label, display_label = derive_runtime_display_label(
        event_family=event_family,
        outcome=resolved_outcome,
        shot_subtype=shot_subtype,
    )
    confidence_before_mapping = family["confidence"]
    confidence_after_mapping = _mapped_confidence(display_label, family, outcome, subtype)
    return {
        "clipId": example.clip_id,
        "sourceKind": example.source_kind,
        "sourceDomain": example.source_domain,
        "sourceSet": example.source_set,
        "split": example.split,
        "weight": example.weight,
        "videoAvailable": example.video_available,
        "eventFamily": event_family,
        "outcome": resolved_outcome,
        "shotSubtype": shot_subtype,
        "confidenceBeforeMapping": round(confidence_before_mapping, 4),
        "confidenceAfterMapping": round(confidence_after_mapping, 4),
        "confidence": round(confidence_after_mapping, 4),
        "canonicalLabel": canonical_label,
        "displayLabel": display_label,
        "isUncertain": bool(family["is_uncertain"] or outcome["is_uncertain"] or display_label == "Highlight"),
        "rawEventFamily": family,
        "rawOutcome": outcome,
        "rawShotSubtype": subtype,
        "rawTopLabels": {
            "eventFamily": family["topLabels"],
            "outcome": outcome["topLabels"],
            "shotSubtype": subtype["topLabels"],
        },
        "temperature": temperature or {},
    }


def export_lora_logits_artifacts(
    *,
    output_dir: Path,
    label_spaces: BasketballLabelSpaces,
    manifest: dict[str, Any],
    baseline_predictions: Sequence[dict[str, Any]],
    rslora_predictions: Sequence[dict[str, Any]],
    baseline_metrics: dict[str, Any],
    rslora_metrics: dict[str, Any],
    baseline_training: dict[str, Any],
    rslora_training: dict[str, Any],
) -> tuple[LoraRunArtifact, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[LoraRunArtifact] = []

    _write_json(output_dir / "manifest.json", manifest)
    _write_json(output_dir / "label_spaces.json", dataclasses.asdict(label_spaces))
    _write_json(output_dir / "baseline_metrics.json", baseline_metrics)
    _write_json(output_dir / "rslora_metrics.json", rslora_metrics)
    _write_json(output_dir / "baseline_training.json", baseline_training)
    _write_json(output_dir / "rslora_training.json", rslora_training)
    _write_jsonl(output_dir / "baseline_logits.jsonl", baseline_predictions)
    _write_jsonl(output_dir / "rslora_logits.jsonl", rslora_predictions)
    _write_text(output_dir / "comparison_report.md", render_comparison_report(
        manifest=manifest,
        label_spaces=label_spaces,
        baseline_metrics=baseline_metrics,
        rslora_metrics=rslora_metrics,
        baseline_training=baseline_training,
        rslora_training=rslora_training,
        baseline_predictions=baseline_predictions,
        rslora_predictions=rslora_predictions,
    ))

    for name in [
        "manifest.json",
        "label_spaces.json",
        "baseline_metrics.json",
        "rslora_metrics.json",
        "baseline_training.json",
        "rslora_training.json",
        "baseline_logits.jsonl",
        "rslora_logits.jsonl",
        "comparison_report.md",
    ]:
        path = output_dir / name
        artifacts.append(
            LoraRunArtifact(
                name=name,
                path=path,
                media_type="text/markdown" if name.endswith(".md") else ("application/jsonl" if name.endswith(".jsonl") else "application/json"),
                size_bytes=path.stat().st_size,
                sha256=_sha256_file(path),
            )
        )
    return tuple(artifacts)


def render_comparison_report(
    *,
    manifest: dict[str, Any],
    label_spaces: BasketballLabelSpaces,
    baseline_metrics: dict[str, Any],
    rslora_metrics: dict[str, Any],
    baseline_training: dict[str, Any],
    rslora_training: dict[str, Any],
    baseline_predictions: Sequence[dict[str, Any]],
    rslora_predictions: Sequence[dict[str, Any]],
) -> str:
    lines = ["# VideoMAE LoRA vs Frozen Baseline", ""]
    lines.append(f"- Schema version: `{VIDEO_LORA_SCHEMA_VERSION}`")
    lines.append(f"- Feature schema version: `{VIDEO_LORA_FEATURE_SCHEMA_VERSION}`")
    lines.append(f"- Source dataset: `{manifest['sourceDataset']}`")
    lines.append(f"- Tiny smoke: `{manifest['summary'].get('tinySmoke', False)}`")
    lines.append(f"- Event families: `{list(label_spaces.event_family)}`")
    lines.append(f"- Outcomes: `{list(label_spaces.outcome)}`")
    lines.append(f"- Shot subtypes: `{list(label_spaces.shot_subtype)}`")
    lines.append("")
    lines.append("## Training")
    lines.append(f"- Frozen baseline loss: `{baseline_training.get('meanLoss')}`")
    lines.append(f"- rsLoRA loss: `{rslora_training.get('meanLoss')}`")
    lines.append(f"- Baseline train examples: `{baseline_training.get('trainExamples')}`")
    lines.append(f"- rsLoRA train examples: `{rslora_training.get('trainExamples')}`")
    lines.append("")
    lines.append("## Metrics")
    lines.append(f"- Baseline eventFamily accuracy: `{baseline_metrics['eventFamily']['accuracy']}`")
    lines.append(f"- rsLoRA eventFamily accuracy: `{rslora_metrics['eventFamily']['accuracy']}`")
    lines.append(f"- Baseline outcome accuracy: `{baseline_metrics['outcome']['accuracy']}`")
    lines.append(f"- rsLoRA outcome accuracy: `{rslora_metrics['outcome']['accuracy']}`")
    lines.append(f"- Baseline shotSubtype accuracy: `{baseline_metrics['shotSubtype']['accuracy']}`")
    lines.append(f"- rsLoRA shotSubtype accuracy: `{rslora_metrics['shotSubtype']['accuracy']}`")
    lines.append("")
    lines.append("## Artifact Preview")
    if baseline_predictions:
        first = baseline_predictions[0]
        lines.append(f"- Baseline first clip: `{first['clipId']}` -> `{first['displayLabel']}`")
    if rslora_predictions:
        first = rslora_predictions[0]
        lines.append(f"- rsLoRA first clip: `{first['clipId']}` -> `{first['displayLabel']}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("- X-CLIP stays frozen; only the VideoMAE backbone receives LoRA adapters.")
    lines.append("- Adapted logits are exported per head for downstream fusion.")
    lines.append("- Gold clips remain the calibration anchor; disagreement rows stay in the manifest for audit.")
    return "\n".join(lines)


def fit_temperature(logits: np.ndarray, labels: np.ndarray, classes: Sequence[str]) -> float:
    if logits.size == 0 or labels.size == 0:
        return 1.0
    class_lookup = {str(label): index for index, label in enumerate(classes)}
    label_indices = np.asarray([class_lookup[str(label)] for label in labels], dtype=np.int64)
    best_temperature = 1.0
    best_loss = float("inf")
    for temperature in np.linspace(0.6, 2.2, 33):
        probabilities = _softmax_with_temperature(logits, float(temperature))
        loss = _negative_log_likelihood(probabilities, label_indices)
        if loss < best_loss:
            best_loss = loss
            best_temperature = float(temperature)
    return best_temperature


def predict_dataset(
    *,
    model: HierarchicalVideoMAELabeler,
    examples: Sequence[BasketballClipExample],
    label_spaces: BasketballLabelSpaces,
    frame_count: int = DEFAULT_FRAME_COUNT,
    image_size: int = DEFAULT_IMAGE_SIZE,
    device: str = "cpu",
    temperature: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    for example in examples:
        if not example.video_available or not example.source_path:
            continue
        predictions.append(
            predict_with_model(
                model,
                example,
                label_spaces=label_spaces,
                frame_count=frame_count,
                image_size=image_size,
                device=device,
                temperature=temperature,
            )
        )
    return predictions


def train_and_export_lora_run(
    *,
    repo_root: Path,
    output_dir: Path,
    model_name: str | None = None,
    tiny_smoke: bool = False,
    frame_count: int = DEFAULT_FRAME_COUNT,
    image_size: int = DEFAULT_IMAGE_SIZE,
    epochs: int = 1,
    batch_size: int = 1,
    learning_rate: float = 2e-4,
    device: str = "cpu",
    r: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
) -> LoraRunResult:
    examples, export_manifest = load_videomae_lora_export(repo_root)
    label_spaces = BasketballLabelSpaces(
        event_family=tuple(export_manifest.get("labelSpaces", {}).get("eventFamily", [])),
        outcome=tuple(export_manifest.get("labelSpaces", {}).get("outcome", [])),
        shot_subtype=tuple(export_manifest.get("labelSpaces", {}).get("shotSubtype", [])),
    )
    manifest = export_manifest
    manifest = {
        **manifest,
        "summary": {
            **manifest["summary"],
            "tinySmoke": tiny_smoke,
            "frameCount": frame_count,
            "imageSize": image_size,
            "epochs": epochs,
            "batchSize": batch_size,
            "learningRate": learning_rate,
            "device": device,
        },
    }

    backbone_baseline, _ = create_videomae_backbone(
        model_name=model_name,
        tiny_smoke=tiny_smoke,
        frame_count=frame_count,
        image_size=image_size,
    )
    baseline_model = HierarchicalVideoMAELabeler(backbone_baseline, label_spaces)
    _freeze_backbone(baseline_model.backbone)
    baseline_training = train_hierarchical_labeler(
        model=baseline_model,
        examples=examples,
        label_spaces=label_spaces,
        frame_count=frame_count,
        batch_size=batch_size,
        epochs=epochs,
        learning_rate=learning_rate,
        device=device,
        image_size=image_size,
    )
    baseline_temperatures = _fit_head_temperatures(
        model=baseline_model,
        examples=[example for example in examples if example.video_available and example.source_path and example.split == "val"],
        label_spaces=label_spaces,
        frame_count=frame_count,
        image_size=image_size,
        device=device,
    )
    baseline_predictions = predict_dataset(
        model=baseline_model,
        examples=[example for example in examples if example.video_available and example.source_path and example.split in {"val", "test"}],
        label_spaces=label_spaces,
        frame_count=frame_count,
        image_size=image_size,
        device=device,
        temperature=baseline_temperatures,
    )
    baseline_metrics = evaluate_predictions(baseline_predictions, label_spaces)

    backbone_lora, _ = create_videomae_backbone(
        model_name=model_name,
        tiny_smoke=tiny_smoke,
        frame_count=frame_count,
        image_size=image_size,
    )
    backbone_lora, lora_metadata = apply_rslora_to_backbone(
        backbone_lora,
        r=r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
    )
    rslora_model = HierarchicalVideoMAELabeler(backbone_lora, label_spaces)
    rslora_training = train_hierarchical_labeler(
        model=rslora_model,
        examples=examples,
        label_spaces=label_spaces,
        frame_count=frame_count,
        batch_size=batch_size,
        epochs=epochs,
        learning_rate=learning_rate,
        device=device,
        image_size=image_size,
    )
    rslora_temperatures = _fit_head_temperatures(
        model=rslora_model,
        examples=[example for example in examples if example.video_available and example.source_path and example.split == "val"],
        label_spaces=label_spaces,
        frame_count=frame_count,
        image_size=image_size,
        device=device,
    )
    rslora_predictions = predict_dataset(
        model=rslora_model,
        examples=[example for example in examples if example.video_available and example.source_path and example.split in {"val", "test"}],
        label_spaces=label_spaces,
        frame_count=frame_count,
        image_size=image_size,
        device=device,
        temperature=rslora_temperatures,
    )
    baseline_metrics = {
        **baseline_metrics,
        "calibration": baseline_temperatures,
    }
    rslora_metrics = evaluate_predictions(rslora_predictions, label_spaces)
    rslora_metrics = {
        **rslora_metrics,
        "calibration": rslora_temperatures,
        "lora": lora_metadata,
    }

    artifacts = export_lora_logits_artifacts(
        output_dir=output_dir,
        label_spaces=label_spaces,
        manifest=manifest,
        baseline_predictions=baseline_predictions,
        rslora_predictions=rslora_predictions,
        baseline_metrics=baseline_metrics,
        rslora_metrics=rslora_metrics,
        baseline_training=baseline_training,
        rslora_training=rslora_training,
    )
    return LoraRunResult(
        schema_version=VIDEO_LORA_SCHEMA_VERSION,
        feature_schema_version=VIDEO_LORA_FEATURE_SCHEMA_VERSION,
        model_version=DEFAULT_RSLORA_MODEL_NAME,
        source_dataset=_display_path(repo_root / "services" / "inference" / "datasets"),
        trained_at=datetime.now(timezone.utc).isoformat(),
        tiny_smoke=tiny_smoke,
        label_spaces=label_spaces,
        manifest=manifest,
        baseline_metrics=baseline_metrics,
        rslora_metrics=rslora_metrics,
        artifacts=artifacts,
    )


def evaluate_predictions(
    predictions: Sequence[dict[str, Any]],
    label_spaces: BasketballLabelSpaces,
) -> dict[str, Any]:
    if not predictions:
        return {"sampleCount": 0}
    report = {
        "eventFamily": _classification_report(
            labels=[str(item.get("eventFamily")) for item in predictions],
            predictions=[str((item.get("rawEventFamily") or {}).get("label") or item.get("eventFamily")) for item in predictions],
            classes=label_spaces.event_family,
        ),
        "outcome": _classification_report(
            labels=[str(item.get("outcome")) for item in predictions],
            predictions=[str((item.get("rawOutcome") or {}).get("label") or item.get("outcome")) for item in predictions],
            classes=label_spaces.outcome,
        ),
        "shotSubtype": _classification_report(
            labels=[_normalize_shot_subtype(item.get("shotSubtype")) for item in predictions],
            predictions=[_normalize_shot_subtype((item.get("rawShotSubtype") or {}).get("label") or item.get("shotSubtype")) for item in predictions],
            classes=label_spaces.shot_subtype,
        ),
        "sampleCount": len(predictions),
        "uncertaintyRate": round(
            float(np.mean([1.0 if item.get("isUncertain") else 0.0 for item in predictions])),
            4,
        ),
        "displayLabelDistribution": _distribution(item.get("displayLabel") for item in predictions),
        "eventFamilyDistribution": _distribution(item.get("eventFamily") for item in predictions),
        "outcomeDistribution": _distribution(item.get("outcome") for item in predictions),
        "shotSubtypeDistribution": _distribution(item.get("shotSubtype") or "null" for item in predictions),
        "durationSummary": _duration_summary(predictions),
        "examples": [
            {
                "clipId": item.get("clipId"),
                "displayLabel": item.get("displayLabel"),
                "eventFamily": item.get("eventFamily"),
                "outcome": item.get("outcome"),
                "shotSubtype": item.get("shotSubtype"),
                "confidenceBeforeMapping": item.get("confidenceBeforeMapping"),
                "confidenceAfterMapping": item.get("confidenceAfterMapping"),
            }
            for item in predictions[:5]
        ],
    }
    return report


def _classification_report(*, labels: Sequence[str], predictions: Sequence[str], classes: Sequence[str]) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, top_k_accuracy_score

    if not labels:
        return {"sampleCount": 0}
    classes = list(classes)
    label_list = [str(label) for label in labels]
    pred_list = [str(prediction) for prediction in predictions]
    accuracy = accuracy_score(label_list, pred_list)
    macro_f1 = f1_score(label_list, pred_list, average="macro", zero_division=0)
    matrix = confusion_matrix(label_list, pred_list, labels=classes)
    confusions = []
    for row_index, expected in enumerate(classes):
        for col_index, predicted in enumerate(classes):
            count = int(matrix[row_index, col_index])
            if count:
                confusions.append({"expected": expected, "predicted": predicted, "count": count})
    return {
        "sampleCount": len(labels),
        "accuracy": round(float(accuracy), 4),
        "macroF1": round(float(macro_f1), 4),
        "confusions": confusions,
        "labelDistribution": _distribution(label_list),
        "predictionDistribution": _distribution(pred_list),
    }


def _duration_summary(predictions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    durations = [float(item["clipDurationSeconds"]) for item in predictions if item.get("clipDurationSeconds") is not None]
    if not durations:
        return {"sampleCount": 0}
    durations = sorted(durations)
    return {
        "sampleCount": len(durations),
        "min": round(float(durations[0]), 4),
        "median": round(float(np.median(durations)), 4),
        "p90": round(float(np.quantile(durations, 0.9)), 4),
        "max": round(float(durations[-1]), 4),
    }


def _fit_head_temperatures(
    *,
    model: HierarchicalVideoMAELabeler,
    examples: Sequence[BasketballClipExample],
    label_spaces: BasketballLabelSpaces,
    frame_count: int,
    image_size: int,
    device: str,
) -> dict[str, float]:
    logits_by_head: dict[str, list[np.ndarray]] = {"eventFamily": [], "outcome": [], "shotSubtype": []}
    labels_by_head: dict[str, list[str]] = {"eventFamily": [], "outcome": [], "shotSubtype": []}
    for example in examples:
        if not example.video_available or not example.source_path:
            continue
        frames = sample_video_frames(Path(example.source_path), frame_count=frame_count)
        if not frames:
            continue
        pixel_values = _frames_to_tensor(frames, image_size=image_size).to(torch.device(device))
        outputs = model(pixel_values=pixel_values)
        logits_by_head["eventFamily"].append(outputs["eventFamily"].detach().cpu().numpy()[0])
        logits_by_head["outcome"].append(outputs["outcome"].detach().cpu().numpy()[0])
        logits_by_head["shotSubtype"].append(outputs["shotSubtype"].detach().cpu().numpy()[0])
        labels_by_head["eventFamily"].append(example.event_family)
        labels_by_head["outcome"].append(example.outcome)
        labels_by_head["shotSubtype"].append(_normalize_shot_subtype(example.shot_subtype))
    temperatures = {}
    temperatures["eventFamily"] = fit_temperature(np.asarray(logits_by_head["eventFamily"]), np.asarray(labels_by_head["eventFamily"]), label_spaces.event_family)
    temperatures["outcome"] = fit_temperature(np.asarray(logits_by_head["outcome"]), np.asarray(labels_by_head["outcome"]), label_spaces.outcome)
    temperatures["shotSubtype"] = fit_temperature(np.asarray(logits_by_head["shotSubtype"]), np.asarray(labels_by_head["shotSubtype"]), label_spaces.shot_subtype)
    return temperatures


def _hierarchical_loss(
    outputs: dict[str, torch.Tensor],
    targets: dict[str, torch.Tensor],
    label_lookup: dict[str, dict[str, int]],
    weight: float,
) -> torch.Tensor:
    family_loss = F.cross_entropy(outputs["eventFamily"], targets["eventFamily"], reduction="none")
    outcome_loss = F.cross_entropy(outputs["outcome"], targets["outcome"], reduction="none")
    subtype_loss = F.cross_entropy(outputs["shotSubtype"], targets["shotSubtype"], reduction="none")
    shot_attempt_idx = label_lookup["event_family"].get("shot_attempt")
    if shot_attempt_idx is None:
        subtype_mask = torch.zeros_like(targets["eventFamily"], dtype=torch.bool)
    else:
        subtype_mask = targets["eventFamily"] == shot_attempt_idx
    subtype_loss = torch.where(subtype_mask, subtype_loss, torch.zeros_like(subtype_loss))
    loss = family_loss + (0.75 * outcome_loss) + (0.5 * subtype_loss)
    return (loss * float(weight)).mean()


def _freeze_backbone(backbone: nn.Module) -> None:
    for parameter in backbone.parameters():
        parameter.requires_grad = False


def _prediction_from_logits(
    logits: torch.Tensor,
    *,
    classes: Sequence[str],
    temperature: float | None = None,
) -> dict[str, Any]:
    logits = logits.detach().float()
    if logits.ndim == 2:
        logits = logits[0]
    if temperature is not None and temperature > 0:
        logits = logits / float(max(temperature, 1e-3))
    probabilities = torch.softmax(logits, dim=-1)
    values, indices = torch.topk(probabilities, k=min(3, probabilities.shape[-1]))
    top_labels = [
        {"label": str(classes[index.item()]), "confidence": round(float(value.item()), 4)}
        for value, index in zip(values, indices, strict=False)
    ]
    top_index = int(indices[0].item())
    second = float(values[1].item()) if len(values) > 1 else 0.0
    top = float(values[0].item())
    return {
        "index": top_index,
        "confidence": round(top, 4),
        "margin": round(max(top - second, 0.0), 4),
        "label": str(classes[top_index]),
        "topLabels": top_labels,
        "is_uncertain": bool(top < 0.45 or (top - second) < 0.05),
    }


def _mapped_confidence(display_label: str, family: dict[str, Any], outcome: dict[str, Any], subtype: dict[str, Any]) -> float:
    confidence = family["confidence"]
    if display_label in {"Dunk", "Layup", "Three Pointer"}:
        confidence = max(confidence, subtype["confidence"])
    elif display_label == "Block":
        confidence = max(confidence, outcome["confidence"])
    elif display_label == "Made Shot":
        confidence = max(confidence, min(outcome["confidence"], subtype["confidence"]))
    if display_label == "Highlight" and (family["is_uncertain"] or outcome["is_uncertain"]):
        confidence = min(confidence, 0.46)
    return min(max(confidence, 0.0), 1.0)


def _resolve_outcome(event_family: str, prediction: dict[str, Any]) -> str:
    if event_family != "shot_attempt":
        return "uncertain"
    if prediction["is_uncertain"]:
        return "uncertain"
    return str(prediction["label"])


def _frames_to_tensor(frames: Sequence[Any], *, image_size: int) -> torch.Tensor:
    tensor_frames = []
    for frame in frames:
        image = frame.convert("RGB").resize((image_size, image_size))
        array = np.asarray(image, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(array).permute(2, 0, 1)
        tensor_frames.append(tensor)
    stacked = torch.stack(tensor_frames, dim=0)
    mean = torch.tensor([0.45, 0.45, 0.45], dtype=stacked.dtype).view(1, 3, 1, 1)
    std = torch.tensor([0.225, 0.225, 0.225], dtype=stacked.dtype).view(1, 3, 1, 1)
    normalized = (stacked - mean) / std
    return normalized.unsqueeze(0)


def _assign_split(
    *,
    source_kind: str,
    clip_id: str,
    event_family: str,
    outcome: str,
    shot_subtype: str | None,
    teacher_confidence: float | None,
) -> str:
    key = "|".join(
        [
            source_kind,
            clip_id,
            event_family,
            outcome,
            shot_subtype or "null",
            f"{teacher_confidence or 0.0:.3f}",
        ]
    )
    bucket = _stable_bucket(key)
    if source_kind == "gold":
        return "val" if bucket < 0.5 else "test"
    if source_kind == "silver":
        if teacher_confidence is not None and teacher_confidence < 0.55:
            return "train"
        return "train" if bucket < 0.8 else ("val" if bucket < 0.9 else "test")
    if source_kind == "disagreement":
        return "train" if bucket < 0.75 else ("val" if bucket < 0.9 else "test")
    return "train"


def _weight_and_ignored(source_kind: str, teacher_confidence: float | None, video_missing: bool) -> tuple[float, bool]:
    confidence = float(teacher_confidence or 0.0)
    if source_kind == "gold":
        return (3.0 if confidence >= 0.0 else 2.5), False
    if source_kind == "silver":
        if confidence >= 0.85:
            return 1.0, False
        if confidence >= 0.65:
            return 0.6, False
        if confidence >= 0.5:
            return 0.35, False
        return 0.0, True
    if source_kind == "disagreement":
        if confidence >= 0.8:
            return 0.8, False
        if confidence >= 0.65:
            return 0.45, False
        return 0.2, video_missing
    return 1.0, False


def _resolve_source_path(repo_root: Path, source_ref: str | None) -> Path | None:
    if not source_ref:
        return None
    candidate = Path(source_ref)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    resolved = (repo_root / candidate).resolve()
    return resolved if resolved.exists() else None


def _ordered_labels(examples: Sequence[BasketballClipExample], field_name: str, *, fallback: Sequence[str]) -> tuple[str, ...]:
    if field_name == "event_family":
        labels = [example.event_family for example in examples]
    elif field_name == "outcome":
        labels = [example.outcome for example in examples]
    else:
        labels = []
    labels.extend(fallback)
    return tuple(_dedupe_preserve_order(labels))


def _dedupe_preserve_order(items: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _normalize_shot_subtype(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value).strip()
    if text.lower() in {"", "none", "null", "unknown"}:
        return "null"
    return text


def normalize_label(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_")
    if not text:
        return "unknown"
    return text


def _distribution(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _stable_bucket(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _softmax_with_temperature(logits: np.ndarray, temperature: float) -> np.ndarray:
    scaled = logits / max(temperature, 1e-3)
    shifted = scaled - np.max(scaled, axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    totals = np.sum(exponentials, axis=1, keepdims=True)
    return exponentials / np.maximum(totals, 1e-9)


def _negative_log_likelihood(probabilities: np.ndarray, label_indices: np.ndarray) -> float:
    chosen = probabilities[np.arange(len(probabilities)), label_indices]
    return float(-np.mean(np.log(np.clip(chosen, 1e-9, 1.0))))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path(__file__).resolve().parents[2]))
    except ValueError:
        return str(resolved)

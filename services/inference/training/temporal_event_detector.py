from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from services.inference.app.temporal_encoder import TemporalTargetModel
from services.inference.app.runtime_models.temporal_event_detector import (
    EVENT_FAMILIES,
    OUTCOMES,
    PROPOSAL_ACCEPT_LABELS,
    PROPOSAL_RANK_LABELS,
    PROPOSAL_REJECT_LABELS,
    SHOT_SUBTYPES,
    TEMPORAL_EVENT_DETECTOR_FEATURE_SCHEMA_VERSION,
    TEMPORAL_EVENT_DETECTOR_MODEL_VERSION,
    TEMPORAL_EVENT_DETECTOR_SCHEMA_VERSION,
    TemporalConvLayer,
    TemporalEventDetectorBundle,
    TemporalEventProposal,
    build_proposal_acceptor_feature_map,
    build_temporal_event_detector_feature_map,
    build_proposal_rejector_feature_map,
    default_temporal_event_detector_feature_names,
    vectorize_temporal_event_detector_observation,
    write_temporal_event_detector_bundle,
)
from services.inference.app.runtime_models.temporal_student import _summarize_other_bucket_signals
from services.inference.training.temporal_student import (
    TemporalStudentTrainingExample as TemporalTrainingExample,
    _export_target,
    load_temporal_student_examples,
)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ModuleNotFoundError:  # pragma: no cover
    torch = None
    nn = None
    F = None


DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED = 11


@dataclass(frozen=True)
class TemporalEventDetectorTrainingResult:
    bundle: TemporalEventDetectorBundle
    metrics: dict[str, Any]
    training_examples: int


if nn is not None:
    class TorchTemporalEventDetector(nn.Module):
        def __init__(self, input_size: int, hidden_size: int, architecture: str) -> None:
            super().__init__()
            self.architecture = architecture
            self.projection = nn.Linear(input_size, hidden_size)
            self.temporal_layers = nn.ModuleList()
            if architecture == "actionformer":
                self.temporal_layers.append(nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=1))
            elif architecture == "tridet":
                self.temporal_layers.append(nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=1))
                self.temporal_layers.append(nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=2, dilation=2))
            else:  # pragma: no cover - guarded by parse-time validation
                raise ValueError(f"Unsupported architecture: {architecture}")
            self.eventness_head = nn.Linear(hidden_size, 1)
            self.frame_family_head = nn.Linear(hidden_size, len(EVENT_FAMILIES))
            self.start_head = nn.Linear(hidden_size, 1)
            self.end_head = nn.Linear(hidden_size, 1)
            self.segment_attention = nn.Linear(hidden_size, 1)
            pooled_size = hidden_size * 4
            self.segment_family_head = nn.Linear(pooled_size, len(EVENT_FAMILIES))
            self.outcome_head = nn.Linear(pooled_size, len(OUTCOMES))
            self.shot_subtype_head = nn.Linear(pooled_size, len(SHOT_SUBTYPES))

        def forward(self, inputs: torch.Tensor, segment_mask: torch.Tensor) -> dict[str, torch.Tensor]:
            hidden = torch.tanh(self.projection(inputs))
            hidden_t = hidden.transpose(1, 2)
            if self.architecture == "actionformer":
                temporal_hidden = torch.tanh(self.temporal_layers[0](hidden_t)).transpose(1, 2)
            else:
                branches = [torch.tanh(layer(hidden_t)) for layer in self.temporal_layers]
                temporal_hidden = torch.tanh((hidden_t + sum(branches)) / float(len(branches) + 1)).transpose(1, 2)
            segment_mask = segment_mask.float()
            if segment_mask.dim() != 2:
                raise ValueError("Expected segment mask to have shape [batch, time].")
            expanded_mask = segment_mask.unsqueeze(-1)
            attention_logits = self.segment_attention(temporal_hidden).squeeze(-1)
            masked_attention_logits = attention_logits.masked_fill(segment_mask <= 0, -1e9)
            attention = torch.softmax(masked_attention_logits, dim=1)
            fallback_attention = torch.softmax(attention_logits, dim=1)
            use_fallback = (segment_mask.sum(dim=1, keepdim=True) <= 0).float()
            attention = (attention * (1.0 - use_fallback)) + (fallback_attention * use_fallback)
            weighted_mean = torch.sum(temporal_hidden * attention.unsqueeze(-1), dim=1)
            masked_hidden = temporal_hidden * expanded_mask
            pooled_max = torch.max(
                masked_hidden + ((1.0 - expanded_mask) * -1e9),
                dim=1,
            ).values
            pooled_max = torch.where(torch.isfinite(pooled_max), pooled_max, torch.max(temporal_hidden, dim=1).values)
            end_indices = torch.argmax(segment_mask, dim=1)
            has_segment = segment_mask.sum(dim=1) > 0
            end_indices = torch.where(has_segment, torch.argmax(torch.flip(segment_mask, dims=(1,)), dim=1), torch.full_like(end_indices, temporal_hidden.shape[1] - 1))
            end_indices = temporal_hidden.shape[1] - 1 - end_indices
            start_indices = torch.where(has_segment, torch.argmax(segment_mask, dim=1), torch.zeros_like(end_indices))
            batch_indices = torch.arange(temporal_hidden.shape[0], device=temporal_hidden.device)
            pooled_last = temporal_hidden[batch_indices, end_indices]
            pooled_first = temporal_hidden[batch_indices, start_indices]
            pooled_delta = pooled_last - pooled_first
            pooled = torch.cat([weighted_mean, pooled_max, pooled_last, pooled_delta], dim=-1)
            return {
                "hidden": temporal_hidden,
                "eventness": self.eventness_head(temporal_hidden).squeeze(-1),
                "frameFamily": self.frame_family_head(temporal_hidden),
                "start": self.start_head(temporal_hidden).squeeze(-1),
                "end": self.end_head(temporal_hidden).squeeze(-1),
                "segmentFamily": self.segment_family_head(pooled),
                "outcome": self.outcome_head(pooled),
                "shotSubtype": self.shot_subtype_head(pooled),
            }


    class TorchProposalRejector(nn.Module):
        def __init__(self, input_size: int) -> None:
            super().__init__()
            self.classifier = nn.Linear(input_size, len(PROPOSAL_REJECT_LABELS))

        def forward(self, inputs: torch.Tensor) -> torch.Tensor:
            return self.classifier(inputs)


    class TorchProposalRanker(nn.Module):
        def __init__(self, input_size: int) -> None:
            super().__init__()
            self.classifier = nn.Linear(input_size, len(PROPOSAL_RANK_LABELS))

        def forward(self, inputs: torch.Tensor) -> torch.Tensor:
            return self.classifier(inputs)


    class TorchProposalAcceptor(nn.Module):
        def __init__(self, input_size: int) -> None:
            super().__init__()
            self.classifier = nn.Linear(input_size, len(PROPOSAL_ACCEPT_LABELS))

        def forward(self, inputs: torch.Tensor) -> torch.Tensor:
            return self.classifier(inputs)


def load_temporal_event_detector_examples(repo_root: Path) -> list[TemporalTrainingExample]:
    return load_temporal_student_examples(repo_root)


def train_temporal_event_detector_from_repo(
    repo_root: Path,
    *,
    architecture: str,
    output_path: Path | None = None,
    hidden_size: int = 18,
    epochs: int = 180,
    learning_rate: float = 0.02,
) -> TemporalEventDetectorTrainingResult:
    examples = load_temporal_event_detector_examples(repo_root)
    result = train_temporal_event_detector(
        examples,
        architecture=architecture,
        hidden_size=hidden_size,
        epochs=epochs,
        learning_rate=learning_rate,
    )
    if output_path is not None:
        write_temporal_event_detector_bundle(output_path, result.bundle)
    return result


def train_temporal_event_detector(
    examples: Sequence[TemporalTrainingExample],
    *,
    architecture: str,
    hidden_size: int = 18,
    epochs: int = 180,
    learning_rate: float = 0.02,
    random_seed: int = DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED,
) -> TemporalEventDetectorTrainingResult:
    if torch is None or nn is None or F is None:  # pragma: no cover
        raise RuntimeError("torch is required to train the temporal event detector")
    if not examples:
        raise ValueError("At least one training example is required.")

    np.random.seed(int(random_seed))
    torch.manual_seed(int(random_seed))
    if torch.cuda.is_available():  # pragma: no cover
        torch.cuda.manual_seed_all(int(random_seed))

    input_feature_names = derive_temporal_event_detector_feature_names(examples)
    dataset = build_training_tensors(examples, input_feature_names=input_feature_names)
    model = TorchTemporalEventDetector(len(input_feature_names), hidden_size, architecture)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    for _ in range(epochs):
        optimizer.zero_grad()
        logits = model(dataset["inputs"], dataset["segmentMask"])
        loss = compute_detector_loss(logits=logits, dataset=dataset)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits = model(dataset["inputs"], dataset["segmentMask"])
        metrics = compute_training_metrics(logits=logits, dataset=dataset)
    bundle = export_temporal_event_detector_bundle(
        model=model,
        input_feature_names=input_feature_names,
        architecture=architecture,
        source_dataset="perception_supervision+phase4_event_localization_queue+teacher_backed",
    )
    bundle = train_proposal_rejector_bundle(bundle, examples)
    bundle = train_proposal_ranker_bundle(bundle, examples)
    bundle = train_proposal_acceptor_bundle(bundle, examples)
    bundle = calibrate_temporal_event_detector_bundle(bundle, examples)
    return TemporalEventDetectorTrainingResult(
        bundle=bundle,
        metrics=metrics,
        training_examples=len(examples),
    )


def derive_temporal_event_detector_feature_names(
    examples: Sequence[TemporalTrainingExample],
) -> tuple[str, ...]:
    feature_names = set(default_temporal_event_detector_feature_names())
    for example in examples:
        for observation in example.observations:
            feature_names.update(build_temporal_event_detector_feature_map(observation).keys())
    return tuple(sorted(feature_names))


def build_training_tensors(
    examples: Sequence[TemporalTrainingExample],
    *,
    input_feature_names: Sequence[str],
) -> dict[str, Any]:
    if torch is None:  # pragma: no cover
        raise RuntimeError("torch is required to build temporal event detector tensors")
    sequence_lengths = [len(example.observations) for example in examples]
    if len(set(sequence_lengths)) != 1:
        raise ValueError("Temporal event detector examples must use a fixed observation count.")
    inputs = torch.tensor(
        [
            [
                [
                    float(vectorize_temporal_event_detector_observation(observation, input_feature_names)[feature_index])
                    for feature_index in range(len(input_feature_names))
                ]
                for observation in example.observations
            ]
            for example in examples
        ],
        dtype=torch.float32,
    )
    frame_event_targets = []
    frame_family_targets = []
    start_indices = []
    end_indices = []
    center_indices = []
    segment_masks = []
    event_mask = []
    shot_mask = []
    localization_mask = []
    weights = []
    outcome_targets = []
    subtype_targets = []
    family_targets = []
    for example in examples:
        target = derive_frame_targets(example)
        frame_event_targets.append(target["frameEventTargets"])
        frame_family_targets.append(target["frameFamilyTargets"])
        start_indices.append(target["startIndex"])
        end_indices.append(target["endIndex"])
        center_indices.append(target["centerIndex"])
        segment_masks.append(target["segmentMask"])
        event_mask.append(1.0 if example.event_family != "other" else 0.0)
        shot_mask.append(1.0 if example.event_family == "shot_attempt" else 0.0)
        localization_mask.append(1.0 if example.has_event_localization else 0.0)
        weights.append(float(max(example.weight, 0.0)))
        family_targets.append(EVENT_FAMILIES.index(example.event_family))
        outcome_targets.append(OUTCOMES.index(example.outcome))
        subtype_targets.append(SHOT_SUBTYPES.index(example.shot_subtype or "null"))
    return {
        "inputs": inputs,
        "frameEventTargets": torch.tensor(frame_event_targets, dtype=torch.float32),
        "frameFamilyTargets": torch.tensor(frame_family_targets, dtype=torch.long),
        "startIndices": torch.tensor(start_indices, dtype=torch.long),
        "endIndices": torch.tensor(end_indices, dtype=torch.long),
        "centerIndices": torch.tensor(center_indices, dtype=torch.long),
        "segmentMask": torch.tensor(segment_masks, dtype=torch.float32),
        "weights": torch.tensor(weights, dtype=torch.float32),
        "eventMask": torch.tensor(event_mask, dtype=torch.float32),
        "shotMask": torch.tensor(shot_mask, dtype=torch.float32),
        "localizationMask": torch.tensor(localization_mask, dtype=torch.float32),
        "familyTargets": torch.tensor(family_targets, dtype=torch.long),
        "outcomeTargets": torch.tensor(outcome_targets, dtype=torch.long),
        "subtypeTargets": torch.tensor(subtype_targets, dtype=torch.long),
    }


def train_proposal_rejector_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
    *,
    epochs: int = 180,
    learning_rate: float = 0.03,
    random_seed: int = DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED + 5,
) -> TemporalEventDetectorBundle:
    if torch is None or nn is None or F is None:  # pragma: no cover
        raise RuntimeError("torch is required to train the proposal rejector")
    rows = build_proposal_rejector_rows(bundle, examples)
    train_rows = [row for row in rows if row["split"] == "train"]
    if not train_rows:
        train_rows = rows
    if len({str(row["label"]) for row in train_rows}) <= 1:
        return replace(
            bundle,
            proposal_rejector_feature_names=(),
            proposal_rejector=None,
        )
    feature_names = derive_proposal_rejector_feature_names(rows)
    if not feature_names:
        return bundle

    np.random.seed(int(random_seed))
    torch.manual_seed(int(random_seed))
    if torch.cuda.is_available():  # pragma: no cover
        torch.cuda.manual_seed_all(int(random_seed))

    inputs = torch.tensor(
        [
            [float(row["features"].get(name, 0.0)) for name in feature_names]
            for row in train_rows
        ],
        dtype=torch.float32,
    )
    targets = torch.tensor(
        [PROPOSAL_REJECT_LABELS.index(str(row["label"])) for row in train_rows],
        dtype=torch.long,
    )
    weights = torch.tensor([float(row["weight"]) for row in train_rows], dtype=torch.float32)
    model = TorchProposalRejector(len(feature_names))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    for _ in range(epochs):
        optimizer.zero_grad()
        logits = model(inputs)
        loss = compute_proposal_rejector_loss(logits=logits, targets=targets, weights=weights)
        loss.backward()
        optimizer.step()

    target_model = export_proposal_rejector_target(model)
    return replace(
        bundle,
        proposal_rejector_feature_names=feature_names,
        proposal_rejector=target_model,
    )


def train_proposal_ranker_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
    *,
    epochs: int = 180,
    learning_rate: float = 0.025,
    random_seed: int = DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED + 9,
) -> TemporalEventDetectorBundle:
    if torch is None or nn is None or F is None:  # pragma: no cover
        raise RuntimeError("torch is required to train the proposal ranker")
    rows = build_proposal_ranker_rows(bundle, examples)
    train_rows = [row for row in rows if row["split"] == "train"]
    if not train_rows:
        train_rows = rows
    labels = {str(row["label"]) for row in train_rows}
    if len(labels) <= 1:
        return replace(
            bundle,
            proposal_ranker_feature_names=(),
            proposal_ranker=None,
        )
    feature_names = derive_proposal_rejector_feature_names(rows)
    if not feature_names:
        return bundle

    np.random.seed(int(random_seed))
    torch.manual_seed(int(random_seed))
    if torch.cuda.is_available():  # pragma: no cover
        torch.cuda.manual_seed_all(int(random_seed))

    inputs = torch.tensor(
        [[float(row["features"].get(name, 0.0)) for name in feature_names] for row in train_rows],
        dtype=torch.float32,
    )
    targets = torch.tensor(
        [PROPOSAL_RANK_LABELS.index(str(row["label"])) for row in train_rows],
        dtype=torch.long,
    )
    weights = torch.tensor([float(row["weight"]) for row in train_rows], dtype=torch.float32)
    group_ids = [str(row["groupId"]) for row in train_rows]
    model = TorchProposalRanker(len(feature_names))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    for _ in range(epochs):
        optimizer.zero_grad()
        logits = model(inputs)
        loss = compute_proposal_ranker_loss(
            logits=logits,
            targets=targets,
            weights=weights,
            group_ids=group_ids,
        )
        loss.backward()
        optimizer.step()

    target_model = export_proposal_ranker_target(model)
    return replace(
        bundle,
        proposal_ranker_feature_names=feature_names,
        proposal_ranker=target_model,
    )


def train_proposal_acceptor_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
    *,
    epochs: int = 180,
    learning_rate: float = 0.02,
    random_seed: int = DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED + 13,
) -> TemporalEventDetectorBundle:
    if torch is None or nn is None or F is None:  # pragma: no cover
        raise RuntimeError("torch is required to train the proposal acceptor")
    rows = build_proposal_acceptor_rows(bundle, examples)
    train_rows = [row for row in rows if row["split"] == "train"]
    if not train_rows:
        train_rows = rows
    labels = {str(row["label"]) for row in train_rows}
    if len(labels) <= 1:
        return replace(
            bundle,
            proposal_acceptor_feature_names=(),
            proposal_acceptor=None,
        )
    feature_names = derive_proposal_acceptor_feature_names(rows)
    if not feature_names:
        return bundle

    np.random.seed(int(random_seed))
    torch.manual_seed(int(random_seed))
    if torch.cuda.is_available():  # pragma: no cover
        torch.cuda.manual_seed_all(int(random_seed))

    inputs = torch.tensor(
        [[float(row["features"].get(name, 0.0)) for name in feature_names] for row in train_rows],
        dtype=torch.float32,
    )
    targets = torch.tensor(
        [PROPOSAL_ACCEPT_LABELS.index(str(row["label"])) for row in train_rows],
        dtype=torch.long,
    )
    weights = torch.tensor([float(row["weight"]) for row in train_rows], dtype=torch.float32)
    model = TorchProposalAcceptor(len(feature_names))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    for _ in range(epochs):
        optimizer.zero_grad()
        logits = model(inputs)
        loss = compute_proposal_acceptor_loss(logits=logits, targets=targets, weights=weights)
        loss.backward()
        optimizer.step()

    target_model = export_proposal_acceptor_target(model)
    return replace(
        bundle,
        proposal_acceptor_feature_names=feature_names,
        proposal_acceptor=target_model,
    )


def build_proposal_rejector_rows(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example in examples:
        proposals, preferred_index, alignment_scores = build_candidate_proposal_alignment(bundle, example)
        for candidate_index, proposal in enumerate(proposals):
            label = infer_proposal_reject_label_for_candidate(
                example,
                proposal=proposal,
                candidate_index=candidate_index,
                preferred_index=preferred_index,
                alignment_score=alignment_scores[candidate_index],
            )
            rows.append(
                {
                    "clipId": example.clip_id,
                    "groupId": example.clip_id,
                    "split": example.split,
                    "sourceKind": example.source_kind,
                    "sourceDomain": example.source_domain,
                    "sourceSet": example.source_set,
                    "eventFamily": example.event_family,
                    "outcome": example.outcome,
                    "shotSubtype": example.shot_subtype,
                    "label": label,
                    "weight": proposal_reject_weight(example, label=label),
                    "features": build_proposal_rejector_feature_map(
                        observations=example.observations,
                        proposal=proposal,
                    ),
                }
            )
    return rows


def build_proposal_ranker_rows(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example in examples:
        proposals, preferred_index, alignment_scores = build_candidate_proposal_alignment(bundle, example)
        for candidate_index, proposal in enumerate(proposals):
            if example.event_family == "other":
                label = "secondary"
            elif preferred_index is not None and candidate_index == preferred_index and alignment_scores[candidate_index] >= 0.28:
                label = "primary"
            else:
                label = "secondary"
            rows.append(
                {
                    "clipId": example.clip_id,
                    "groupId": example.clip_id,
                    "split": example.split,
                    "label": label,
                    "weight": proposal_rank_weight(
                        example,
                        label=label,
                        alignment_score=alignment_scores[candidate_index],
                    ),
                    "features": build_proposal_rejector_feature_map(
                        observations=example.observations,
                        proposal=proposal,
                    ),
                }
            )
    return rows


def build_proposal_acceptor_rows(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example in examples:
        proposals, preferred_index, alignment_scores = build_candidate_proposal_alignment(bundle, example)
        for candidate_index, proposal in enumerate(proposals):
            rejector_prediction = bundle._predict_proposal_rejector(example.observations, proposal)
            ranker_prediction = bundle._predict_proposal_ranker(example.observations, proposal)
            label = infer_proposal_accept_label_for_candidate(
                example,
                candidate_index=candidate_index,
                preferred_index=preferred_index,
                alignment_score=alignment_scores[candidate_index],
            )
            rows.append(
                {
                    "clipId": example.clip_id,
                    "groupId": example.clip_id,
                    "split": example.split,
                    "label": label,
                    "weight": proposal_accept_weight(
                        example,
                        label=label,
                        alignment_score=alignment_scores[candidate_index],
                    ),
                    "features": build_proposal_acceptor_feature_map(
                        proposal=proposal,
                        rejector_prediction=rejector_prediction,
                        ranker_prediction=ranker_prediction,
                    ),
                }
            )
    return rows


def derive_proposal_rejector_feature_names(rows: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    feature_names: set[str] = set()
    for row in rows:
        feature_names.update(str(name) for name in (row.get("features") or {}).keys())
    return tuple(sorted(feature_names))


def compute_proposal_rejector_loss(*, logits: Any, targets: Any, weights: Any):
    base_loss = F.cross_entropy(logits, targets, reduction="none")
    probabilities = torch.softmax(logits, dim=-1)
    pt = probabilities[torch.arange(probabilities.shape[0]), targets]
    focal = torch.pow(1.0 - pt, 2.0)
    weighted = base_loss * focal * weights
    return weighted.sum() / torch.clamp(weights.sum(), min=1e-6)


def compute_proposal_ranker_loss(*, logits: Any, targets: Any, weights: Any, group_ids: Sequence[str]):
    base_loss = F.cross_entropy(logits, targets, reduction="none")
    probabilities = torch.softmax(logits, dim=-1)
    pt = probabilities[torch.arange(probabilities.shape[0]), targets]
    focal = torch.pow(1.0 - pt, 1.5)
    weighted_base = (base_loss * focal * weights).sum() / torch.clamp(weights.sum(), min=1e-6)
    ranking_logits = logits[:, PROPOSAL_RANK_LABELS.index("primary")] - logits[:, PROPOSAL_RANK_LABELS.index("secondary")]
    pair_losses: list[Any] = []
    for group_id in sorted(set(group_ids)):
        indices = [index for index, value in enumerate(group_ids) if value == group_id]
        positive_indices = [index for index in indices if int(targets[index].item()) == PROPOSAL_RANK_LABELS.index("primary")]
        negative_indices = [index for index in indices if int(targets[index].item()) != PROPOSAL_RANK_LABELS.index("primary")]
        if not positive_indices or not negative_indices:
            continue
        positive_scores = ranking_logits[positive_indices]
        negative_scores = ranking_logits[negative_indices]
        pair_weights = weights[positive_indices].unsqueeze(1) * weights[negative_indices].unsqueeze(0)
        pair_loss = -F.logsigmoid(positive_scores.unsqueeze(1) - negative_scores.unsqueeze(0))
        pair_losses.append((pair_loss * pair_weights).sum() / torch.clamp(pair_weights.sum(), min=1e-6))
    if not pair_losses:
        return weighted_base
    return weighted_base + (0.45 * torch.stack(pair_losses).mean())


def derive_proposal_acceptor_feature_names(rows: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    feature_names: set[str] = set()
    for row in rows:
        features = row.get("features")
        if isinstance(features, dict):
            feature_names.update(str(name) for name in features.keys())
    return tuple(sorted(feature_names))


def compute_proposal_acceptor_loss(*, logits: Any, targets: Any, weights: Any):
    loss = F.cross_entropy(logits, targets, reduction="none")
    probabilities = torch.softmax(logits, dim=-1)
    pt = probabilities[torch.arange(probabilities.shape[0]), targets]
    focal = torch.pow(1.0 - pt, 1.75)
    weighted = loss * focal * weights
    return weighted.sum() / torch.clamp(weights.sum(), min=1e-6)


def export_proposal_rejector_target(model: Any) -> TemporalTargetModel:
    return TemporalTargetModel(
        name="proposalRejector",
        classes=tuple(PROPOSAL_REJECT_LABELS),
        weight=tuple(
            tuple(float(value) for value in row)
            for row in model.classifier.weight.detach().cpu().numpy().tolist()
        ),
        bias=tuple(float(value) for value in model.classifier.bias.detach().cpu().numpy().tolist()),
        temperature=1.0,
        uncertainty_threshold=0.5,
        margin_threshold=0.08,
        top_k=3,
    )


def export_proposal_ranker_target(model: Any) -> TemporalTargetModel:
    return TemporalTargetModel(
        name="proposalRanker",
        classes=tuple(PROPOSAL_RANK_LABELS),
        weight=tuple(
            tuple(float(value) for value in row)
            for row in model.classifier.weight.detach().cpu().numpy().tolist()
        ),
        bias=tuple(float(value) for value in model.classifier.bias.detach().cpu().numpy().tolist()),
        temperature=1.0,
        uncertainty_threshold=0.56,
        margin_threshold=0.06,
        top_k=2,
    )


def export_proposal_acceptor_target(model: Any) -> TemporalTargetModel:
    return TemporalTargetModel(
        name="proposalAcceptor",
        classes=tuple(PROPOSAL_ACCEPT_LABELS),
        weight=tuple(
            tuple(float(value) for value in row)
            for row in model.classifier.weight.detach().cpu().numpy().tolist()
        ),
        bias=tuple(float(value) for value in model.classifier.bias.detach().cpu().numpy().tolist()),
        temperature=1.0,
        uncertainty_threshold=0.58,
        margin_threshold=0.06,
        top_k=2,
    )


def build_candidate_proposal_alignment(
    bundle: TemporalEventDetectorBundle,
    example: TemporalTrainingExample,
) -> tuple[list[Any], int | None, list[float]]:
    proposals = bundle.propose_candidates(
        example.observations,
        max_candidates=max(int(bundle.proposal_candidate_limit), 4),
    )
    if example.event_family == "other":
        return proposals, None, [0.0 for _ in proposals]
    target_indices = derive_frame_targets(example)
    start_index = int(target_indices["startIndex"])
    end_index = int(target_indices["endIndex"])
    center_index = int(target_indices["centerIndex"])
    alignment_scores = [
        proposal_alignment_score(
            proposal=proposal,
            gold_start_index=start_index,
            gold_end_index=end_index,
            gold_center_index=center_index,
            sequence_length=len(example.observations),
        )
        for proposal in proposals
    ]
    if not alignment_scores:
        return proposals, None, []
    preferred_index = int(max(range(len(alignment_scores)), key=lambda index: alignment_scores[index]))
    if alignment_scores[preferred_index] < 0.18:
        preferred_index = None
    return proposals, preferred_index, alignment_scores


def proposal_alignment_score(
    *,
    proposal: Any,
    gold_start_index: int,
    gold_end_index: int,
    gold_center_index: int,
    sequence_length: int,
) -> float:
    proposal_start = int(proposal.start_index)
    proposal_end = int(proposal.end_index)
    intersection = max(min(proposal_end, gold_end_index) - max(proposal_start, gold_start_index) + 1, 0)
    union = max(max(proposal_end, gold_end_index) - min(proposal_start, gold_start_index) + 1, 1)
    iou = float(intersection) / float(union)
    center_distance = abs(int(proposal.center_index) - int(gold_center_index)) / max(sequence_length - 1, 1)
    center_score = max(1.0 - center_distance, 0.0)
    return round((0.7 * iou) + (0.3 * center_score), 4)


def infer_proposal_reject_label_for_candidate(
    example: TemporalTrainingExample,
    *,
    proposal: Any,
    candidate_index: int,
    preferred_index: int | None,
    alignment_score: float,
) -> str:
    if example.event_family == "other":
        return infer_proposal_reject_label(example)
    if preferred_index is not None and candidate_index == preferred_index and alignment_score >= 0.28:
        return "real_event"
    if alignment_score >= 0.2:
        return "ambiguous"
    if preferred_index is not None and alignment_score < 0.08:
        return "non_event"
    if proposal.spotter_ranking_score >= 0.34 or proposal.event_score >= 0.46 or proposal.coarse_event_family != "other":
        return "ambiguous"
    return "non_event"


def infer_proposal_reject_label(example: TemporalTrainingExample) -> str:
    if example.event_family != "other":
        return "real_event"
    text = " ".join(
        item
        for item in (
            example.clip_id,
            example.source_domain,
            example.source_set,
            getattr(example, "reviewer_notes", ""),
        )
        if item
    ).lower()
    if any(token in text for token in ("dead_ball", "dead-ball", "dead ball")):
        return "dead_ball"
    if any(token in text for token in ("replay", "celebration", "reaction")):
        return "replay_or_reaction"
    if any(token in text for token in ("inbound", "setup", "halfcourt", "half-court")):
        return "setup"
    if any(
        token in text
        for token in (
            "camera_pan",
            "camera-pan",
            "camera pan",
            "dribble_only",
            "dribble-only",
            "dribble only",
            "non_event",
            "non-event",
            "non event",
        )
    ):
        return "non_event"
    signal_summary = _summarize_other_bucket_signals(example.observations)
    shot_signal = max(
        signal_summary["shot_release_candidate"],
        signal_summary["ball_near_rim"],
        signal_summary["ball_through_hoop_likelihood"],
        signal_summary["ball_above_rim"],
        signal_summary["ball_arc_apex"],
    )
    transition_signal = max(
        signal_summary["transition_likelihood"],
        signal_summary["transition_speed_score"],
        signal_summary["possession_change_likelihood"],
        signal_summary["ball_carrier_speed"],
    )
    setup_context = min(
        1.0,
        max(signal_summary["hoop_visible"], signal_summary["ball_visible"] * 0.4)
        * max(signal_summary["tracked_player_presence"], signal_summary["tracking_continuity"], 0.15),
    )
    reaction_sparse = min(
        max(1.0 - signal_summary["ball_visible"], 0.0),
        max(1.0 - signal_summary["hoop_visible"], 0.0),
        max(1.0 - max(signal_summary["detection_density"], signal_summary["tracking_density"]), 0.0),
    )
    if reaction_sparse >= 0.72 and signal_summary["tracking_continuity"] < 0.25:
        return "replay_or_reaction"
    if setup_context >= 0.38 and shot_signal < 0.22 and transition_signal < 0.24:
        return "setup"
    if (
        max(signal_summary["hoop_visible"], signal_summary["tracked_player_presence"]) >= 0.34
        and shot_signal < 0.18
        and transition_signal < 0.18
        and signal_summary["possession_change_likelihood"] < 0.2
    ):
        return "dead_ball"
    if (
        max(signal_summary["detection_density"], signal_summary["tracking_density"]) < 0.18
        and signal_summary["ball_visible"] < 0.2
        and signal_summary["hoop_visible"] < 0.24
    ):
        return "non_event"
    return "ambiguous"


def proposal_reject_weight(example: TemporalTrainingExample, *, label: str | None = None) -> float:
    weight = max(float(example.weight), 0.0)
    label = label or infer_proposal_reject_label(example)
    text = " ".join(
        item
        for item in (
            example.clip_id,
            example.source_domain,
            example.source_set,
            getattr(example, "reviewer_notes", ""),
        )
        if item
    ).lower()
    if label != "real_event":
        weight *= 1.45
    if label in {"dead_ball", "setup", "replay_or_reaction"}:
        weight *= 1.3
    if label == "non_event" and any(
        token in text
        for token in ("camera_pan", "camera-pan", "camera pan", "dribble_only", "dribble-only", "dribble only")
    ):
        weight *= 1.2
    if example.source_kind == "disagreement":
        weight *= 1.2
    if example.source_domain in {"manual_negative", "hard_negative"} and label != "real_event":
        weight *= 1.25
    if example.has_event_localization and example.event_family != "other":
        weight *= 1.1
    return round(weight, 4)


def infer_proposal_accept_label_for_candidate(
    example: TemporalTrainingExample,
    *,
    candidate_index: int,
    preferred_index: int | None,
    alignment_score: float,
) -> str:
    if example.event_family == "other":
        return "reject"
    if preferred_index is not None and candidate_index == preferred_index and alignment_score >= 0.28:
        return "accept"
    return "reject"


def proposal_rank_weight(
    example: TemporalTrainingExample,
    *,
    label: str,
    alignment_score: float,
) -> float:
    weight = max(float(example.weight), 0.0)
    if label == "primary":
        weight *= 1.3
    else:
        weight *= 1.05
    if example.event_family == "other":
        weight *= 1.15
    if example.source_kind == "disagreement":
        weight *= 1.1
    if example.source_domain in {"manual_negative", "hard_negative"}:
        weight *= 1.1
    if alignment_score < 0.18 and example.event_family != "other":
        weight *= 1.1
    return round(weight, 4)


def proposal_accept_weight(
    example: TemporalTrainingExample,
    *,
    label: str,
    alignment_score: float,
) -> float:
    weight = max(float(example.weight), 0.0)
    if label == "accept":
        weight *= 1.3
    else:
        weight *= 1.15
    if example.event_family == "other":
        weight *= 1.2
    if example.source_kind == "disagreement":
        weight *= 1.1
    if example.source_domain in {"manual_negative", "hard_negative"}:
        weight *= 1.2
    if alignment_score < 0.12 and example.event_family != "other":
        weight *= 1.15
    return round(weight, 4)


def derive_frame_targets(example: TemporalTrainingExample) -> dict[str, Any]:
    timestamps = [float(observation.timestamp_seconds) for observation in example.observations]
    runtime = example.observations[0].runtime_features if example.observations else {}
    center_time = _resolve_time(
        runtime.get("eventCenterSeconds"),
        default=timestamps[len(timestamps) // 2],
    )
    start_time = _resolve_time(runtime.get("eventStartSeconds"), default=center_time)
    end_time = _resolve_time(runtime.get("eventEndSeconds"), default=center_time)
    if example.event_family != "other" and end_time < start_time:
        end_time = start_time
    if example.event_family != "other" and not example.has_event_localization:
        half_step = _median_step(timestamps) / 2.0
        start_time = max(center_time - half_step, timestamps[0])
        end_time = min(center_time + half_step, timestamps[-1])
    center_index = _closest_index(timestamps, center_time)
    start_index = _closest_index(timestamps, start_time)
    end_index = _closest_index(timestamps, end_time)
    if end_index < start_index:
        end_index = start_index
    segment_mask = [0.0 for _ in timestamps]
    frame_event_targets = [0.0 for _ in timestamps]
    frame_family_targets = [EVENT_FAMILIES.index("other") for _ in timestamps]
    if example.event_family != "other":
        for index in range(start_index, end_index + 1):
            segment_mask[index] = 1.0
            frame_event_targets[index] = 1.0
            frame_family_targets[index] = EVENT_FAMILIES.index(example.event_family)
        frame_event_targets[center_index] = 1.0
        frame_family_targets[center_index] = EVENT_FAMILIES.index(example.event_family)
    return {
        "frameEventTargets": frame_event_targets,
        "frameFamilyTargets": frame_family_targets,
        "startIndex": start_index,
        "endIndex": end_index,
        "centerIndex": center_index,
        "segmentMask": segment_mask,
    }


def compute_detector_loss(*, logits: dict[str, Any], dataset: dict[str, Any]):
    eventness_loss = F.binary_cross_entropy_with_logits(
        logits["eventness"],
        dataset["frameEventTargets"],
        reduction="none",
    )
    family_loss = F.cross_entropy(
        logits["frameFamily"].transpose(1, 2),
        dataset["frameFamilyTargets"],
        reduction="none",
    )
    pooled_family_loss = F.cross_entropy(logits["segmentFamily"], dataset["familyTargets"], reduction="none")
    outcome_loss = F.cross_entropy(logits["outcome"], dataset["outcomeTargets"], reduction="none")
    subtype_loss = F.cross_entropy(logits["shotSubtype"], dataset["subtypeTargets"], reduction="none")
    start_loss = F.cross_entropy(logits["start"], dataset["startIndices"], reduction="none")
    end_loss = F.cross_entropy(logits["end"], dataset["endIndices"], reduction="none")

    weights = dataset["weights"]
    event_mask = dataset["eventMask"]
    shot_mask = dataset["shotMask"]
    localization_mask = dataset["localizationMask"]
    negative_mask = 1.0 - event_mask
    frame_weights = weights.unsqueeze(1) * (1.15 + (0.45 * negative_mask.unsqueeze(1)) + (0.2 * localization_mask.unsqueeze(1)))
    frame_family_weights = weights.unsqueeze(1) * (1.0 + (0.25 * event_mask.unsqueeze(1)))
    eventness_loss = _focalize(eventness_loss, logits["eventness"], dataset["frameEventTargets"], gamma=2.0)
    weighted_eventness = (eventness_loss * frame_weights).sum() / torch.clamp(frame_weights.sum(), min=1e-6)
    weighted_frame_family = (family_loss * frame_family_weights).sum() / torch.clamp(frame_family_weights.sum(), min=1e-6)
    family_weights = weights * (1.0 + (0.25 * event_mask) + (0.15 * localization_mask))
    weighted_pooled_family = (pooled_family_loss * family_weights).sum() / torch.clamp(family_weights.sum(), min=1e-6)
    outcome_weights = weights * event_mask
    weighted_outcome = (outcome_loss * outcome_weights).sum() / torch.clamp(outcome_weights.sum(), min=1e-6)
    subtype_weights = weights * shot_mask
    weighted_subtype = (subtype_loss * subtype_weights).sum() / torch.clamp(subtype_weights.sum(), min=1e-6)
    boundary_weights = weights * event_mask * (1.0 + (0.5 * localization_mask))
    weighted_start = (start_loss * boundary_weights).sum() / torch.clamp(boundary_weights.sum(), min=1e-6)
    weighted_end = (end_loss * boundary_weights).sum() / torch.clamp(boundary_weights.sum(), min=1e-6)
    return (
        weighted_eventness
        + weighted_frame_family
        + weighted_pooled_family
        + weighted_outcome
        + weighted_subtype
        + (0.35 * weighted_start)
        + (0.35 * weighted_end)
    )


def _focalize(base_loss, logits, targets, *, gamma: float):
    probabilities = torch.sigmoid(logits)
    pt = torch.where(targets > 0.5, probabilities, 1.0 - probabilities)
    modulation = torch.pow(1.0 - pt, gamma)
    return base_loss * modulation


def compute_training_metrics(*, logits: dict[str, Any], dataset: dict[str, Any]) -> dict[str, Any]:
    frame_event_predictions = (torch.sigmoid(logits["eventness"]) >= 0.5).float()
    frame_family_predictions = torch.argmax(logits["frameFamily"], dim=-1)
    family_predictions = torch.argmax(logits["segmentFamily"], dim=-1)
    outcome_predictions = torch.argmax(logits["outcome"], dim=-1)
    subtype_predictions = torch.argmax(logits["shotSubtype"], dim=-1)
    metrics = {
        "frameEventAccuracy": round(float((frame_event_predictions == dataset["frameEventTargets"]).float().mean().item()), 4),
        "frameFamilyAccuracy": round(float((frame_family_predictions == dataset["frameFamilyTargets"]).float().mean().item()), 4),
        "segmentFamilyAccuracy": round(float((family_predictions == dataset["familyTargets"]).float().mean().item()), 4),
        "outcomeAccuracy": round(float((outcome_predictions == dataset["outcomeTargets"]).float().mean().item()), 4),
        "shotSubtypeAccuracy": round(float((subtype_predictions == dataset["subtypeTargets"]).float().mean().item()), 4),
    }
    return metrics


def evaluate_temporal_event_detector_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> dict[str, Any]:
    evaluation_examples = [
        example
        for example in examples
        if example.source_kind == "gold" and example.split in {"val", "test"}
    ]
    if not evaluation_examples:
        evaluation_examples = [example for example in examples if example.source_kind == "gold"] or list(examples)

    rows: list[dict[str, Any]] = []
    for example in evaluation_examples:
        prediction = bundle.predict(example.observations)
        metadata = prediction.metadata or {}
        proposal_accepted = bool(
            metadata.get("temporal_event_detector_proposal_accepted")
            if "temporal_event_detector_proposal_accepted" in metadata
            else metadata.get("temporal_event_detector_gate_open")
        )
        proposal_score = float(
            metadata.get("temporal_event_detector_proposal_acceptance_score")
            or metadata.get("temporal_event_detector_event_score")
            or 0.0
        )
        rejector_label = str(
            metadata.get("temporal_event_detector_proposal_rejector_label")
            or "null"
        )
        acceptor_label = str(
            metadata.get("temporal_event_detector_proposal_acceptor_label")
            or "null"
        )
        predicted_spotter_family = str(
            metadata.get("temporal_event_detector_event_family")
            or metadata.get("temporal_student_event_spotter_family")
            or prediction.eventFamily
            or "other"
        )
        rows.append(
            {
                "clipId": example.clip_id,
                "expectedEventFamily": example.event_family,
                "expectedOutcome": example.outcome,
                "expectedShotSubtype": example.shot_subtype or "null",
                "predictedSpotterFamily": predicted_spotter_family,
                "predictedSpotterLikelyEvent": bool(
                    metadata.get("temporal_event_detector_gate_open")
                    if "temporal_event_detector_gate_open" in metadata
                    else metadata.get("temporal_student_event_spotter_likely_event")
                ),
                "predictedEventFamily": prediction.eventFamily or "other",
                "predictedOutcome": prediction.outcome or "uncertain",
                "predictedShotSubtype": prediction.shotSubtype or "null",
                "predictedDisplayLabel": prediction.label,
                "isUncertain": bool(prediction.isUncertain),
                "hasEventLocalization": bool(example.has_event_localization),
                "proposalAccepted": proposal_accepted,
                "proposalScore": round(proposal_score, 4),
                "proposalRejectorLabel": rejector_label,
                "proposalAcceptorLabel": acceptor_label,
            }
        )
    total = max(len(rows), 1)
    event_family_accuracy = round(
        sum(1 for row in rows if row["expectedEventFamily"] == row["predictedEventFamily"]) / total,
        4,
    )
    outcome_accuracy = round(
        sum(1 for row in rows if row["expectedOutcome"] == row["predictedOutcome"]) / total,
        4,
    )
    subtype_rows = [row for row in rows if row["expectedEventFamily"] == "shot_attempt"]
    subtype_total = max(len(subtype_rows), 1)
    shot_subtype_accuracy = round(
        sum(1 for row in subtype_rows if row["expectedShotSubtype"] == row["predictedShotSubtype"]) / subtype_total,
        4,
    )
    uncertainty_rate = round(sum(1 for row in rows if row["isUncertain"]) / total, 4)
    flat_label_distribution = dict(sorted(Counter(row["predictedDisplayLabel"] for row in rows).items()))
    event_family_distribution = dict(sorted(Counter(row["predictedEventFamily"] for row in rows).items()))
    outcome_distribution = dict(sorted(Counter(row["predictedOutcome"] for row in rows).items()))
    subtype_distribution = dict(sorted(Counter(row["predictedShotSubtype"] for row in rows).items()))
    highlight_dominance = round(flat_label_distribution.get("Highlight", 0) / total, 4)
    other_dominance = round(event_family_distribution.get("other", 0) / total, 4)
    miss_vs_made_confusion = sum(
        1
        for row in rows
        if row["expectedOutcome"] == "missed" and row["predictedDisplayLabel"] == "Made Shot"
    )
    labeled_rows = [row for row in rows if row["expectedEventFamily"] in EVENT_FAMILIES]
    true_positive = sum(
        1
        for row in labeled_rows
        if row["expectedEventFamily"] != "other" and row["predictedSpotterFamily"] != "other"
    )
    false_positive = sum(
        1
        for row in labeled_rows
        if row["expectedEventFamily"] == "other" and row["predictedSpotterFamily"] != "other"
    )
    false_negative = sum(
        1
        for row in labeled_rows
        if row["expectedEventFamily"] != "other" and row["predictedSpotterFamily"] == "other"
    )
    event_detection_precision = round(true_positive / max(true_positive + false_positive, 1), 4)
    event_detection_recall = round(true_positive / max(true_positive + false_negative, 1), 4)
    other_examples = [row for row in rows if row["predictedEventFamily"] == "other"]
    true_missed_events_in_other = sum(1 for row in other_examples if row["expectedEventFamily"] != "other")
    proposal_acceptance_rate = round(
        sum(1 for row in rows if row["proposalAccepted"]) / total,
        4,
    )
    eventness_brier = round(
        sum(
            (float(row["proposalScore"]) - (1.0 if row["expectedEventFamily"] != "other" else 0.0)) ** 2
            for row in rows
        )
        / total,
        4,
    )
    accepted_shot_rows = [
        row
        for row in rows
        if row["proposalAccepted"] and row["expectedEventFamily"] == "shot_attempt"
    ]
    accepted_shot_total = len(accepted_shot_rows)
    accepted_shot_outcome_accuracy = (
        round(
            sum(1 for row in accepted_shot_rows if row["expectedOutcome"] == row["predictedOutcome"])
            / accepted_shot_total,
            4,
        )
        if accepted_shot_rows
        else None
    )
    rejected_rows = [row for row in rows if not row["proposalAccepted"]]
    rejected_true_negative = sum(1 for row in rejected_rows if row["expectedEventFamily"] == "other")
    rejected_true_miss = sum(1 for row in rejected_rows if row["expectedEventFamily"] != "other")
    return {
        "eventFamilyAccuracy": event_family_accuracy,
        "outcomeAccuracy": outcome_accuracy,
        "shotSubtypeAccuracy": shot_subtype_accuracy,
        "uncertaintyRate": uncertainty_rate,
        "proposalAcceptanceRate": proposal_acceptance_rate,
        "eventnessBrier": eventness_brier,
        "acceptedShotProposalOutcomeAccuracy": accepted_shot_outcome_accuracy,
        "flatLabelSpread": len(flat_label_distribution),
        "flatLabelDistribution": flat_label_distribution,
        "eventFamilyDistribution": event_family_distribution,
        "outcomeDistribution": outcome_distribution,
        "shotSubtypeDistribution": subtype_distribution,
        "highlightDominance": highlight_dominance,
        "otherDominance": other_dominance,
        "missVsMadeConfusion": miss_vs_made_confusion,
        "eventSpotterPrecision": event_detection_precision,
        "eventSpotterRecall": event_detection_recall,
        "eventDetectionPrecision": event_detection_precision,
        "eventDetectionRecall": event_detection_recall,
        "eventDetectionLabeledRows": len(labeled_rows),
        "predictedOtherTrueMissRate": round(true_missed_events_in_other / max(len(other_examples), 1), 4),
        "rejectedProposalTrueNegativeRate": round(rejected_true_negative / max(len(rejected_rows), 1), 4) if rejected_rows else None,
        "rejectedProposalTrueMissRate": round(rejected_true_miss / max(len(rejected_rows), 1), 4) if rejected_rows else None,
        "evaluationRows": rows,
    }


def calibrate_temporal_event_detector_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> TemporalEventDetectorBundle:
    calibration_examples = [
        example
        for example in examples
        if example.source_kind == "gold" and example.split in {"val", "test"}
    ]
    if not calibration_examples:
        return bundle
    if len(calibration_examples) < 6:
        return bundle
    best_bundle = _calibrate_proposal_rejector(bundle, calibration_examples)
    best_bundle = _calibrate_proposal_ranker(best_bundle, calibration_examples)
    best_bundle = _calibrate_proposal_acceptor(best_bundle, calibration_examples)
    best_bundle = _calibrate_outcome_target(best_bundle, calibration_examples)
    best_metrics = evaluate_temporal_event_detector_bundle(best_bundle, calibration_examples)
    best_score = candidate_score(best_metrics)
    calibrated_base = best_bundle
    for threshold in (0.22, 0.28, 0.34):
        for margin in (0.03, 0.05, 0.07):
            for eventness_temperature in (0.95, 1.1, 1.25):
                for acceptance_threshold in (0.56, 0.62, 0.68):
                    for competition_margin in (0.04, 0.06, 0.09):
                        candidate_bundle = replace(
                            calibrated_base,
                            event_score_threshold=float(threshold),
                            event_margin_threshold=float(margin),
                            eventness_temperature=float(eventness_temperature),
                            proposal_acceptance_threshold=float(acceptance_threshold),
                            proposal_competition_margin_threshold=float(competition_margin),
                        )
                        metrics = evaluate_temporal_event_detector_bundle(candidate_bundle, calibration_examples)
                        score = candidate_score(metrics)
                        if score > best_score:
                            best_bundle = candidate_bundle
                            best_metrics = metrics
                            best_score = score
    best_bundle = train_proposal_rejector_bundle(best_bundle, examples)
    best_bundle = train_proposal_ranker_bundle(best_bundle, examples)
    best_bundle = train_proposal_acceptor_bundle(best_bundle, examples)
    best_bundle = _calibrate_proposal_rejector(best_bundle, calibration_examples)
    best_bundle = _calibrate_proposal_ranker(best_bundle, calibration_examples)
    best_bundle = _calibrate_proposal_acceptor(best_bundle, calibration_examples)
    best_bundle = _calibrate_outcome_target(best_bundle, calibration_examples)
    return best_bundle


def _calibrate_proposal_rejector(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> TemporalEventDetectorBundle:
    if bundle.proposal_rejector is None:
        return bundle
    best_bundle = bundle
    best_metrics = evaluate_temporal_event_detector_bundle(bundle, examples)
    best_score = candidate_score(best_metrics)
    for temperature in (0.9, 1.1, 1.3):
        for uncertainty in (0.46, 0.52, 0.58):
            for margin in (0.05, 0.08, 0.11):
                candidate_rejector = replace(
                    bundle.proposal_rejector,
                    temperature=float(temperature),
                    uncertainty_threshold=float(uncertainty),
                    margin_threshold=float(margin),
                )
                candidate_bundle = replace(bundle, proposal_rejector=candidate_rejector)
                metrics = evaluate_temporal_event_detector_bundle(candidate_bundle, examples)
                score = candidate_score(metrics)
                if score > best_score:
                    best_bundle = candidate_bundle
                    best_metrics = metrics
                    best_score = score
    return best_bundle


def _calibrate_proposal_ranker(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> TemporalEventDetectorBundle:
    if bundle.proposal_ranker is None:
        return bundle
    best_bundle = bundle
    best_score = candidate_score(evaluate_temporal_event_detector_bundle(bundle, examples))
    for temperature in (0.9, 1.05, 1.2):
        for uncertainty in (0.48, 0.56, 0.62):
            for margin in (0.04, 0.06, 0.09):
                candidate_ranker = replace(
                    bundle.proposal_ranker,
                    temperature=float(temperature),
                    uncertainty_threshold=float(uncertainty),
                    margin_threshold=float(margin),
                )
                candidate_bundle = replace(bundle, proposal_ranker=candidate_ranker)
                score = candidate_score(evaluate_temporal_event_detector_bundle(candidate_bundle, examples))
                if score > best_score:
                    best_bundle = candidate_bundle
                    best_score = score
    return best_bundle


def _calibrate_proposal_acceptor(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> TemporalEventDetectorBundle:
    if bundle.proposal_acceptor is None:
        return bundle
    best_bundle = bundle
    best_score = candidate_score(evaluate_temporal_event_detector_bundle(bundle, examples))
    for temperature in (0.9, 1.05, 1.2):
        for uncertainty in (0.52, 0.58, 0.64):
            for margin in (0.04, 0.06, 0.09):
                candidate_acceptor = replace(
                    bundle.proposal_acceptor,
                    temperature=float(temperature),
                    uncertainty_threshold=float(uncertainty),
                    margin_threshold=float(margin),
                )
                candidate_bundle = replace(bundle, proposal_acceptor=candidate_acceptor)
                score = candidate_score(evaluate_temporal_event_detector_bundle(candidate_bundle, examples))
                if score > best_score:
                    best_bundle = candidate_bundle
                    best_score = score
    return best_bundle


def _calibrate_outcome_target(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> TemporalEventDetectorBundle:
    outcome_target = bundle.targets.get("outcome")
    if outcome_target is None:
        return bundle
    best_bundle = bundle
    best_score = candidate_score(evaluate_temporal_event_detector_bundle(bundle, examples))
    for temperature in (0.9, 1.05, 1.2):
        for uncertainty in (0.42, 0.48, 0.54):
            for margin in (0.05, 0.08):
                candidate_target = replace(
                    outcome_target,
                    temperature=float(temperature),
                    uncertainty_threshold=float(uncertainty),
                    margin_threshold=float(margin),
                )
                candidate_targets = dict(bundle.targets)
                candidate_targets["outcome"] = candidate_target
                candidate_bundle = replace(bundle, targets=candidate_targets)
                score = candidate_score(evaluate_temporal_event_detector_bundle(candidate_bundle, examples))
                if score > best_score:
                    best_bundle = candidate_bundle
                    best_score = score
    return best_bundle


def export_temporal_event_detector_bundle(
    *,
    model,
    input_feature_names: Sequence[str],
    architecture: str,
    source_dataset: str,
) -> TemporalEventDetectorBundle:
    projection_weight = tuple(tuple(float(value) for value in row) for row in model.projection.weight.detach().cpu().numpy().tolist())
    projection_bias = tuple(float(value) for value in model.projection.bias.detach().cpu().numpy().tolist())
    temporal_layers = tuple(
        TemporalConvLayer(
            weight=tuple(
                tuple(tuple(float(value) for value in kernel) for kernel in channel)
                for channel in layer.weight.detach().cpu().numpy().tolist()
            ),
            bias=tuple(float(value) for value in layer.bias.detach().cpu().numpy().tolist()),
            dilation=int(layer.dilation[0]),
        )
        for layer in model.temporal_layers
    )
    return TemporalEventDetectorBundle(
        schema_version=TEMPORAL_EVENT_DETECTOR_SCHEMA_VERSION,
        feature_schema_version=TEMPORAL_EVENT_DETECTOR_FEATURE_SCHEMA_VERSION,
        model_version=(
            TEMPORAL_EVENT_DETECTOR_MODEL_VERSION
            if architecture == "tridet"
            else f"temporal-event-detector-{architecture}-open-set-v1"
        ),
        detector_family=architecture,
        trained_at=datetime.now(timezone.utc).isoformat(),
        source_dataset=source_dataset,
        notes=(
            f"{architecture} temporal detector over structured basketball signals, perception features, and clip-runtime cues.",
            "TriDet is used as a proposal stage only; it does not emit final flat labels directly.",
            "A proposal verifier and ranker gate classification so weak adjacent proposals do not outrank true events.",
            "Open-set calibration is applied before outcome/subtype heads run.",
        ),
        input_feature_names=tuple(input_feature_names),
        hidden_size=int(model.projection.out_features),
        projection_weight=projection_weight,
        projection_bias=projection_bias,
        temporal_layers=temporal_layers,
        segment_attention_weight=tuple(float(value) for value in model.segment_attention.weight.detach().cpu().numpy()[0].tolist()),
        segment_attention_bias=float(model.segment_attention.bias.detach().cpu().numpy()[0]),
        eventness_weight=tuple(float(value) for value in model.eventness_head.weight.detach().cpu().numpy()[0].tolist()),
        eventness_bias=float(model.eventness_head.bias.detach().cpu().numpy()[0]),
        frame_family_weight=tuple(
            tuple(float(value) for value in row)
            for row in model.frame_family_head.weight.detach().cpu().numpy().tolist()
        ),
        frame_family_bias=tuple(float(value) for value in model.frame_family_head.bias.detach().cpu().numpy().tolist()),
        start_weight=tuple(float(value) for value in model.start_head.weight.detach().cpu().numpy()[0].tolist()),
        start_bias=float(model.start_head.bias.detach().cpu().numpy()[0]),
        end_weight=tuple(float(value) for value in model.end_head.weight.detach().cpu().numpy()[0].tolist()),
        end_bias=float(model.end_head.bias.detach().cpu().numpy()[0]),
        event_score_threshold=0.32 if architecture == "actionformer" else 0.3,
        event_margin_threshold=0.045 if architecture == "actionformer" else 0.04,
        targets={
            "eventFamily": _export_target(
                name="eventFamily",
                labels=EVENT_FAMILIES,
                weight_matrix=model.segment_family_head.weight.detach().cpu().numpy(),
                bias_vector=model.segment_family_head.bias.detach().cpu().numpy(),
            ),
            "outcome": _export_target(
                name="outcome",
                labels=OUTCOMES,
                weight_matrix=model.outcome_head.weight.detach().cpu().numpy(),
                bias_vector=model.outcome_head.bias.detach().cpu().numpy(),
            ),
            "shotSubtype": _export_target(
                name="shotSubtype",
                labels=SHOT_SUBTYPES,
                weight_matrix=model.shot_subtype_head.weight.detach().cpu().numpy(),
                bias_vector=model.shot_subtype_head.bias.detach().cpu().numpy(),
            ),
        },
        proposal_acceptance_threshold=0.62,
        proposal_competition_margin_threshold=0.06,
        proposal_candidate_limit=4,
    )


def build_temporal_event_detector_report(
    *,
    baseline_metrics: dict[str, Any],
    actionformer_metrics: dict[str, Any],
    tridet_metrics: dict[str, Any],
    winner: str,
) -> str:
    lines = [
        "# Temporal Event Detector Candidates",
        "",
        f"- Winner: `{winner}`",
        "",
        "## Candidate Metrics",
    ]
    for name, metrics in (
        ("phase4bBaseline", baseline_metrics),
        ("actionformer", actionformer_metrics),
        ("tridet", tridet_metrics),
    ):
        lines.extend(
            [
                f"### {name}",
                f"- eventFamilyAccuracy: `{metrics.get('eventFamilyAccuracy')}`",
                f"- outcomeAccuracy: `{metrics.get('outcomeAccuracy')}`",
                f"- shotSubtypeAccuracy: `{metrics.get('shotSubtypeAccuracy')}`",
                f"- eventDetectionPrecision / Recall: `{metrics.get('eventDetectionPrecision')}` / `{metrics.get('eventDetectionRecall')}`",
                f"- proposalAcceptanceRate: `{metrics.get('proposalAcceptanceRate')}`",
                f"- acceptedShotProposalOutcomeAccuracy: `{metrics.get('acceptedShotProposalOutcomeAccuracy')}`",
                f"- eventnessBrier: `{metrics.get('eventnessBrier')}`",
                f"- uncertaintyRate: `{metrics.get('uncertaintyRate')}`",
                f"- highlightDominance: `{metrics.get('highlightDominance')}`",
                f"- otherDominance: `{metrics.get('otherDominance')}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def candidate_score(metrics: dict[str, Any]) -> float:
    proposal_acceptance_rate = float(metrics.get("proposalAcceptanceRate", 0.0) or 0.0)
    uncertainty_rate = float(metrics.get("uncertaintyRate", 0.0) or 0.0)
    rejected_true_negative_rate = float(metrics.get("rejectedProposalTrueNegativeRate", 0.0) or 0.0)
    rejected_true_miss_rate = float(metrics.get("rejectedProposalTrueMissRate", 0.0) or 0.0)
    flat_label_spread = float(len(metrics.get("flatLabelDistribution", {}) or {}))
    return (
        (1.15 * float(metrics.get("eventFamilyAccuracy", 0.0)))
        + (0.95 * float(metrics.get("outcomeAccuracy", 0.0)))
        + (0.9 * float(metrics.get("eventDetectionPrecision", 0.0)))
        + (0.9 * float(metrics.get("eventDetectionRecall", 0.0)))
        + (1.0 * float(metrics.get("acceptedShotProposalOutcomeAccuracy", 0.0) or 0.0))
        + (0.35 * (1.0 - float(metrics.get("eventnessBrier", 1.0) or 1.0)))
        + (0.25 * float(metrics.get("shotSubtypeAccuracy", 0.0) or 0.0))
        + (0.3 * rejected_true_negative_rate)
        - (0.7 * rejected_true_miss_rate)
        + (0.08 * flat_label_spread)
        - (0.7 * float(metrics.get("highlightDominance", 0.0)))
        - (0.7 * float(metrics.get("otherDominance", 0.0)))
        - (0.55 * abs(proposal_acceptance_rate - 0.45))
        - (0.6 * abs(uncertainty_rate - 0.18))
        - (0.9 * max(0.0, proposal_acceptance_rate - 0.8))
        - (0.9 * max(0.0, 0.06 - uncertainty_rate))
        - (0.75 * max(0.0, 2.0 - flat_label_spread))
    )


def _resolve_time(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _closest_index(timestamps: Sequence[float], target: float) -> int:
    return min(range(len(timestamps)), key=lambda index: abs(float(timestamps[index]) - float(target)))


def _median_step(timestamps: Sequence[float]) -> float:
    if len(timestamps) < 2:
        return 0.75
    deltas = [max(float(timestamps[index + 1]) - float(timestamps[index]), 0.0) for index in range(len(timestamps) - 1)]
    sorted_deltas = sorted(delta for delta in deltas if delta > 0.0)
    if not sorted_deltas:
        return 0.75
    return float(sorted_deltas[len(sorted_deltas) // 2])

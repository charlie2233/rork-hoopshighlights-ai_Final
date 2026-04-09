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
    SHOT_SPECIALIST_SUBTYPE_LABELS,
    TEMPORAL_EVENT_DETECTOR_FEATURE_SCHEMA_VERSION,
    TEMPORAL_EVENT_DETECTOR_MODEL_VERSION,
    TEMPORAL_EVENT_DETECTOR_SCHEMA_VERSION,
    TemporalConvLayer,
    TemporalEventDetectorBundle,
    TemporalEventProposal,
    build_shot_specialist_feature_map,
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


@dataclass(frozen=True)
class BinaryTrainingLossConfig:
    mode: str = "focal_class_balanced"
    focal_gamma: float = 1.75
    class_balance_alpha: float = 0.5


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


    class TorchShotSpecialistHead(nn.Module):
        def __init__(self, input_size: int, output_size: int) -> None:
            super().__init__()
            self.classifier = nn.Linear(input_size, output_size)

        def forward(self, inputs: torch.Tensor) -> torch.Tensor:
            return self.classifier(inputs)


    class TorchShotSpecialistTarget(nn.Module):
        def __init__(self, input_size: int, output_size: int) -> None:
            super().__init__()
            self.classifier = nn.Linear(input_size, output_size)

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
    proposal_rejector_loss: BinaryTrainingLossConfig = BinaryTrainingLossConfig(),
    proposal_acceptor_loss: BinaryTrainingLossConfig = BinaryTrainingLossConfig(),
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
    bundle = train_proposal_rejector_bundle(bundle, examples, loss_config=proposal_rejector_loss)
    bundle = train_proposal_ranker_bundle(bundle, examples)
    bundle = train_proposal_acceptor_bundle(bundle, examples, loss_config=proposal_acceptor_loss)
    bundle = train_shot_specialist_bundle(bundle, examples)
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
    loss_config: BinaryTrainingLossConfig = BinaryTrainingLossConfig(),
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
        loss = compute_proposal_rejector_loss(
            logits=logits,
            targets=targets,
            weights=weights,
            loss_config=loss_config,
        )
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
    loss_config: BinaryTrainingLossConfig = BinaryTrainingLossConfig(),
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
        loss = compute_proposal_acceptor_loss(
            logits=logits,
            targets=targets,
            weights=weights,
            loss_config=loss_config,
        )
        loss.backward()
        optimizer.step()

    target_model = export_proposal_acceptor_target(model)
    return replace(
        bundle,
        proposal_acceptor_feature_names=feature_names,
        proposal_acceptor=target_model,
    )


def build_shot_specialist_rows(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> list[dict[str, Any]]:
    return [
        row
        for row in build_proposal_conditioned_shot_rows(bundle, examples)
        if bool(row.get("includeInShotSpecialistDataset"))
    ]


def build_proposal_conditioned_shot_rows(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example in examples:
        proposals, _preferred_index, alignment_scores = build_candidate_proposal_alignment(bundle, example)
        if not proposals:
            continue
        alignment_by_index = {
            index: float(alignment_scores[index]) if index < len(alignment_scores) else 0.0
            for index in range(len(proposals))
        }
        for ranked_proposal in bundle._score_ranked_proposals(example.observations, proposals):
            proposal = ranked_proposal.proposal
            alignment_score = alignment_by_index.get(int(proposal.proposal_index), 0.0)
            features = build_shot_specialist_feature_map(
                observations=example.observations,
                proposal=proposal,
                ranked_proposal=ranked_proposal,
            )
            shot_attempt_likelihood = float(features.get("shot_attempt_likelihood", 0.0))
            proposal_shot_attempt_score = float(features.get("shot_proposal_shot_attempt_score", 0.0))
            proposal_likely_shot_attempt = (
                proposal.coarse_event_family == "shot_attempt"
                or shot_attempt_likelihood >= 0.34
                or alignment_score >= 0.22
                or (
                    ranked_proposal.accepted
                    and ranked_proposal.acceptance_score >= max(bundle.proposal_acceptance_threshold + 0.02, 0.64)
                    and proposal_shot_attempt_score >= 0.42
                )
            )
            accepted_true_shot = (
                ranked_proposal.accepted
                and proposal_likely_shot_attempt
                and example.event_family == "shot_attempt"
                and alignment_score >= 0.24
            )
            accepted_false_shot = (
                ranked_proposal.accepted
                and proposal_likely_shot_attempt
                and not accepted_true_shot
            )
            borderline_accepted = (
                ranked_proposal.accepted
                and proposal_likely_shot_attempt
                and (
                    ranked_proposal.acceptance_score < bundle.proposal_acceptance_threshold + 0.08
                    or ranked_proposal.competition_margin < bundle.proposal_competition_margin_threshold + 0.04
                    or proposal.event_score < bundle.event_score_threshold + 0.08
                )
            )
            rejected_near_shot = (
                not ranked_proposal.accepted
                and proposal_likely_shot_attempt
                and (
                    alignment_score >= 0.2
                    or shot_attempt_likelihood >= 0.24
                    or proposal.event_score >= max(bundle.event_score_threshold - 0.02, 0.18)
                )
            )
            include_in_dataset = accepted_true_shot or accepted_false_shot or borderline_accepted or rejected_near_shot
            if not include_in_dataset:
                continue

            if accepted_true_shot:
                proposal_category = "accepted_true_shot"
                outcome_label = example.outcome if example.outcome in OUTCOMES else "uncertain"
                subtype_label = (
                    example.shot_subtype
                    if example.shot_subtype in {"dunk", "layup", "jumper", "three", "putback"}
                    and outcome_label != "uncertain"
                    else "uncertain"
                )
            elif accepted_false_shot:
                proposal_category = "accepted_false_shot"
                outcome_label = "uncertain"
                subtype_label = "uncertain"
            elif borderline_accepted:
                proposal_category = "borderline_accepted"
                outcome_label = "uncertain"
                subtype_label = "uncertain"
            else:
                proposal_category = "rejected_near_shot"
                outcome_label = "uncertain"
                subtype_label = "uncertain"

            rows.append(
                {
                    "clipId": example.clip_id,
                    "proposalIndex": int(proposal.proposal_index),
                    "split": example.split,
                    "sourceKind": example.source_kind,
                    "sourceDomain": example.source_domain,
                    "sourceSet": example.source_set,
                    "eventFamily": example.event_family,
                    "proposalEventFamily": proposal.coarse_event_family,
                    "proposalCategory": proposal_category,
                    "proposalAccepted": ranked_proposal.accepted,
                    "proposalLikelyShotAttempt": proposal_likely_shot_attempt,
                    "proposalAlignmentScore": round(alignment_score, 4),
                    "proposalAcceptanceScore": round(float(ranked_proposal.acceptance_score), 4),
                    "proposalCompetitionMargin": round(float(ranked_proposal.competition_margin), 4),
                    "includeInShotSpecialistDataset": include_in_dataset,
                    "useForTraining": proposal_category in {"accepted_true_shot", "accepted_false_shot"},
                    "useForCalibration": (
                        example.source_kind == "gold"
                        and example.split in {"val", "test"}
                        and proposal_category in {"accepted_true_shot", "accepted_false_shot"}
                    ),
                    "outcomeLabel": outcome_label,
                    "subtypeLabel": subtype_label,
                    "features": features,
                    "outcomeWeight": shot_specialist_outcome_weight(
                        example,
                        outcome_label=outcome_label,
                        proposal_category=proposal_category,
                    ),
                    "subtypeWeight": shot_specialist_subtype_weight(
                        example,
                        subtype_label=subtype_label,
                        proposal_category=proposal_category,
                    ),
                }
            )
    return rows


def derive_shot_specialist_feature_names(rows: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    feature_names: set[str] = set()
    for row in rows:
        features = row.get("features")
        if isinstance(features, dict):
            feature_names.update(str(name) for name in features.keys())
    return tuple(sorted(feature_names))


def compute_shot_specialist_loss(*, logits: Any, targets: Any, weights: Any):
    base_loss = F.cross_entropy(logits, targets, reduction="none")
    probabilities = torch.softmax(logits, dim=-1)
    pt = probabilities[torch.arange(probabilities.shape[0]), targets]
    focal = torch.pow(1.0 - pt, 1.85)
    weighted = base_loss * focal * weights
    return weighted.sum() / torch.clamp(weights.sum(), min=1e-6)


def export_shot_specialist_target(
    model: Any,
    *,
    name: str,
    labels: Sequence[str],
    uncertainty_threshold: float,
    margin_threshold: float,
    top_k: int,
) -> TemporalTargetModel:
    return TemporalTargetModel(
        name=name,
        classes=tuple(str(label) for label in labels),
        weight=tuple(
            tuple(float(value) for value in row)
            for row in model.classifier.weight.detach().cpu().numpy().tolist()
        ),
        bias=tuple(float(value) for value in model.classifier.bias.detach().cpu().numpy().tolist()),
        temperature=1.0,
        uncertainty_threshold=uncertainty_threshold,
        margin_threshold=margin_threshold,
        top_k=top_k,
    )


def shot_specialist_outcome_weight(
    example: TemporalTrainingExample,
    *,
    outcome_label: str,
    proposal_category: str,
) -> float:
    weight = max(float(example.weight), 0.0)
    if proposal_category == "accepted_true_shot":
        weight *= 1.65
    elif proposal_category == "accepted_false_shot":
        weight *= 1.2
    elif proposal_category == "borderline_accepted":
        weight *= 0.8
    elif proposal_category == "rejected_near_shot":
        weight *= 0.55
    if outcome_label in {"missed", "blocked"}:
        weight *= 1.5
    elif outcome_label == "made":
        weight *= 1.18
    if outcome_label == "uncertain":
        if proposal_category == "accepted_true_shot":
            weight *= 0.95
        elif proposal_category == "accepted_false_shot":
            weight *= 0.85
        else:
            weight *= 0.75
    if example.source_kind == "disagreement":
        weight *= 1.15
    if example.source_domain in {"live_staging", "staging_smoke", "benchmark_eval"}:
        weight *= 1.15
    if example.event_family == "defensive_event" or example.outcome == "blocked":
        weight *= 1.2
    return round(weight, 4)


def shot_specialist_subtype_weight(
    example: TemporalTrainingExample,
    *,
    subtype_label: str,
    proposal_category: str,
) -> float:
    weight = max(float(example.weight), 0.0)
    if proposal_category == "accepted_true_shot":
        weight *= 1.45
    elif proposal_category == "accepted_false_shot":
        weight *= 0.85
    elif proposal_category == "borderline_accepted":
        weight *= 0.72
    elif proposal_category == "rejected_near_shot":
        weight *= 0.55
    if subtype_label in {"dunk", "layup"}:
        weight *= 1.3
    if subtype_label in {"jumper", "three"}:
        weight *= 1.25
    if subtype_label == "uncertain":
        weight *= 0.9
    if example.outcome in {"missed", "blocked"}:
        weight *= 1.1
    if example.source_kind == "disagreement":
        weight *= 1.1
    if example.source_domain in {"live_staging", "staging_smoke", "benchmark_eval"}:
        weight *= 1.1
    return round(weight, 4)


def train_shot_specialist_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
    *,
    epochs: int = 220,
    learning_rate: float = 0.02,
    random_seed: int = DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED + 17,
) -> TemporalEventDetectorBundle:
    if torch is None or nn is None or F is None:  # pragma: no cover
        raise RuntimeError("torch is required to train the shot specialist")
    rows = build_shot_specialist_rows(bundle, examples)
    train_rows = [row for row in rows if row["split"] == "train" and row["useForTraining"]]
    if not train_rows:
        train_rows = [row for row in rows if row["useForTraining"]]
    feature_names = derive_shot_specialist_feature_names(rows)
    if not feature_names:
        return replace(
            bundle,
            shot_specialist_feature_names=(),
            shot_specialist_outcome=None,
            shot_specialist_subtype=None,
        )

    np.random.seed(int(random_seed))
    torch.manual_seed(int(random_seed))
    if torch.cuda.is_available():  # pragma: no cover
        torch.cuda.manual_seed_all(int(random_seed))

    targets = dict(bundle.targets)
    targets.pop("shotOutcomeSpecialist", None)
    targets.pop("shotSubtypeSpecialist", None)
    shot_outcome_target: TemporalTargetModel | None = None
    shot_subtype_target: TemporalTargetModel | None = None

    outcome_labels = {str(row["outcomeLabel"]) for row in train_rows}
    if len(outcome_labels) > 1:
        inputs = torch.tensor(
            [[float(row["features"].get(name, 0.0)) for name in feature_names] for row in train_rows],
            dtype=torch.float32,
        )
        outcome_targets = torch.tensor(
            [OUTCOMES.index(str(row["outcomeLabel"])) for row in train_rows],
            dtype=torch.long,
        )
        outcome_weights = torch.tensor(
            [float(row["outcomeWeight"]) for row in train_rows],
            dtype=torch.float32,
        )
        outcome_model = TorchShotSpecialistHead(len(feature_names), len(OUTCOMES))
        optimizer = torch.optim.Adam(outcome_model.parameters(), lr=learning_rate)
        for _ in range(epochs):
            optimizer.zero_grad()
            loss = compute_shot_specialist_loss(
                logits=outcome_model(inputs),
                targets=outcome_targets,
                weights=outcome_weights,
            )
            loss.backward()
            optimizer.step()
        shot_outcome_target = export_shot_specialist_target(
            outcome_model,
            name="shotOutcomeSpecialist",
            labels=OUTCOMES,
            uncertainty_threshold=0.62,
            margin_threshold=0.12,
            top_k=3,
        )
        targets["shotOutcomeSpecialist"] = shot_outcome_target

    subtype_rows = [
        row
        for row in train_rows
        if row["outcomeLabel"] != "uncertain"
        and str(row["subtypeLabel"]) in SHOT_SPECIALIST_SUBTYPE_LABELS
    ]
    subtype_labels = {str(row["subtypeLabel"]) for row in subtype_rows}
    if len(subtype_labels) > 1:
        inputs = torch.tensor(
            [[float(row["features"].get(name, 0.0)) for name in feature_names] for row in subtype_rows],
            dtype=torch.float32,
        )
        subtype_targets = torch.tensor(
            [SHOT_SPECIALIST_SUBTYPE_LABELS.index(str(row["subtypeLabel"])) for row in subtype_rows],
            dtype=torch.long,
        )
        subtype_weights = torch.tensor(
            [float(row["subtypeWeight"]) for row in subtype_rows],
            dtype=torch.float32,
        )
        subtype_model = TorchShotSpecialistHead(len(feature_names), len(SHOT_SPECIALIST_SUBTYPE_LABELS))
        optimizer = torch.optim.Adam(subtype_model.parameters(), lr=learning_rate)
        for _ in range(epochs):
            optimizer.zero_grad()
            loss = compute_shot_specialist_loss(
                logits=subtype_model(inputs),
                targets=subtype_targets,
                weights=subtype_weights,
            )
            loss.backward()
            optimizer.step()
        shot_subtype_target = export_shot_specialist_target(
            subtype_model,
            name="shotSubtypeSpecialist",
            labels=SHOT_SPECIALIST_SUBTYPE_LABELS,
            uncertainty_threshold=0.68,
            margin_threshold=0.14,
            top_k=3,
        )
        targets["shotSubtypeSpecialist"] = shot_subtype_target

    return replace(
        bundle,
        shot_specialist_feature_names=feature_names,
        targets=targets,
        shot_specialist_outcome=shot_outcome_target,
        shot_specialist_subtype=shot_subtype_target,
    )


def summarize_proposal_conditioned_shot_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "totalRows": len(rows),
        "acceptedRows": sum(1 for row in rows if row.get("proposalAccepted")),
        "trainingRows": sum(1 for row in rows if row.get("useForTraining")),
        "calibrationRows": sum(1 for row in rows if row.get("useForCalibration")),
        "likelyShotAttemptRows": sum(1 for row in rows if row.get("proposalLikelyShotAttempt")),
        "categories": dict(sorted(Counter(str(row.get("proposalCategory") or "unknown") for row in rows).items())),
    }


def _proposal_conditioned_calibration_rows(
    rows: Sequence[dict[str, Any]],
    *,
    require_outcome_resolution: bool,
) -> list[dict[str, Any]]:
    filtered = [
        row
        for row in rows
        if row.get("useForCalibration")
        and row.get("proposalAccepted")
        and row.get("proposalLikelyShotAttempt")
        and str(row.get("proposalCategory")) in {"accepted_true_shot", "accepted_false_shot"}
    ]
    if require_outcome_resolution:
        filtered = [
            row
            for row in filtered
            if str(row.get("proposalCategory")) == "accepted_true_shot"
            and str(row.get("outcomeLabel")) != "uncertain"
        ]
    return filtered


def _proposal_conditioned_target_calibration(
    bundle: TemporalEventDetectorBundle,
    rows: Sequence[dict[str, Any]],
    *,
    target_key: str,
    gold_key: str,
) -> dict[str, Any] | None:
    target = bundle.targets.get(target_key)
    if target is None or not bundle.shot_specialist_feature_names:
        return None
    eligible_rows = _proposal_conditioned_calibration_rows(
        rows,
        require_outcome_resolution=(target_key == "shotSubtypeSpecialist"),
    )
    if not eligible_rows:
        return None

    bucket_bounds = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))
    bucket_totals = [{"count": 0, "correct": 0, "confidence": 0.0} for _ in bucket_bounds]
    label_space = tuple(str(label) for label in target.classes)
    predicted_distribution: Counter[str] = Counter()
    gold_distribution: Counter[str] = Counter()
    confidence_sum = 0.0
    brier_sum = 0.0
    correct = 0
    abstained = 0
    evaluated = 0

    for row in eligible_rows:
        gold_label = str(row.get(gold_key) or "uncertain")
        if gold_label not in label_space:
            continue
        feature_vector = np.asarray(
            [float((row.get("features") or {}).get(name, 0.0)) for name in bundle.shot_specialist_feature_names],
            dtype=np.float64,
        )
        prediction = target.predict(feature_vector, model_version=bundle.model_version)
        evaluated += 1
        confidence_sum += float(prediction.confidence)
        predicted_distribution[str(prediction.label)] += 1
        gold_distribution[gold_label] += 1
        if str(prediction.label) == gold_label:
            correct += 1
        if prediction.is_uncertain or str(prediction.label) in {"uncertain", "null"}:
            abstained += 1
        brier_sum += sum(
            (float(prediction.distribution.get(label, 0.0)) - (1.0 if label == gold_label else 0.0)) ** 2
            for label in label_space
        ) / max(len(label_space), 1)
        confidence = min(max(float(prediction.confidence), 0.0), 1.0)
        bucket_index = 0
        for index, (low, high) in enumerate(bucket_bounds):
            if confidence < high or (index == len(bucket_bounds) - 1 and confidence <= high):
                bucket_index = index
                break
        bucket_totals[bucket_index]["count"] += 1
        bucket_totals[bucket_index]["confidence"] += confidence
        bucket_totals[bucket_index]["correct"] += int(str(prediction.label) == gold_label)

    if evaluated == 0:
        return None

    ece = 0.0
    bins: list[dict[str, Any]] = []
    for (low, high), bucket in zip(bucket_bounds, bucket_totals):
        count = int(bucket["count"])
        mean_confidence = round(float(bucket["confidence"]) / count, 4) if count else 0.0
        accuracy = round(float(bucket["correct"]) / count, 4) if count else 0.0
        if count:
            ece += (count / evaluated) * abs(accuracy - mean_confidence)
        bins.append(
            {
                "minScore": low,
                "maxScore": high,
                "count": count,
                "meanConfidence": mean_confidence,
                "accuracy": accuracy,
            }
        )

    return {
        "sampleCount": evaluated,
        "accuracy": round(correct / evaluated, 4),
        "meanConfidence": round(confidence_sum / evaluated, 4),
        "brierScore": round(brier_sum / evaluated, 4),
        "expectedCalibrationError": round(ece, 4),
        "abstentionRate": round(abstained / evaluated, 4),
        "predictedDistribution": dict(sorted(predicted_distribution.items())),
        "goldDistribution": dict(sorted(gold_distribution.items())),
        "bins": bins,
    }


def _proposal_conditioned_target_score(summary: dict[str, Any] | None, *, target_key: str) -> float:
    if not summary:
        return float("-inf")
    desired_abstention = 0.14 if target_key == "shotOutcomeSpecialist" else 0.24
    abstention_rate = float(summary.get("abstentionRate", desired_abstention))
    return (
        (1.35 * float(summary.get("accuracy", 0.0)))
        + (0.45 * (1.0 - float(summary.get("brierScore", 1.0))))
        + (0.4 * (1.0 - float(summary.get("expectedCalibrationError", 1.0))))
        - (0.35 * abs(abstention_rate - desired_abstention))
        - (0.2 * max(abstention_rate - (desired_abstention * 1.5), 0.0))
    )


def _calibrate_proposal_conditioned_specialist_target(
    bundle: TemporalEventDetectorBundle,
    rows: Sequence[dict[str, Any]],
    *,
    target_key: str,
    gold_key: str,
    temperatures: Sequence[float],
    uncertainty_thresholds: Sequence[float],
    margin_thresholds: Sequence[float],
) -> TemporalEventDetectorBundle:
    target = bundle.targets.get(target_key)
    if target is None:
        return bundle
    best_bundle = bundle
    best_summary = _proposal_conditioned_target_calibration(bundle, rows, target_key=target_key, gold_key=gold_key)
    best_score = _proposal_conditioned_target_score(best_summary, target_key=target_key)
    for temperature in temperatures:
        for uncertainty in uncertainty_thresholds:
            for margin in margin_thresholds:
                candidate_target = replace(
                    target,
                    temperature=float(temperature),
                    uncertainty_threshold=float(uncertainty),
                    margin_threshold=float(margin),
                )
                candidate_targets = dict(bundle.targets)
                candidate_targets[target_key] = candidate_target
                replace_kwargs: dict[str, Any] = {"targets": candidate_targets}
                if target_key == "shotOutcomeSpecialist":
                    replace_kwargs["shot_specialist_outcome"] = candidate_target
                elif target_key == "shotSubtypeSpecialist":
                    replace_kwargs["shot_specialist_subtype"] = candidate_target
                candidate_bundle = replace(bundle, **replace_kwargs)
                summary = _proposal_conditioned_target_calibration(
                    candidate_bundle,
                    rows,
                    target_key=target_key,
                    gold_key=gold_key,
                )
                score = _proposal_conditioned_target_score(summary, target_key=target_key)
                if score > best_score:
                    best_bundle = candidate_bundle
                    best_score = score
    return best_bundle


def refresh_shot_specialist_bundle(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
    *,
    epochs: int = 220,
    learning_rate: float = 0.02,
    random_seed: int = DEFAULT_TEMPORAL_EVENT_DETECTOR_SEED + 17,
) -> TemporalEventDetectorBundle:
    refreshed_bundle = train_shot_specialist_bundle(
        bundle,
        examples,
        epochs=epochs,
        learning_rate=learning_rate,
        random_seed=random_seed,
    )
    calibration_examples = [
        example
        for example in examples
        if example.source_kind == "gold" and example.split in {"val", "test"}
    ]
    proposal_conditioned_rows = build_proposal_conditioned_shot_rows(refreshed_bundle, calibration_examples)
    if len(_proposal_conditioned_calibration_rows(proposal_conditioned_rows, require_outcome_resolution=False)) >= 4:
        refreshed_bundle = _calibrate_proposal_conditioned_specialist_target(
            refreshed_bundle,
            proposal_conditioned_rows,
            target_key="shotOutcomeSpecialist",
            gold_key="outcomeLabel",
            temperatures=(0.95, 1.1, 1.25),
            uncertainty_thresholds=(0.48, 0.54, 0.6),
            margin_thresholds=(0.08, 0.12, 0.16),
        )
    if len(_proposal_conditioned_calibration_rows(proposal_conditioned_rows, require_outcome_resolution=True)) >= 4:
        refreshed_bundle = _calibrate_proposal_conditioned_specialist_target(
            refreshed_bundle,
            proposal_conditioned_rows,
            target_key="shotSubtypeSpecialist",
            gold_key="subtypeLabel",
            temperatures=(0.95, 1.1, 1.25),
            uncertainty_thresholds=(0.54, 0.6, 0.66),
            margin_thresholds=(0.1, 0.14, 0.18),
        )
    notes = tuple(
        dict.fromkeys(
            [
                *refreshed_bundle.notes,
                "Proposal-conditioned shot-specialist heads refreshed from the frozen phase4e TriDet proposal stack.",
            ]
        )
    )
    return replace(
        refreshed_bundle,
        trained_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        source_dataset=f"{bundle.source_dataset}+phase4g_proposal_conditioned_shot_refresh",
        model_version=(
            "temporal-event-detector-tridet-proposal-conditioned-shot-specialist-v2"
            if bundle.detector_family == "tridet"
            else f"temporal-event-detector-{bundle.detector_family}-proposal-conditioned-shot-specialist-v2"
        ),
        notes=notes,
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


def compute_proposal_rejector_loss(
    *,
    logits: Any,
    targets: Any,
    weights: Any,
    loss_config: BinaryTrainingLossConfig = BinaryTrainingLossConfig(),
):
    return _compute_binary_training_loss(logits=logits, targets=targets, weights=weights, loss_config=loss_config)


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


def compute_proposal_acceptor_loss(
    *,
    logits: Any,
    targets: Any,
    weights: Any,
    loss_config: BinaryTrainingLossConfig = BinaryTrainingLossConfig(),
):
    return _compute_binary_training_loss(logits=logits, targets=targets, weights=weights, loss_config=loss_config)


def _compute_binary_training_loss(
    *,
    logits: Any,
    targets: Any,
    weights: Any,
    loss_config: BinaryTrainingLossConfig,
):
    base_loss = F.cross_entropy(logits, targets, reduction="none")
    effective_weights = weights
    mode = str(loss_config.mode or "focal").lower()
    if "class" in mode:
        class_weights = _binary_class_balance_weights(targets, alpha=float(loss_config.class_balance_alpha))
        effective_weights = effective_weights * class_weights
    probabilities = torch.softmax(logits, dim=-1)
    pt = probabilities[torch.arange(probabilities.shape[0]), targets]
    focal_gamma = float(loss_config.focal_gamma)
    if "focal" in mode:
        focal = torch.pow(1.0 - pt, focal_gamma)
    else:
        focal = torch.ones_like(pt)
    weighted = base_loss * focal * effective_weights
    return weighted.sum() / torch.clamp(effective_weights.sum(), min=1e-6)


def _binary_class_balance_weights(targets: Any, *, alpha: float) -> Any:
    counts = torch.bincount(targets, minlength=2).float()
    total = torch.clamp(counts.sum(), min=1.0)
    inverse_frequency = total / torch.clamp(counts, min=1.0)
    inverse_frequency = inverse_frequency / torch.clamp(inverse_frequency.mean(), min=1e-6)
    blended = (1.0 - float(alpha)) + (float(alpha) * inverse_frequency)
    return blended[targets]


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


def export_proposal_acceptor_target(
    model: Any,
    *,
    temperature: float = 1.0,
    uncertainty_threshold: float = 0.58,
    margin_threshold: float = 0.06,
) -> TemporalTargetModel:
    return TemporalTargetModel(
        name="proposalAcceptor",
        classes=tuple(PROPOSAL_ACCEPT_LABELS),
        weight=tuple(
            tuple(float(value) for value in row)
            for row in model.classifier.weight.detach().cpu().numpy().tolist()
        ),
        bias=tuple(float(value) for value in model.classifier.bias.detach().cpu().numpy().tolist()),
        temperature=float(temperature),
        uncertainty_threshold=float(uncertainty_threshold),
        margin_threshold=float(margin_threshold),
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
        family_gate_open = bool(
            metadata.get("temporal_event_detector_family_gate_open")
            if "temporal_event_detector_family_gate_open" in metadata
            else metadata.get("temporal_event_detector_classifier_gate_open")
        )
        proposal_score = float(
            metadata.get("temporal_event_detector_proposal_acceptance_score")
            or metadata.get("temporal_event_detector_event_score")
            or 0.0
        )
        acceptance_probability = float(
            metadata.get("temporal_event_detector_proposal_acceptance_probability")
            or metadata.get("temporal_event_detector_proposal_acceptor_confidence")
            or proposal_score
            or 0.0
        )
        acceptance_raw_score = float(
            metadata.get("temporal_event_detector_proposal_acceptance_raw_score")
            or proposal_score
            or 0.0
        )
        acceptance_energy = metadata.get("temporal_event_detector_proposal_acceptance_energy")
        shot_head_invoked = bool(
            metadata.get("temporal_event_detector_shot_head_invoked")
            if "temporal_event_detector_shot_head_invoked" in metadata
            else metadata.get("temporal_event_detector_shot_specialist_used")
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
                "familyGateOpen": family_gate_open,
                "proposalScore": round(proposal_score, 4),
                "proposalAcceptanceRawScore": round(acceptance_raw_score, 4),
                "proposalAcceptanceProbability": round(acceptance_probability, 4),
                "proposalAcceptanceEnergy": acceptance_energy,
                "proposalRejectorLabel": rejector_label,
                "proposalAcceptorLabel": acceptor_label,
                "shotHeadInvoked": shot_head_invoked,
                "familyGateRejectionReason": str(
                    metadata.get("temporal_event_detector_family_gate_rejection_reason")
                    or "none"
                ),
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
    family_gate_open_rate = round(sum(1 for row in rows if row["familyGateOpen"]) / total, 4)
    shot_head_invocation_rate = round(sum(1 for row in rows if row["shotHeadInvoked"]) / total, 4)
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
    acceptance_calibration = _binary_acceptance_calibration(rows)
    acceptance_coverage_risk_curve = _coverage_risk_curve(rows)
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
    accepted_shot_subtype_distribution = dict(
        sorted(Counter(row["predictedShotSubtype"] for row in accepted_shot_rows).items())
    )
    accepted_shot_abstention_rate = (
        round(
            sum(
                1
                for row in accepted_shot_rows
                if row["predictedShotSubtype"] in {"null", "uncertain"}
            )
            / accepted_shot_total,
            4,
        )
        if accepted_shot_rows
        else None
    )
    dunk_dominance = (
        round(
            sum(1 for row in accepted_shot_rows if str(row["predictedDisplayLabel"]).strip().lower() == "dunk")
            / accepted_shot_total,
            4,
        )
        if accepted_shot_rows
        else None
    )
    rejected_rows = [row for row in rows if not row["proposalAccepted"]]
    rejected_true_negative = sum(1 for row in rejected_rows if row["expectedEventFamily"] == "other")
    rejected_true_miss = sum(1 for row in rejected_rows if row["expectedEventFamily"] != "other")
    proposal_conditioned_rows = build_proposal_conditioned_shot_rows(bundle, evaluation_examples)
    proposal_conditioned_summary = summarize_proposal_conditioned_shot_rows(proposal_conditioned_rows)
    proposal_conditioned_outcome_calibration = _proposal_conditioned_target_calibration(
        bundle,
        proposal_conditioned_rows,
        target_key="shotOutcomeSpecialist",
        gold_key="outcomeLabel",
    )
    proposal_conditioned_subtype_calibration = _proposal_conditioned_target_calibration(
        bundle,
        proposal_conditioned_rows,
        target_key="shotSubtypeSpecialist",
        gold_key="subtypeLabel",
    )
    return {
        "eventFamilyAccuracy": event_family_accuracy,
        "outcomeAccuracy": outcome_accuracy,
        "shotSubtypeAccuracy": shot_subtype_accuracy,
        "uncertaintyRate": uncertainty_rate,
        "proposalAcceptanceRate": proposal_acceptance_rate,
        "familyGateOpenRate": family_gate_open_rate,
        "shotHeadInvocationRate": shot_head_invocation_rate,
        "eventnessBrier": eventness_brier,
        "proposalAcceptanceCalibration": acceptance_calibration,
        "proposalAcceptanceCoverageRiskCurve": acceptance_coverage_risk_curve,
        "acceptedShotProposalOutcomeAccuracy": accepted_shot_outcome_accuracy,
        "acceptedShotSubtypeDistribution": accepted_shot_subtype_distribution,
        "acceptedShotAbstentionRate": accepted_shot_abstention_rate,
        "dunkDominance": dunk_dominance,
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
        "proposalConditionedShotRows": proposal_conditioned_summary,
        "proposalConditionedOutcomeCalibration": proposal_conditioned_outcome_calibration,
        "proposalConditionedSubtypeCalibration": proposal_conditioned_subtype_calibration,
        "evaluationRows": rows,
    }


def _binary_acceptance_calibration(rows: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    scored_rows = [
        row
        for row in rows
        if row.get("proposalAcceptanceProbability") is not None and row.get("expectedEventFamily") is not None
    ]
    if not scored_rows:
        return None
    bucket_bounds = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))
    bucket_totals = [{"count": 0, "correct": 0, "probability": 0.0} for _ in bucket_bounds]
    brier_sum = 0.0
    for row in scored_rows:
        probability = float(row["proposalAcceptanceProbability"])
        target = 1.0 if str(row["expectedEventFamily"]) != "other" else 0.0
        brier_sum += (probability - target) ** 2
        bucket_index = 0
        for index, (low, high) in enumerate(bucket_bounds):
            if probability < high or (index == len(bucket_bounds) - 1 and probability <= high):
                bucket_index = index
                break
        bucket_totals[bucket_index]["count"] += 1
        bucket_totals[bucket_index]["probability"] += probability
        bucket_totals[bucket_index]["correct"] += int((probability >= 0.5) == (target >= 0.5))
    bins: list[dict[str, Any]] = []
    ece = 0.0
    total = len(scored_rows)
    for (low, high), bucket in zip(bucket_bounds, bucket_totals):
        count = int(bucket["count"])
        mean_probability = round(float(bucket["probability"]) / count, 4) if count else 0.0
        accuracy = round(float(bucket["correct"]) / count, 4) if count else 0.0
        if count:
            ece += (count / total) * abs(accuracy - mean_probability)
        bins.append(
            {
                "minScore": low,
                "maxScore": high,
                "count": count,
                "meanProbability": mean_probability,
                "accuracy": accuracy,
            }
        )
    return {
        "sampleCount": total,
        "brierScore": round(brier_sum / total, 4),
        "expectedCalibrationError": round(ece, 4),
        "bins": bins,
    }


def _coverage_risk_curve(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    scored_rows = [
        row
        for row in rows
        if row.get("proposalAcceptanceProbability") is not None and row.get("expectedEventFamily") is not None
    ]
    if not scored_rows:
        return []
    ranked_rows = sorted(scored_rows, key=lambda row: float(row["proposalAcceptanceProbability"]), reverse=True)
    total = len(ranked_rows)
    thresholds = (0.25, 0.4, 0.55, 0.7, 0.85)
    curve: list[dict[str, Any]] = []
    for threshold in thresholds:
        keep_count = max(int(round(total * threshold)), 1)
        kept = ranked_rows[:keep_count]
        accepted = sum(1 for row in kept if float(row["proposalAcceptanceProbability"]) >= 0.5)
        misses = sum(1 for row in kept if str(row["expectedEventFamily"]) != "shot_attempt" and float(row["proposalAcceptanceProbability"]) >= 0.5)
        curve.append(
            {
                "coverage": round(len(kept) / total, 4),
                "risk": round(misses / max(accepted, 1), 4),
            }
        )
    return curve


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
    proposal_conditioned_rows = build_proposal_conditioned_shot_rows(best_bundle, calibration_examples)
    best_bundle = _calibrate_proposal_conditioned_specialist_target(
        best_bundle,
        proposal_conditioned_rows,
        target_key="shotOutcomeSpecialist",
        gold_key="outcomeLabel",
        temperatures=(0.95, 1.1, 1.25),
        uncertainty_thresholds=(0.48, 0.54, 0.6),
        margin_thresholds=(0.08, 0.12, 0.16),
    )
    best_bundle = _calibrate_proposal_conditioned_specialist_target(
        best_bundle,
        proposal_conditioned_rows,
        target_key="shotSubtypeSpecialist",
        gold_key="subtypeLabel",
        temperatures=(0.95, 1.1, 1.25),
        uncertainty_thresholds=(0.54, 0.6, 0.66),
        margin_thresholds=(0.1, 0.14, 0.18),
    )
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
    proposal_conditioned_rows = build_proposal_conditioned_shot_rows(best_bundle, calibration_examples)
    best_bundle = _calibrate_proposal_conditioned_specialist_target(
        best_bundle,
        proposal_conditioned_rows,
        target_key="shotOutcomeSpecialist",
        gold_key="outcomeLabel",
        temperatures=(0.95, 1.1, 1.25),
        uncertainty_thresholds=(0.48, 0.54, 0.6),
        margin_thresholds=(0.08, 0.12, 0.16),
    )
    best_bundle = _calibrate_proposal_conditioned_specialist_target(
        best_bundle,
        proposal_conditioned_rows,
        target_key="shotSubtypeSpecialist",
        gold_key="subtypeLabel",
        temperatures=(0.95, 1.1, 1.25),
        uncertainty_thresholds=(0.54, 0.6, 0.66),
        margin_thresholds=(0.1, 0.14, 0.18),
    )
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


def _calibrate_specialist_target(
    bundle: TemporalEventDetectorBundle,
    examples: Sequence[TemporalTrainingExample],
    *,
    target_key: str,
    temperatures: Sequence[float],
    uncertainty_thresholds: Sequence[float],
    margin_thresholds: Sequence[float],
) -> TemporalEventDetectorBundle:
    target = bundle.targets.get(target_key)
    if target is None:
        return bundle
    best_bundle = bundle
    best_score = candidate_score(evaluate_temporal_event_detector_bundle(bundle, examples))
    for temperature in temperatures:
        for uncertainty in uncertainty_thresholds:
            for margin in margin_thresholds:
                candidate_target = replace(
                    target,
                    temperature=float(temperature),
                    uncertainty_threshold=float(uncertainty),
                    margin_threshold=float(margin),
                )
                candidate_targets = dict(bundle.targets)
                candidate_targets[target_key] = candidate_target
                replace_kwargs: dict[str, Any] = {"targets": candidate_targets}
                if target_key == "shotOutcomeSpecialist":
                    replace_kwargs["shot_specialist_outcome"] = candidate_target
                elif target_key == "shotSubtypeSpecialist":
                    replace_kwargs["shot_specialist_subtype"] = candidate_target
                candidate_bundle = replace(bundle, **replace_kwargs)
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
                f"- acceptedShotAbstentionRate: `{metrics.get('acceptedShotAbstentionRate')}`",
                f"- dunkDominance: `{metrics.get('dunkDominance')}`",
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
    family_gate_open_rate = float(metrics.get("familyGateOpenRate", 0.0) or 0.0)
    shot_head_invocation_rate = float(metrics.get("shotHeadInvocationRate", 0.0) or 0.0)
    uncertainty_rate = float(metrics.get("uncertaintyRate", 0.0) or 0.0)
    rejected_true_negative_rate = float(metrics.get("rejectedProposalTrueNegativeRate", 0.0) or 0.0)
    rejected_true_miss_rate = float(metrics.get("rejectedProposalTrueMissRate", 0.0) or 0.0)
    flat_label_spread = float(len(metrics.get("flatLabelDistribution", {}) or {}))
    dunk_dominance = float(metrics.get("dunkDominance", 0.0) or 0.0)
    abstention_rate = float(metrics.get("acceptedShotAbstentionRate", 0.0) or 0.0)
    acceptance_calibration = metrics.get("proposalAcceptanceCalibration") or {}
    return (
        (1.15 * float(metrics.get("eventFamilyAccuracy", 0.0)))
        + (0.95 * float(metrics.get("outcomeAccuracy", 0.0)))
        + (0.9 * float(metrics.get("eventDetectionPrecision", 0.0)))
        + (0.9 * float(metrics.get("eventDetectionRecall", 0.0)))
        + (1.25 * float(metrics.get("acceptedShotProposalOutcomeAccuracy", 0.0) or 0.0))
        + (0.35 * (1.0 - float(metrics.get("eventnessBrier", 1.0) or 1.0)))
        + (0.25 * float(metrics.get("shotSubtypeAccuracy", 0.0) or 0.0))
        + (0.18 * abstention_rate)
        + (0.3 * rejected_true_negative_rate)
        - (0.7 * rejected_true_miss_rate)
        + (0.2 * family_gate_open_rate)
        + (0.15 * shot_head_invocation_rate)
        + (0.08 * flat_label_spread)
        - (0.9 * dunk_dominance)
        - (0.7 * float(metrics.get("highlightDominance", 0.0)))
        - (0.7 * float(metrics.get("otherDominance", 0.0)))
        - (0.55 * abs(proposal_acceptance_rate - 0.45))
        - (0.6 * abs(uncertainty_rate - 0.18))
        - (0.9 * max(0.0, proposal_acceptance_rate - 0.8))
        - (0.9 * max(0.0, 0.06 - uncertainty_rate))
        - (0.75 * max(0.0, 2.0 - flat_label_spread))
        - (0.25 * float(acceptance_calibration.get("expectedCalibrationError", 0.0) or 0.0))
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

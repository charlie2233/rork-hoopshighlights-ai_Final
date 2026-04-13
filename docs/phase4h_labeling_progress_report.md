# Phase 4h Labeling Progress Report

## Scope

- Branch: `codex/phase4h-hard-negative-labeling-sprint`.
- Purpose: prepare labels for a future acceptor retrain; no retraining is performed in this branch.
- Truth-label policy: reviewer fields are intentionally blank until human review. Artifact-derived hints remain in `artifact_*` columns only.

## Queue Outputs

- Normalized seed queue: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_normalized.csv`.
- Expanded queue: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_expanded.csv`.
- Machine-readable summary: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_labeling_progress_summary.json`.

## Counts

- Normalized seed rows: `65`.
- Expanded rows: `110` across `96` unique clips.
- Row count can exceed clip count because accepted-proposal review and model-miss review are separate review tasks.
- Expanded source batches: `{"phase4h_acceptor_smoke_15clip": 21, "phase4h_gate_unblock_smoke_18clip": 18, "phase4h_staging_eval_63clip": 71}`.
- Expanded candidate buckets: `{"accepted_proposal_light_label": 14, "dead_ball|replay_or_reaction|setup|true_negative_non_event": 51, "possible_real_event_miss": 45}`.
- Accepted-proposal light-label rows: `14`.
- Remaining unlabeled rows: `110`.

## Candidate Hard-Negative Option Counts

- dead_ball: `51` candidate rows.
- replay_or_reaction: `51` candidate rows.
- setup: `51` candidate rows.
- true_negative_non_event: `51` candidate rows.

## Confirmed Hard-Negative Counts

- dead_ball: `0` confirmed rows.
- replay_or_reaction: `0` confirmed rows.
- setup: `0` confirmed rows.
- true_negative_non_event: `0` confirmed rows.

## Recommendation

- `continue labeling`.
- Rationale: confirmed hard-negative counts remain zero, so this pack unlocks review, not retraining.

# Phase 4h Hard-Negative Labeling Plan

## Scope

- Build labels needed for a future acceptor retrain; do not retrain from this queue yet.
- Do not invent hard-negative labels. Blank manual fields require human review before training use.
- Prioritize clips currently collapsing to `Highlight` / `eventFamily=other`, then accepted proposals that need lightweight shot labels.

## Queue Artifact

- CSV: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue.csv`.
- Total queue rows: `65`.
- Queue type distribution: `{"accepted_proposal_light_label": 14, "hard_negative_bucket_assignment": 51}`.
- Candidate hard-negative rows: `51`.
- Accepted proposal light-label rows: `14`.

## Confirmed Hard-Negative Counts

- dead_ball: `0`.
- replay_or_reaction: `0`.
- setup: `0`.
- true_negative_non_event: `0`.

## Manual Review Fields

- `manualHardNegativeBucket`: one of `dead_ball`, `replay_or_reaction`, `setup`, `true_negative_non_event`, or blank if not a hard negative.
- `manualAuditLabel`: `true_negative_non_event`, `real_event_missed_by_model`, `ambiguous_clip`, or `data_sampling_issue`.
- `manualShotAttempt`: `yes`, `no`, or `uncertain`.
- `manualOutcome`: `made`, `missed`, `blocked`, `uncertain`, or blank when not visible.

## Stop Rule

- Do not train a new acceptor until each required hard-negative bucket has confirmed rows and high-scoring unknown clips are resolved.

# Phase 4h Acceptor Calibration Plan

## Scope

- Branch: `codex/phase4h-acceptor-coverage-lift`.
- Goal: lift proposal acceptance coverage without touching family rescue thresholds, detector family, SpaceJam, or outcome mapping.
- Contract posture: additive-only replay artifacts and training config; no app-facing payload fields are removed or renamed.

## Standing Dataset

- Artifact: `services/inference/evals/phase4h_acceptor_coverage_lift/acceptance_calibration_dataset.jsonl`.
- Rows: `81`.
- Source distribution: `{"phase4h_gate_unblock_smoke_18clip": 18, "phase4h_staging_eval_63clip": 63}`.
- Acceptance labels: `{"accept": 42, "unknown": 39}`.
- Event families: `{"other": 39, "shot_attempt": 42}`.
- Outcomes: `{"made": 14, "missed": 28, "uncertain": 39}`.
- Source accepted proposals: `11`.
- Source acceptance rate: `0.1358`.

## Hard-Negative Coverage

- Present hard-negative buckets: `{}`.
- Missing hard-negative buckets: `["dead_ball", "replay_or_reaction", "setup", "true_negative_non_event"]`.
- Human-review rows still required: `39`.
- The current artifacts do not contain enough confirmed replay/dead-ball/setup/non-event labels to safely write a new acceptor checkpoint.

## Calibration Path

- Use raw acceptance score as the replay control signal because the 63-clip staging artifact lacks calibrated acceptance probability and energy score.
- Treat smoke `proposalAcceptanceProbability` as diagnostic telemetry only; raw acceptance score remains the sweep input for consistency with staging.
- Report accepted precision on audited rows separately from accepted unknown rows so unlabeled demo clips cannot masquerade as safe positives.
- Proposed retrain config artifact: `services/inference/evals/phase4h_acceptor_coverage_lift/proposal_acceptor_retrain_config.json`.

## Required Next Labels

- Confirm whether high-scoring unlabeled demo clips are real events, setup, replay/reaction, or true non-events.
- Add at least one confirmed row for each required hard-negative bucket before writing an acceptor checkpoint.
- Keep accepted -> family gate -> shot head smoke coverage as the first guardrail after any acceptor threshold or checkpoint change.

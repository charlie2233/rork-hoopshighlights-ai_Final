# Phase 4h Rollout Checklist

## Staging Validation Result - 2026-04-10

- Result: no-go; hold and recalibrate before any larger shadow rollout.
- Batch: `43` completed Worker-path uploads produced `63` clips through staging.
- Eval artifact: `services/inference/evals/phase4h_staging_eval/shadow_eval_report.json`.
- Audit queue: `services/inference/evals/phase4h_staging_eval/phase4h_audit_queue.json`.
- Proposal acceptance rate: `0.127` (`8` / `63`), below the `0.35` lower bound.
- Family gate open rate: `0.0`; accepted proposals existed but `familyGateOpenCount == 0`.
- Shot head invocation rate: `0.0`; accepted-shot outcome accuracy is not computable.
- Dominant flat label: `Highlight` at `1.0`; raw `eventFamily=other` is `1.0`.
- Miss-to-made drift: `0`, but this is weak because no clip reached a made-shot label.
- Telemetry gap: staged payload lacks calibrated acceptance probability, acceptance energy score, and explicit family-gate rejection reasons.

## Family Gate Suppression Replay - 2026-04-11

- Branch: `codex/phase4h-family-gate-suppression-fix`.
- Debug report: `docs/phase4h_family_gate_debug_report.md`.
- Sweep report: `docs/phase4h_family_gate_sweep_report.md`.
- Accepted-slice replay: `8` accepted proposals; all were known made-shot clips.
- Root cause: family top-1 was `transition` at `0.5264`, shot_attempt was top-2 at `0.4706`, and the old gate suppressed the accepted proposal without an exported closure reason.
- Comparator result: accepted-implies-family-eval with close-margin spotter rescue opens `8` family gates and invokes the shot head `8` times on replay.
- Recommended smoke setting: family temperature `1.0`, top-1 threshold `0.42`, top-2 margin threshold `0.02`, spotter rescue max delta `0.08`.
- Next gate: run only a small `15-20` clip staging smoke. Do not promote to another large batch until calibrated acceptance probability, energy score, and explicit family-gate closure reasons are present in staging payloads.

## Family Gate Smoke - 2026-04-11

- Branch: `codex/phase4h-family-gate-suppression-fix`.
- Smoke report: `docs/phase4h_smoke_report.md`.
- Eval artifact: `services/inference/evals/phase4h_smoke/shadow_eval_report.json`.
- Cloud Run revision: `hoopsclips-inference-staging-00034-xtc`.
- Result: no-go for follow-on branch creation from this smoke.
- Accepted proposals reached the shot stack: `proposalAcceptedCount=3`, `familyGateOpenCount=3`, `shotHeadInvocationCount=3`.
- Safety held for made/dunk collapse and miss-to-made drift: `Made Shot=3`, `Highlight=15`, `missToMadeDrift=0`, no concrete subtype emitted.
- Smoke failed the flat-label dominance guard: `Highlight=0.8333`, above the `0.80` smoke cap.
- Next gate: do not run a medium batch yet and do not create `codex/phase4h-acceptor-coverage-lift` from this no-go smoke without explicit approval.

## Acceptor Coverage Lift Replay - 2026-04-11

- Branch: `codex/phase4h-acceptor-coverage-lift`, based on `7e183fe`.
- Calibration plan: `docs/phase4h_acceptor_calibration_plan.md`.
- Sweep report: `docs/phase4h_acceptor_sweep_report.md`.
- Retrain report: `docs/phase4h_acceptor_retrain_report.md`.
- Bootstrap dataset: `services/inference/evals/phase4h_acceptor_coverage_lift/acceptance_calibration_dataset.jsonl`.
- Dataset rows: `81` from the `63`-clip staging batch and `18`-clip smoke batch.
- Current source artifact acceptance rate: `0.1358`; staging baseline remains `0.127`.
- Recommended replay-only config: temperature `1.0`, calibrated acceptance probability threshold `0.3`, energy threshold `-0.8`.
- Replay lift: proposal acceptance `0.3704`, family gate opens `29`, shot head invocations `29`, dominant flat-label share `0.642`, miss-to-made drift `0`.
- Safety caveat: confirmed hard-negative buckets are still missing for `dead_ball`, `replay_or_reaction`, `setup`, and `true_negative_non_event`.
- Decision: rerun a small smoke only after the acceptor change is wired behind the existing shadow path; do not request a `60-80` clip medium batch until high-scoring unknown clips and hard negatives are audited.

## Acceptor Coverage Smoke - 2026-04-13

- Branch: `codex/phase4h-acceptor-coverage-lift`.
- Smoke report: `docs/phase4h_acceptor_smoke_report.md`.
- Eval artifact: `services/inference/evals/phase4h_acceptor_smoke/shadow_eval_report.json`.
- Cloud Run revision: `hoopsclips-inference-staging-00035-nzj`.
- Runtime config: family temperature `1.0`, acceptance threshold `0.3`, energy threshold `-0.8`.
- Completed Worker-path outputs: `11` jobs, `15` clip windows; `0` completed-job failures and `0` null `runtimeFusionTemporalShadow` payloads.
- Harness caveat: two transient `ECONNRESET` polling failures occurred before the 20-item manifest finished; this decision uses the completed `15` clip windows only.
- Accepted path remained unblocked: `proposalAcceptedCount=3`, `familyGateOpenCount=3`, `shotHeadInvocationCount=3`.
- Smoke failed promotion guards: dominant flat-label share `0.8` (`Highlight`), raw `eventFamily=other` `0.8`, uncertainty rate `1.0`.
- Safety held for miss-to-made drift and subtype collapse: `expectedMissPredictedMadeShot=0`, no concrete subtype emitted.
- Decision: no-go for medium batch. Fill the hard-negative and accepted-proposal label queue before retrain or another staging-size request.

## Hard-Negative Labeling Bootstrap - 2026-04-13

- Labeling plan: `docs/phase4h_hard_negative_labeling_plan.md`.
- Queue artifact: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue.csv`.
- Total queue rows: `65`.
- Queue source counts: `phase4h_staging_eval_63clip=38`, `phase4h_gate_unblock_smoke_18clip=12`, `phase4h_acceptor_smoke_15clip=15`.
- Queue type counts: `hard_negative_bucket_assignment=51`, `accepted_proposal_light_label=14`.
- Confirmed hard-negative bucket counts remain `0` for `dead_ball`, `replay_or_reaction`, `setup`, and `true_negative_non_event`; blank manual fields require review before training use.

## Hard-Negative Labeling Sprint - 2026-04-13

- Branch: `codex/phase4h-hard-negative-labeling-sprint`, based on `35b1b5d`.
- Labeling guide: `docs/phase4h_labeling_guide.md`.
- Progress report: `docs/phase4h_labeling_progress_report.md`.
- Normalized reviewer queue: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_normalized.csv`.
- Expanded reviewer queue: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_label_queue_expanded.csv`.
- Machine-readable progress: `services/inference/evals/phase4h_acceptor_coverage_lift/hard_negative_labeling_progress_summary.json`.
- Smoke runner notes: `docs/phase4h_smoke_runner_reliability_notes.md`.
- Normalized seed rows: `65`; expanded rows: `110` across `96` unique clips.
- Expanded candidate buckets: `hard_negative_bucket_assignment options=51`, `possible_real_event_miss=45`, `accepted_proposal_light_label=14`.
- Confirmed hard-negative bucket counts remain `0` until human review fills `reviewer_split_other_bucket`.
- Decision: continue labeling. Do not retrain or request a medium batch from this branch.

## Before Shadow Deploy

- Confirm branch is the exact smoke candidate branch: `codex/phase4h-family-gate-suppression-fix` for gate-only smoke, or `codex/phase4h-acceptor-coverage-lift` only after the acceptor threshold/config change is explicitly approved.
- Confirm `services/inference/tests/test_temporal_event_detector.py` passes.
- Confirm `services/inference/tests/test_shadow_eval.py` passes.
- Confirm `services/inference/tests/test_phase4h_acceptor_coverage_lift.py` passes for acceptor coverage work.
- Confirm syntax check passes for all touched Phase 4h files.
- Confirm no app-facing contract fields changed in control-plane or iOS payload parsing.

## After Shadow Deploy

- Run one Worker-path smoke job.
- Confirm `requestId`, `uploadTraceId`, `inferenceAttemptId`, and `modelVersion` are present end to end.
- Confirm `runtimeFusionTemporalShadow` is non-null on the returned clips.
- Confirm `temporal_event_detector_family_gate_rejection_reason` is present whenever `familyGateOpen == false`.
- Confirm `temporal_event_detector_proposal_acceptance_probability` and `temporal_event_detector_proposal_acceptance_energy` are present in shadow metadata.

## Large Batch Eval

- Run a mixed shadow batch with at least `60` clips.
- Record:
  - proposal acceptance rate,
  - family gate open rate,
  - shot head invocation rate,
  - dominant flat-label share,
  - raw `eventFamily=other` rate,
  - uncertainty rate,
  - accepted-shot outcome accuracy,
  - acceptance calibration,
  - accepted-shot outcome calibration,
  - coverage-vs-risk curve.

## Guardrail Checks

- Proposal acceptance rate stays between `0.35` and `0.75`.
- `Highlight` dominance stays below `0.55`.
- raw `eventFamily=other` stays below `0.40`.
- No single flat label exceeds `0.65`.
- Miss-to-made drift remains `0`.
- Accepted proposals do not get suppressed so completely that `familyGateOpenCount == 0`.
- Accepted proposals do not get suppressed so completely that `shotHeadInvocationCount == 0`.

## Stop Conditions

- If `proposalAcceptanceRate` collapses to `0.0` or `1.0`, stop and inspect acceptor calibration before touching the detector.
- If accepted proposals exist but `familyGateOpenCount == 0`, stop and inspect gate rejection reasons before changing label mapping.
- If `familyGateOpenCount > 0` but `shotHeadInvocationCount == 0`, stop and inspect family output collapse before changing the shot head.

# Phase 4h Acceptor Coverage Smoke Report

## Scope

- Branch: `codex/phase4h-acceptor-coverage-lift`.
- Cloud Run revision: `hoopsclips-inference-staging-00035-nzj`.
- Staging version: `phase4h-acceptor-coverage-lift`.
- Worker path: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`.
- Runtime config: family temperature `1.0`, acceptance threshold `0.3`, energy threshold `-0.8`.
- Eval artifact: `services/inference/evals/phase4h_acceptor_smoke/shadow_eval_report.json`.

## Smoke Execution

- Completed Worker-path job outputs: `11`.
- Completed clip windows evaluated: `15`.
- Completed job statuses: `11 completed`, `0 failed`.
- Null `runtimeFusionTemporalShadow` payloads in completed clips: `0`.
- Harness note: the batch runner hit two transient `ECONNRESET` polling failures while progressing through the 20-item manifest. The decision below is based only on the completed `15` clip windows.

## Metrics

| Metric | Result | Gate | Status |
| --- | ---: | ---: | --- |
| `proposalAcceptedCount` | `3` | `> 0` | pass |
| `familyGateOpenCount / proposalAcceptedCount` | `1.0` | `>= 0.9` | pass |
| `shotHeadInvocationCount / familyGateOpenCount` | `1.0` | `>= 0.9` | pass |
| dominant flat-label share | `0.8` (`Highlight`) | `<= 0.75` | fail |
| raw `eventFamily=other` | `0.8` | `<= 0.65` | fail |
| miss-to-made drift | `0` | `0` | pass |
| uncertainty rate | `1.0` | no all-uncertain collapse | fail |
| all-dunk/made collapse | `Made Shot=3`, `Highlight=12`, no subtype emitted | no collapse | pass |

## Distribution

- Flat labels: `{"Highlight": 12, "Made Shot": 3}`.
- Event family: `{"other": 12, "shot_attempt": 3}`.
- Outcome: `{"made": 3, "uncertain": 12}`.
- Shot subtype: `{"null": 15}`.
- Source domains: `staging_hoopcut_demo_mixed_unlabeled=6`, `staging_hoopcut_known_made=3`, `staging_hoopcut_known_miss=6`.

## Calibration

- Acceptance Brier score: `0.7264`.
- Acceptance ECE-lite: `0.7348`.
- Reliability bucket: all `15` scored clips landed in `[0.8,1.0)` with mean probability `0.9348` and observed accuracy `0.2`.
- Accepted-shot outcome accuracy: `1.0` on `3` accepted shot proposals, but all accepted shots abstained on subtype and the sample is too small for promotion.

## Diagnosis

- The gate-unblocking path remains intact: every accepted proposal opened the family gate and invoked the shot head.
- The dominant failure is still under-fire / acceptance coverage plus overconfident acceptance calibration. Six labeled rejected clips are counted as true misses in the eval artifact, and the accepted probability distribution is high even when observed event correctness is low.
- The smoke does not justify a medium batch because flat-label dominance, raw `other`, and all-uncertain behavior all failed their smoke gates.

## Decision

- Result: no-go for promotion and no medium batch request.
- Recommendation: more labeling first. Fill the hard-negative queue and accepted-proposal light labels before retraining or requesting a `60-80` clip batch.
- Do not widen downstream family rescue logic; the accepted path is already unblocked.

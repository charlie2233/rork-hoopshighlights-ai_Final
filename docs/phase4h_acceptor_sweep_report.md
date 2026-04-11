# Phase 4h Acceptor Sweep Report

## Summary

- Sweep artifact: `services/inference/evals/phase4h_acceptor_coverage_lift/acceptor_sweep.json`.
- Baseline staging acceptance rate: `0.127`.
- Source artifact acceptance rate across bootstrap rows: `0.1358`.
- Bootstrap rows: `81`.
- Confirmed hard-negative rows: `0`.

## Recommendation

- Recommendation: rerun a small smoke only, not a 60-80 clip medium batch.
- Temperature: `1.0`.
- Calibrated acceptance probability threshold: `0.3`.
- Energy threshold: `-0.8`.
- Training loss config tag: `focal_class_balanced:g1.75:a0.50`.
- Replay proposal acceptance rate: `0.3704`.
- Replay family gate opens: `29`.
- Replay shot head invocations: `29`.
- Replay dominant flat-label share: `0.642`.
- Replay miss-to-made drift: `0`.
- Accepted unknown rows: `1`.
- This is a smoke-safety recommendation only because confirmed hard negatives are still missing.
- Source-specific replay acceptance: `{"phase4h_gate_unblock_smoke_18clip": {"acceptanceRate": 0.2778, "acceptedCount": 5, "rowCount": 18}, "phase4h_staging_eval_63clip": {"acceptanceRate": 0.3968, "acceptedCount": 25, "rowCount": 63}}`.

## Top Replay Rows

| temp | prob threshold | energy threshold | loss config | accept rate | gate opens | shot head | raw other | dominant share | unknown accepted | audited rejects accepted | miss->made |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0 | 0.3 | -0.8 | focal_class_balanced:g1.75:a0.50 | 0.3704 | 29 | 29 | 0.642 | 0.642 | 1 | 0 | 0 |
| 1.5 | 0.65 | None | focal_class_balanced:g1.75:a0.50 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | None | focal_class_balanced:g2.00:a0.65 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | None | class_balanced:g0.00:a0.65 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | -1.5 | focal_class_balanced:g1.75:a0.50 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | -1.5 | focal_class_balanced:g2.00:a0.65 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | -1.5 | class_balanced:g0.00:a0.65 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | -1.25 | focal_class_balanced:g1.75:a0.50 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | -1.25 | focal_class_balanced:g2.00:a0.65 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | -1.25 | class_balanced:g0.00:a0.65 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | -1.0 | focal_class_balanced:g1.75:a0.50 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |
| 1.5 | 0.65 | -1.0 | focal_class_balanced:g2.00:a0.65 | 0.1358 | 11 | 11 | 0.8642 | 0.8642 | 0 | 0 | 0 |

## Guardrail Readout

- Acceptance lift can be achieved on replay, but the medium-batch target of `0.35-0.75` is not justified until unknown high-scoring clips receive hard-negative or event labels.
- Accepted rows continue to model family-gate opening and shot-head invocation because this branch does not alter the now-working family-gate rescue path.
- Replay emits `Shot Attempt` for missed/uncertain accepted shot attempts, preventing miss-to-made drift in the sweep model.
- The sweep does not validate real shot-head outcome quality; live smoke remains required before any medium batch.

# Phase 4h Staging Eval Report

## Batch

- Date: `2026-04-10`
- Branch: `codex/phase4h-staging-eval-decision`
- Endpoint: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Shadow source: `runtimeFusionTemporalShadow`
- Worker-path uploads completed: `43` of `60` manifest items, stopped after the persisted result set exceeded the `>=60` clip gate.
- Clips evaluated: `63`
- Batch source mix: 11 known made clips, 22 known missed clips, 30 unlabeled demo-mixed clips.
- Raw eval artifact: `services/inference/evals/phase4h_staging_eval/shadow_eval_report.json`
- Full normalized markdown table: `services/inference/evals/phase4h_staging_eval/shadow_eval_report.md`

## Promotion Gate

| Gate | Target | Observed | Result |
| --- | --- | ---: | --- |
| Proposal acceptance rate | `0.35 to 0.75` | `0.1270` | `FAIL` |
| Highlight dominance | `< 0.55` | `1.0000` | `FAIL` |
| Raw eventFamily=other | `< 0.40` | `1.0000` | `FAIL` |
| Dominant flat-label share | `<= 0.65` | `1.0000` | `FAIL` |
| Miss-to-made drift | `= 0` | `0` | `PASS` |

## Core Metrics

- Proposal acceptance rate: `0.1270` (`8` / `63` clips)
- Family gate open rate: `0.0000` (`0` / `63` clips)
- Shot head invocation rate: `0.0000` (`0` / `63` clips)
- Dominant flat label: `Highlight` at `1.0000`
- Raw eventFamily=other rate: `1.0000`
- Uncertainty rate: `1.0000`
- Accepted-shot outcome accuracy: `N/A`
- Flat label distribution: `{"Highlight": 63}`
- EventFamily distribution: `{"other": 63}`
- Outcome distribution: `{"uncertain": 63}`
- Subtype distribution: `{"null": 63}`
- Source-domain distribution: `{"staging_hoopcut_demo_mixed_unlabeled": 30, "staging_hoopcut_known_made": 11, "staging_hoopcut_known_miss": 22}`
- Miss-vs-made confusion: `{"expectedMadePredictedHighlight": 0, "expectedMadePredictedMiss": 0, "expectedMissPredictedHighlight": 0, "expectedMissPredictedMadeShot": 0}`

## Calibration

- Harness acceptance calibration: `null`
- Harness eventness calibration: `null`
- Harness accepted-shot outcome calibration: `null`
- Raw proposal-score proxy, not promotion-grade calibrated probability:
  - scored clips: `33`
  - proxy Brier: `0.4139`
  - proxy ECE-lite: `0.5752`
  - proxy reliability buckets: `[{"accuracy": 1.0, "bin": "[0.0,0.2)", "count": 8, "meanScore": 0.0661, "risk": 0.0}, {"accuracy": 1.0, "bin": "[0.2,0.4)", "count": 14, "meanScore": 0.3563, "risk": 0.0}, {"accuracy": 1.0, "bin": "[0.4,0.6)", "count": 3, "meanScore": 0.5064, "risk": 0.0}, {"accuracy": null, "bin": "[0.6,0.8)", "count": 0, "meanScore": null, "risk": null}, {"accuracy": 1.0, "bin": "[0.8,1.0)", "count": 8, "meanScore": 0.8726, "risk": 0.0}]`
  - proxy coverage-vs-risk points: `[{"count": 1, "coverage": 0.0303, "risk": 0.0}, {"count": 2, "coverage": 0.0606, "risk": 0.0}, {"count": 3, "coverage": 0.0909, "risk": 0.0}, {"count": 4, "coverage": 0.1212, "risk": 0.0}, {"count": 5, "coverage": 0.1515, "risk": 0.0}]` ... `[{"count": 31, "coverage": 0.9394, "risk": 0.0}, {"count": 32, "coverage": 0.9697, "risk": 0.0}, {"count": 33, "coverage": 1.0, "risk": 0.0}]`

## Audit Pack Summary

- Audit queue: `services/inference/evals/phase4h_staging_eval/phase4h_audit_queue.json`
- Predicted-other clips queued: `63` / `63`
- Manual audit label distribution: `{"ambiguous_clip": 30, "real_event_missed_by_model": 33}`
- Split-other distribution: `{"ambiguous_event": 63}`
- Accepted proposals: `8`; all accepted proposals were known made-shot clips, but every one remained `eventFamily=other`, `familyGateOpen=false`, and `shotHeadInvoked=false`.

## Diagnosis

- Dominant failure mode: `family-gate suppression` with secondary `under-fire / rejection collapse`.
- Evidence for family-gate suppression: `proposalAcceptedCount=8` but `familyGateOpenCount=0` and `shotHeadInvocationCount=0`.
- Evidence for under-fire collapse: `proposalAcceptanceRate=0.127`, below the `0.35` lower bound.
- Evidence for flat-label collapse: `Highlight=63/63`, `eventFamily=other=63/63`, and `uncertaintyRate=1.0`.
- Accepted-shot outcome realism cannot be evaluated because no accepted proposal reached the shot head.

## Telemetry Gaps

- Calibrated acceptance probability is absent, so canonical Brier score, ECE-lite, reliability buckets, and coverage-vs-risk are unavailable from the current staged payload.
- Eventness calibration is absent from the staged payload.
- Accepted-shot outcome accuracy is not computable because shotHeadInvocationCount is 0.
- Explicit family-gate rejection reasons are absent even when accepted proposals are suppressed by the family gate.

## SpaceJam

- Skipped. No local SpaceJam manifest, annotations file, or clip root exists under `services/inference`, and this validation branch does not include the parked experiment runner.

## Commands

```bash
node --experimental-strip-types scripts/control-plane-shadow-batch.ts --base-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev --manifest /tmp/phase4h-staging-eval/manifest.json --output-dir /tmp/phase4h-staging-eval/batch --poll-timeout-seconds 240 --poll-interval-seconds 2
PYTHONPATH=. uv run --with-requirements services/inference/requirements.txt python3 services/inference/scripts/run_shadow_eval.py --batch-results /tmp/phase4h-staging-eval/batch/*.json --shadow-source runtimeFusionTemporalShadow --output-dir /tmp/phase4h-staging-eval/report
```

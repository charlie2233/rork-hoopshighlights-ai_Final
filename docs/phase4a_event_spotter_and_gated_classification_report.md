# Phase 4a Event Spotter And Gated Classification Report

## Summary

Phase 4a promoted event spotting to a first-class runtime task and gated outcome/subtype classification behind a likely-event decision. The branch was deployed to staging in shadow mode on Cloud Run revision `hoopsclips-inference-staging-00019-8jj` with runtime version `phase4a-event-spotter-and-gated-classification`.

The branch materially improved live mixed-batch behavior relative to phase 4:

- flat-label distribution improved from `Highlight 5 / Fast Break 3 / Dunk 1` to `Highlight 4 / Fast Break 3 / Layup 2`
- `Highlight` dominance improved from `55.56%` to `44.44%`
- `eventFamily=other` dominance improved from `55.56%` to `44.44%`
- `shot_attempt` separation improved from `1` clip to `2` clips
- uncertainty improved from `55.56%` to `0.00%`
- miss-to-`Made Shot` drift remained `0`

The branch still missed one required bar:

- `eventFamily other < 40%` was **not** met; live mixed batch landed at `44.44%`

Because of that, phase 4a is an operational success and a clear modeling improvement, but it does **not** fully clear acceptance yet.

## Runtime Changes

- Added phase-4 event-localization queue ingestion and stronger in-domain weighting in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/perception_supervision.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/perception_supervision.py)
- Reworked temporal-student training to add an explicit `eventSpotter` head, hard-negative-aware weighting, gated outcome loss, and event-spotting metrics in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_student.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_student.py)
- Updated runtime inference to gate outcome/subtype prediction on a confident event-spotter decision in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_student.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_student.py)
- Upgraded disagreement mining to prioritize runtime-missed likely events in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/build_disagreement_queue.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/build_disagreement_queue.py)
- Fixed shadow-report normalization so temporal spotter decisions are read from live `runtimeFusionTemporalShadow` payloads in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py)

## Deployment

- Cloud Run service: [https://hoopsclips-inference-staging-568888872909.us-central1.run.app](https://hoopsclips-inference-staging-568888872909.us-central1.run.app)
- Active revision: `hoopsclips-inference-staging-00019-8jj`
- Staging Worker: [https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev](https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev)
- Runtime mode: `runtimeModelMode=off`, `temporalEncoderMode=shadow`

## Validation

### Targeted regressions

- `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_student services.inference.tests.test_disagreement_queue services.inference.tests.test_perception_supervision services.inference.tests.test_pipeline services.inference.tests.test_shadow_eval`
- `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final services/inference/.venv/bin/python -m unittest services.inference.tests.test_shadow_eval`
- `npm --prefix services/control-plane run typecheck`

### Worker-path smoke

The first smoke attempt timed out at the script’s default `90s` poll window while the new revision was warming, but the job completed successfully in the Worker after the inference callback landed.

Clean rerun:

- jobId: `e66260c84ef54ca58a5f2afee9de759c`
- uploadTraceId: `a276249ff6eb4e3da94f4c1862793395`
- inferenceAttemptId: `347aee2dc90e45f681a94317ba06f390`
- final status: `completed`

Smoke observations:

- live app-facing result stayed backward-compatible as `Highlight`
- live hierarchy improved to `eventFamily=shot_attempt`, `shotSubtype=layup`, `outcome=uncertain`
- shadow temporal model produced:
  - `eventSpotter=shot_attempt`
  - `gateOpen=true`
  - `eventFamily=shot_attempt`
  - `shotSubtype=layup`
  - `outcomeDistribution made=0.4203 / uncertain=0.48`

### Mixed live shadow batch

- output dir: `/tmp/phase4a-batch/results`
- shadow report: [`/tmp/phase4a-batch/shadow-report/shadow_eval_report.md`](/tmp/phase4a-batch/shadow-report/shadow_eval_report.md)

Mixed-batch summary:

- clip count: `9`
- flat labels: `{"Fast Break": 3, "Highlight": 4, "Layup": 2}`
- event families: `{"other": 4, "shot_attempt": 2, "transition": 3}`
- outcomes: `{"made": 2, "uncertain": 7}`
- shot subtypes: `{"layup": 2, "null": 2, "unknown": 5}`
- uncertainty rate: `0.0000`
- `Highlight` dominance: `0.4444`
- `eventFamily=other` dominance: `0.4444`
- miss-vs-made confusion: `{"expectedMadePredictedHighlight": 0, "expectedMadePredictedMiss": 0, "expectedMissPredictedHighlight": 0, "expectedMissPredictedMadeShot": 0}`
- event-spotter precision / recall on labeled clips: `1.0 / 1.0`

Phase 4 -> Phase 4a comparison:

- highlight share delta: `-0.1111`
- spread score delta: `+0.1112`
- uncertainty delta: `-0.5556`
- baseline eventFamily distribution: `{"other": 5, "shot_attempt": 1, "transition": 3}`
- candidate eventFamily distribution: `{"other": 4, "shot_attempt": 2, "transition": 3}`

Representative collapse examples remained in the batch, including clips where raw VideoMAE still suggested `dunking basketball` or `shooting basketball` but the final flat label stayed `Highlight`. Those examples are captured in the generated shadow report.

### Simulator upload flow

- staging build succeeded against booted simulator `iPhone 16e (09C3102D-6824-4BA2-8CBE-F6348561F6E8)`
- app was installed and launched with automation env vars:
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_ENABLED=1`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_AUTH_MODE=guest`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_SAMPLE_VIDEO_PATH=/tmp/phase4-batch/clips/demo_02_8.0.mp4`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_AUTO_ANALYZE=1`
- final screenshot: [phase4a-ios-smoke-late.png](/tmp/phase4a-ios-smoke-late.png)

The final screenshot shows the Review screen with the live `Staging Debug Trace` card rendered correctly, confirming no regression in the app-path trace metadata surface.

## Acceptance Check

- `Highlight < 45%`: **pass** (`44.44%`)
- `eventFamily other < 40%`: **fail** (`44.44%`)
- meaningful eventFamily spread on mixed live clips: **pass**
- visible `shot_attempt` separation: **pass**
- no miss drift into `Made Shot`: **pass**
- no regression in smoke, simulator, or trace metadata: **pass**

## Decision

Phase 4a should remain in shadow mode only.

The event-spotter-and-gating design is the strongest live result so far and clearly improved the batch, but it still failed the `eventFamily other < 40%` acceptance bar. The remaining blocker is not infrastructure or control-plane compatibility; it is the residual `other` collapse on real mixed clips.

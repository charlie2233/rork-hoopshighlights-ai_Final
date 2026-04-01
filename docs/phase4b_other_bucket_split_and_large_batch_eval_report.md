# Phase 4b Other Bucket Split And Large Batch Eval Report

## Summary

Phase 4b kept the phase-4a event-spotter plus gated-classifier runtime architecture, split the internal `eventFamily=other` path into diagnostic sub-buckets, upgraded the disagreement queue for `other` and low-margin event cases, and ran a larger live shadow batch to determine whether the remaining collapse is mostly valid non-events or true missed basketball events.

This branch stayed backward-compatible on the live control-plane contract and remained shadow-only in staging.

The large-batch decision is clear:

- `Highlight` still dominated the batch at `69.64%`
- raw `eventFamily=other` landed at `42.86%`
- after manual audit of every predicted-`other` clip:
  - `66.67%` of `other` clips were **real events missed by the model**
  - `33.33%` were valid true-negative non-events
- miss-to-`Made Shot` drift stayed at `0`

Because most remaining `other` clips are true missed events, this branch indicates the current model family is the blocker. The next step should be a new model-family branch rather than more hardening on the current stack.

## Runtime / Eval Changes

- Added split-`other` diagnostic buckets to the temporal student runtime metadata in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_student.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_student.py)
- Extended shadow reporting with split-`other` distributions and manual audit overlays in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py)
- Upgraded disagreement-queue prioritization for `runtime_event_family_other`, low-margin event-family cases, and runtime-missed events in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/build_disagreement_queue.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/build_disagreement_queue.py)
- Added shadow-eval coverage for temporal-shadow event-family normalization and fallback clip IDs in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_shadow_eval.py)

Two eval-path correctness fixes were required during rollout:

- live batch result payloads did not include `clipId`, so manual audits needed a deterministic fallback ID of `jobId:clip-index`
- event-family normalization in the shadow report was incorrectly stripping underscores from `shot_attempt` and related labels, which would have overstated `other`

## Deployment

- Cloud Run service: [https://hoopsclips-inference-staging-568888872909.us-central1.run.app](https://hoopsclips-inference-staging-568888872909.us-central1.run.app)
- Active revision: `hoopsclips-inference-staging-00020-qw4`
- Runtime version: `phase4b-other-bucket-split-and-large-batch-eval`
- Staging Worker: [https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev](https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev)
- Runtime mode: `runtimeModelMode=off`, `temporalEncoderMode=shadow`

## Validation

### Targeted regressions

- `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_student services.inference.tests.test_disagreement_queue services.inference.tests.test_perception_supervision services.inference.tests.test_pipeline services.inference.tests.test_shadow_eval services.inference.tests.test_runtime_model services.inference.tests.test_structured_signals`
- `npm --prefix services/control-plane run typecheck`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'platform=iOS Simulator,id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' -derivedDataPath /tmp/HoopsClipsPhase4b CODE_SIGNING_ALLOWED=NO HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev build`

### Worker-path smoke

- jobId: `2fef73a60bba4cdabab6c5c0784af179`
- uploadTraceId: `0f2c220e60124058a86fdcbe871064e2`
- inferenceAttemptId: `0d0f7500480644e29f4577c555bea79a`
- final status: `completed`

Smoke observations:

- live shadow payload was present under `runtimeFusionTemporalShadow`
- hierarchical outputs and split-`other` diagnostics were available in the result artifact
- app-facing label contract remained unchanged

### Simulator upload flow

- staging app installed on simulator `iPhone 16e (09C3102D-6824-4BA2-8CBE-F6348561F6E8)`
- automation launch used:
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_ENABLED=1`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_AUTH_MODE=guest`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_SAMPLE_VIDEO_PATH=/Users/hanfei/rork-hoopshighlights-ai_Final/backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_AUTO_ANALYZE=1`
- screenshot: [phase4b-ios-smoke.png](/tmp/phase4b-ios-smoke.png)

OCR on the screenshot confirmed the app was on `Review` and the `Staging Debug Trace` card was visible with live trace fields rendered, including `requestId`, `uploadTraceId`, and `inferenceAttemptId`.

### Large live shadow batch

- batch size: `56` clips
- artifact dir: `/tmp/phase4b-large-batch/results`
- shadow report: [`/tmp/phase4b-large-batch/shadow-report/shadow_eval_report.md`](/tmp/phase4b-large-batch/shadow-report/shadow_eval_report.md)
- manual other-audit overlay: [`/tmp/phase4b-large-batch/other_audit.jsonl`](/tmp/phase4b-large-batch/other_audit.jsonl)

Mixed-batch summary:

- flat labels: `{"Fast Break": 8, "Highlight": 39, "Layup": 9}`
- event families: `{"other": 24, "shot_attempt": 24, "transition": 8}`
- split-other distribution: `{"ambiguous_event": 24}`
- outcomes: `{"made": 9, "missed": 8, "uncertain": 39}`
- shot subtypes: `{"jumper": 8, "layup": 16, "null": 8, "unknown": 24}`
- uncertainty rate: `0.2679`
- `Highlight` dominance: `0.6964`
- raw `eventFamily=other` dominance: `0.4286`
- event detection precision / recall: `0.5 / 0.5`
- eventFamily accuracy: `0.2857`
- miss-vs-made confusion: `{"expectedMadePredictedHighlight": 7, "expectedMadePredictedMiss": 0, "expectedMissPredictedHighlight": 0, "expectedMissPredictedMadeShot": 0}`

Manual audit for predicted-`other` clips:

- eligible predicted-`other` clips: `24`
- audited predicted-`other` clips: `24`
- audit distribution: `{"real_event_missed_by_model": 16, "true_negative_non_event": 8}`
- true model-miss rate within predicted-`other`: `0.6667`
- true negative rate within predicted-`other`: `0.3333`
- true model-miss share of full batch: `0.2857`
- true negative share of full batch: `0.1429`

Interpretation:

- the current stack is correctly identifying a meaningful non-event slice inside `other`
- but most of the remaining `other` bucket is still composed of real missed events, not benign setup/replay/dead-ball traffic
- the live flat-label collapse remains severe because many true events still end up as `Highlight`

## Acceptance Check

- `Highlight < 45%` on the larger batch: **fail** (`69.64%`)
- `eventFamily other < 40%` after split-other audit accounting: **diagnostic pass, overall fail**
  - raw `eventFamily=other`: `42.86%`
  - true missed-event share within full batch: `28.57%`
  - but flat-label `Highlight` still dominates the batch, so acceptance is not met
- no miss drift into `Made Shot`: **pass**
- smoke job still passes: **pass**
- simulator upload still reaches Review with live trace metadata: **pass**

## Decision

Phase 4b should **not** continue hardening the current model family as the main path.

The decisive signal from the audited larger batch is that most remaining `other` clips are true missed events, not valid non-events. That satisfies the branch decision rule for opening a new model-family branch.

Recommended next branch:

- `codex/phase4c-new-model-family-event-detector`

That follow-up should keep the current control-plane contract and staging path intact, but replace the current event-family detector with a stronger in-domain model family aimed at recovering the missed-event portion that still collapses into `Highlight` / `other`.

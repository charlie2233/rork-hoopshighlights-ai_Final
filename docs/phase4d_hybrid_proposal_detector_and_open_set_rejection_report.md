# Phase 4d Hybrid Proposal Detector And Open-Set Rejection Report

## Summary

Phase 4d kept `TriDet` as the first-stage temporal proposal generator and added a second-stage proposal rejector plus calibrated gated hierarchy heads for:

- `eventFamily`
- `outcome`
- `shotSubtype`

The intent was to stop the phase 4c failure mode where the temporal detector promoted weak or non-event clips into confident `shot_attempt / made / dunk` outputs.

The branch deployed cleanly to staging and all required validation paths completed:

- one Worker-path smoke job
- one mixed live shadow batch
- one simulator upload flow

The branch still failed acceptance.

Phase 4d did break the old `Highlight/other` collapse, but only by over-accepting every proposal. On the final live mixed batch:

- proposal acceptance rate was `1.0`
- rejector labeled every proposal `real_event`
- uncertainty collapsed to `0.0`
- accepted-shot outcome accuracy stayed at `0.3333`
- flat labels collapsed to `Dunk 6 / Fast Break 3`

So the phase 4d failure mode is not under-detection anymore. It is a total open-set rejection failure: the proposal stack accepted everything and pushed weak or non-event clips into confident basketball event labels.

The branch should remain shadow-only.

## Runtime Changes

- Reworked the temporal detector runtime bundle to emit proposal-stage metadata, run a proposal rejector, and gate hierarchy heads in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py)
- Added proposal-rejector training, export, and calibration flow in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py)
- Updated candidate training/export CLI to write the phase 4d detector bundle in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py)
- Extended live shadow report normalization to capture proposal acceptance, rejector labels, and calibration stats in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py)
- Updated the staging deploy bundle/version in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml)
- Refreshed the shipped temporal detector bundle in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json)
- Added regression coverage for proposal metrics and rejector behavior in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py) and [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_shadow_eval.py)

## Deployment

- Starting verified state: `8e73ae7`
- Cloud Build: `995ca103-11e9-4abd-886d-f68ac69740a0`
- Cloud Run service: [https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app](https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app)
- Active revision after rollout: `hoopsclips-inference-staging-00027-jpq`
- Runtime version: `phase4d-hybrid-proposal-detector-and-open-set-rejection`
- Staging Worker: [https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev](https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev)
- Runtime mode: `runtimeModelMode=off`, `temporalEncoderMode=shadow`

Important rollout note:

- Cloud Build finished successfully, but Cloud Run traffic was still pinned to the older `phase4c` revision after deploy.
- I manually routed staging traffic to `hoopsclips-inference-staging-00027-jpq`.
- After that cutover, `/version` returned `phase4d-hybrid-proposal-detector-and-open-set-rejection` and `/readyz` returned `ready`.

## Validation

### Targeted regressions

- `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_event_detector services.inference.tests.test_shadow_eval services.inference.tests.test_pipeline`
- `services/inference/.venv/bin/python services/inference/scripts/train_temporal_event_detector_candidates.py --output-dir /tmp/phase4d-candidates --write-models --write-model-architecture winner`
- `npm --prefix services/control-plane run typecheck`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'platform=iOS Simulator,id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' -derivedDataPath /tmp/HoopsClipsPhase4d CODE_SIGNING_ALLOWED=NO HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev build`

### Worker-path smoke

- artifact: [`/tmp/phase4d-smoke.json`](/tmp/phase4d-smoke.json)
- jobId: `78a3c6adb2844492a7b800404f03a790`
- uploadTraceId: `c2c58fd3388c45c4ba2a9198865305b1`
- inferenceAttemptId: `9e28dc403500431c945193d2a808fdae`
- final status: `completed`

Smoke observations:

- the Worker-path request completed end to end against the phase 4d revision
- the app-facing result stayed backward-compatible as `Highlight`
- live shadow metadata was present under `runtimeFusionTemporalShadow`
- the smoke clip’s shadow prediction was `Fast Break / transition / uncertain`
- the control-plane contract and trace IDs remained intact

### Mixed live shadow batch

Batch artifacts:

- batch summary: [`/tmp/phase4d-batch-run2/summary.json`](/tmp/phase4d-batch-run2/summary.json)
- shadow report markdown: [`/tmp/phase4d-batch-run2/shadow-report/shadow_eval_report.md`](/tmp/phase4d-batch-run2/shadow-report/shadow_eval_report.md)
- shadow report json: [`/tmp/phase4d-batch-run2/shadow-report/shadow_eval_report.json`](/tmp/phase4d-batch-run2/shadow-report/shadow_eval_report.json)

This turn used the only local basketball clips available in-repo at runtime:

- `make_2_3.20s.mp4`
- `miss_2_3.13s.mp4`
- `miss_1_0.00s.mp4`

Those three clips were repeated into a 9-item shadow batch to validate proposal acceptance, rejector behavior, and gated outcome precision consistently on staging.

Mixed-batch summary:

- clip count: `9`
- flat labels: `{"Dunk": 6, "Fast Break": 3}`
- event families: `{"shot_attempt": 6, "transition": 3}`
- outcomes: `{"made": 6, "uncertain": 3}`
- shot subtypes: `{"dunk": 6, "layup": 1, "null": 2}`
- proposal acceptance rate: `1.0`
- eventness calibration: `{"brierScore": 0.2564, "eligibleClips": 9, "negativeMeanScore": 0.8497, "positiveMeanScore": 0.8469}`
- uncertainty rate: `0.0`
- accepted-shot proposal outcome accuracy: `0.3333`
- `Highlight` dominance: `0.0`
- `eventFamily=other` dominance: `0.0`
- event detection precision / recall: `0.6667 / 1.0`
- eventFamily accuracy: `0.3333`
- outcome accuracy: `0.2222`
- shot subtype accuracy: `0.3333`
- rejected proposal audit: `0` rejected clips

Representative per-clip failure pattern:

- expected `shot_attempt / missed / layup` clips were split between:
  - `shot_attempt / made / dunk / Dunk`
  - `transition / uncertain / null / Fast Break`
- expected `other / uncertain / null` clips were promoted to:
  - `shot_attempt / made / dunk / Dunk`

That means the proposal rejector did not create meaningful open-set rejection at all:

- all `9/9` proposals were accepted
- all `9/9` proposals were labeled `real_event`
- there were no rejected proposals to audit as true non-events vs true misses

This is worse than a residual `Highlight/other` collapse because the runtime now emits confident positive basketball labels on weak and non-event clips.

### Simulator upload flow

- simulator: `iPhone 16e (09C3102D-6824-4BA2-8CBE-F6348561F6E8)`
- screenshot: [phase4d-ios-smoke.png](/tmp/phase4d-ios-smoke.png)

The final screenshot shows:

- the app on `Review`
- the `Staging Debug Trace` card rendered
- live `requestId`
- live `uploadTraceId`
- live `inferenceAttemptId`
- live `modelVersion`

No app-path regression was observed.

## Acceptance Check

- no collapse to a single confident positive label: **fail**
  - the batch produced `2` labels, but both were confident positive basketball labels and `Dunk` still dominated at `66.67%`
- `Highlight < 50%`: **pass technically** (`0.0%`)
  - this is not a real win because the model stopped using `Highlight` by over-promoting clips into `Dunk` and `Fast Break`
- `eventFamily other < 40%`: **pass technically** (`0.0%`)
  - this is also a false win because non-event clips were not rejected; they were promoted into `shot_attempt`
- materially better `shot_attempt` precision than phase 4c: **fail**
  - open-set precision did not improve; non-event clips still became accepted `shot_attempt` events
- outcome accuracy on accepted shot proposals improves over `0.333`: **fail** (`0.3333`)
- uncertainty no longer collapses to `0.0`: **fail** (`0.0`)
- no smoke/simulator regression: **pass**

Overall acceptance: **fail**

## Decision

Phase 4d should remain in shadow mode only.

It did not solve the phase 4c failure mode. It just redirected it:

- phase 4c collapsed into confident `shot_attempt / made / dunk` directly
- phase 4d collapses by accepting every proposal and then confidently flattening most clips to `Dunk`

The remaining blocker is not rollout, control-plane compatibility, or iOS integration. It is the lack of a functioning precision gate:

- proposal eventness scores do not separate positives from negatives meaningfully
- proposal rejector never rejects
- uncertainty is fully collapsed
- accepted-shot outcome accuracy does not improve

If work continues after phase 4d, the next branch should focus on a stronger verifier or true open-set rejection path rather than more threshold tuning around the current rejector.

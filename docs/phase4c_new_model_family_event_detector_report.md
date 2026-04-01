# Phase 4c New Model Family Event Detector Report

## Summary

Phase 4c replaced the prior event-spotter family with a true temporal detector path and compared two candidates:

- Candidate A: `ActionFormer`-style temporal detector
- Candidate B: `TriDet`-style temporal detector

Both candidates ran over fused basketball inputs from structured signals, perception features, and event-localization features while preserving the current control-plane contract and the existing gated hierarchy:

- `eventFamily`
- `outcome`
- `shotSubtype`

The branch also fixed one important modeling leak before rollout: the detector was initially consuming the current runtime flat-label and hierarchy outputs as direct features, which would have baked the old `Highlight/other` collapse back into the new spotter. Those runtime-derived label features were removed from the detector input set before the final candidate export and staging rollout.

The final offline winner was `TriDet`, and staging rollout completed successfully on Cloud Run revision `hoopsclips-inference-staging-00022-hqf`.

The live result still failed acceptance.

The new detector eliminated the old `Highlight/other` collapse on the narrow repeated-clip shadow batch used in this turn, but it replaced it with a worse failure mode:

- every clip was promoted to `eventFamily=shot_attempt`
- every clip was promoted to `outcome=made`
- every clip was flattened to `Dunk`

That means phase 4c produced a false-positive explosion rather than a usable event detector. The branch remains shadow-only.

## Runtime Changes

- Added the new detector runtime bundle in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py)
- Added detector training, calibration, export, and offline comparison in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py)
- Added candidate training/export CLI in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py)
- Integrated temporal-detector bundle loading into the live inference pipeline in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/pipeline.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/pipeline.py)
- Pointed staging temporal shadow mode at the new detector bundle in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/config.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/config.py) and [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml)
- Extended shadow reporting to normalize the new detector metadata in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py)
- Added detector coverage in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py)

## Offline Candidate Comparison

Final comparison output:

- report: [`/tmp/phase4c-candidates/comparison_report.md`](/tmp/phase4c-candidates/comparison_report.md)
- json: [`/tmp/phase4c-candidates/comparison_report.json`](/tmp/phase4c-candidates/comparison_report.json)
- exported runtime bundle: [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json)

Offline summary after removing runtime-label leakage:

- baseline temporal-student:
  - `eventFamilyAccuracy=1.0`
  - `eventDetectionPrecision/Recall=1.0 / 1.0`
  - `highlightDominance=0.5455`
  - `otherDominance=0.4545`
- `ActionFormer`:
  - `eventFamilyAccuracy=0.9091`
  - `eventDetectionPrecision/Recall=1.0 / 0.8333`
  - `highlightDominance=0.6364`
  - `otherDominance=0.5455`
- `TriDet`:
  - `eventFamilyAccuracy=1.0`
  - `eventDetectionPrecision/Recall=1.0 / 1.0`
  - `highlightDominance=0.4545`
  - `otherDominance=0.4545`
  - `uncertaintyRate=0.0`

Selected runtime candidate:

- detector family: `tridet`
- model version: `temporal-event-detector-tridet-v1`

Important caveat:

- the offline winner still showed poor subtype behavior and over-predicted `dunk`
- offline comparison alone was not strong enough to justify promotion; live shadow rollout was still required

## Deployment

- Cloud Run service: [https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app](https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app)
- Active revision: `hoopsclips-inference-staging-00022-hqf`
- Runtime version: `phase4c-new-model-family-event-detector`
- Staging Worker: [https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev](https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev)
- Runtime mode: `runtimeModelMode=off`, `temporalEncoderMode=shadow`

## Validation

### Targeted regressions

- `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_event_detector services.inference.tests.test_temporal_student services.inference.tests.test_pipeline services.inference.tests.test_shadow_eval`
- `npm --prefix services/control-plane run typecheck`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'platform=iOS Simulator,id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' -derivedDataPath /tmp/HoopsClipsPhase4c CODE_SIGNING_ALLOWED=NO HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev build`

### Worker-path smoke

- artifact: [`/tmp/phase4c-smoke.json`](/tmp/phase4c-smoke.json)
- jobId: `3f74780da499461abb010fe6e3eefb4f`
- uploadTraceId: `820f48331f514e1daea975690af8eb15`
- inferenceAttemptId: `5be42e9dae464a0f89ec9a729d7d25f3`
- final status: `completed`

Smoke observations:

- the Worker-path request completed end to end against the new revision
- live trace IDs were populated correctly
- the control-plane contract remained unchanged

### Simulator upload flow

- simulator: `iPhone 16e (09C3102D-6824-4BA2-8CBE-F6348561F6E8)`
- screenshot: [phase4c-ios-smoke.png](/tmp/phase4c-ios-smoke.png)

The final screenshot shows:

- the app on `Review`
- the `Staging Debug Trace` card rendered
- live `requestId`
- live `uploadTraceId`
- live `inferenceAttemptId`
- live `modelVersion`

No app-path regression was observed.

### Mixed live shadow batch

Batch artifacts:

- batch summary: [`/tmp/phase4c-batch/summary.json`](/tmp/phase4c-batch/summary.json)
- clean shadow report markdown: [`/tmp/phase4c-batch/shadow-report-clean/shadow_eval_report.md`](/tmp/phase4c-batch/shadow-report-clean/shadow_eval_report.md)
- clean shadow report json: [`/tmp/phase4c-batch/shadow-report-clean/shadow_eval_report.json`](/tmp/phase4c-batch/shadow-report-clean/shadow_eval_report.json)

Important eval note:

- the first shadow-report glob accidentally picked up stale result files already present in `/tmp/phase4c-batch/results`
- the final decision below is based only on the explicit output paths recorded in the current batch summary

This turn’s live batch used the only local basketball clips available in the repo at runtime:

- `make_2_3.20s.mp4`
- `miss_2_3.13s.mp4`
- `miss_1_0.00s.mp4`

Those three clips were repeated into a 9-item shadow batch to validate the fresh `TriDet` detector consistently on staging.

Clean mixed-batch summary:

- clip count: `9`
- flat labels: `{"Dunk": 9}`
- event families: `{"shot_attempt": 9}`
- outcomes: `{"made": 9}`
- shot subtypes: `{"dunk": 9}`
- uncertainty rate: `0.0`
- `Highlight` dominance: `0.0`
- `eventFamily=other` dominance: `0.0`
- event detection precision / recall: `1.0 / 1.0`
- eventFamily accuracy: `1.0`
- outcome accuracy: `0.3333`
- miss-vs-made confusion: `{"expectedMissPredictedMadeShot": 0, "expectedMissPredictedHighlight": 0, "expectedMadePredictedHighlight": 0, "expectedMadePredictedMiss": 0}`
- label spread: `1` unique flat label

Interpretation:

- the detector no longer collapsed this narrow batch to `Highlight/other`
- but it over-fired catastrophically into one concrete label family
- both miss clips were incorrectly promoted to `shot_attempt / made / dunk`
- this is worse than the old collapse because it introduces a strong false-positive basketball semantics bias instead of preserving uncertainty

## Acceptance Check

- `Highlight < 50%`: **pass** (`0.0%`)
- `eventFamily other < 40%`: **pass** (`0.0%`)
- clear `shot_attempt` separation: **pass**, but only because the detector predicted `shot_attempt` for everything
- fewer audited true missed events inside predicted-`other`: **pass trivially** (`0` predicted-`other` clips)
- no miss drift into `Made Shot`: **pass technically**, but **practical fail** because misses drifted into `made / dunk`
- no smoke/simulator regression: **pass**

Overall acceptance: **fail**

The branch did not produce a usable detector. It traded the old `Highlight/other` collapse for an all-positive `Dunk` collapse.

## Decision

Phase 4c should remain in shadow mode only.

The new detector family did prove that the old `Highlight/other` behavior can be broken, but the resulting model is not safe or reliable enough to promote:

- label spread collapsed to a single flat label
- miss clips lost outcome separation
- all clips were promoted to `made / dunk`

The blocker after phase 4c is no longer “can the runtime find events at all?” It is “can the detector stay calibrated and preserve outcome realism once it starts firing aggressively?”

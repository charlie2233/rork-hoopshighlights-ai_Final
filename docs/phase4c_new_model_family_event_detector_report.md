# Phase 4c New Model Family Event Detector Report

## Summary

Phase 4c replaced the prior temporal-student event spotter family with a new temporal event detector family while keeping the live control-plane contract unchanged and preserving the gated hierarchical runtime path.

This branch implemented and compared two detector candidates over the existing fused basketball inputs:

- Candidate A: `ActionFormer`-style temporal detector
- Candidate B: `TriDet`-style temporal detector

The winning offline candidate, `ActionFormer`, was deployed to staging in shadow mode as `temporal-event-detector-actionformer-v1` through the existing `runtimeFusionTemporalShadow` namespace.

The operational rollout succeeded:

- Cloud Run deployed revision `hoopsclips-inference-staging-00021-nk9`
- the staging Worker path stayed healthy
- the Worker-path smoke completed
- the simulator upload flow reached `Review` and rendered the live staging trace card

The model result still failed the phase acceptance bar.

On the completed serialized live shadow batch:

- flat labels: `{"Highlight": 2, "Fast Break": 1}`
- `Highlight` dominance: `0.6667`
- event families: `{"other": 2, "transition": 1}`
- `eventFamily=other` dominance: `0.6667`
- outcomes: `{"uncertain": 3}`
- miss-to-`Made Shot` drift: `0`
- audited predicted-`other` clips: `2/2` were real missed events, not true negatives

That means phase 4c verified the new detector family was actually deployed and active, but it still missed too many real basketball events and continued collapsing them into `Highlight` / `other`.

## Runtime Changes

- Added the new runtime detector bundle in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py)
- Added detector-family training and evaluation in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py)
- Added the candidate training/export script in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/train_temporal_event_detector_candidates.py)
- Integrated detector-bundle loading into [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/pipeline.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/pipeline.py)
- Updated config defaults in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/config.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/config.py)
- Updated shadow-report normalization in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py)
- Wrote the exported detector bundle to [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json)
- Added unit coverage in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py)
- Updated Cloud Run deploy config in [`/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml)

## Offline Candidate Comparison

The phase4c candidate trainer wrote:

- comparison markdown: [`/tmp/phase4c-candidates/comparison_report.md`](/tmp/phase4c-candidates/comparison_report.md)
- comparison json: [`/tmp/phase4c-candidates/comparison_report.json`](/tmp/phase4c-candidates/comparison_report.json)

`ActionFormer` won the internal candidate comparison, but the detector-family path still underperformed the prior temporal-student baseline offline on event-family fidelity. That was already a warning sign before live rollout.

## Deployment

- Cloud Run service: [https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app](https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app)
- Active revision: `hoopsclips-inference-staging-00021-nk9`
- Runtime version: `phase4c-new-model-family-event-detector`
- Temporal bundle path: `/app/services/inference/models/temporal_event_detector_v1.json`
- Staging Worker: [https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev](https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev)
- Runtime mode: `runtimeModelMode=off`, `temporalEncoderMode=shadow`

## Validation

### Local regressions

- `services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_event_detector services.inference.tests.test_temporal_student services.inference.tests.test_pipeline services.inference.tests.test_shadow_eval`
- `npm --prefix services/control-plane run typecheck`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO`

### Worker-path smoke

- jobId: `2c4ce1dba647479ca0e93ed98d4da438`
- uploadTraceId: `fb645caf282b428fbe8f3397df678f32`
- inferenceAttemptId: `4c97428e5e3044f8b91f3e5bd7f67e6c`
- final status: `completed`
- artifact: [`/tmp/phase4c-live/smoke.json`](/tmp/phase4c-live/smoke.json)

Smoke notes:

- the live staging path completed end to end through the Worker
- the clip finished with app-facing label `Highlight` on the made-dunk sample
- the detailed live shadow artifact showed `runtimeFusionTemporalShadow.modelVersion = temporal-event-detector-actionformer-v1`, confirming the new detector family was active on staging

### Simulator upload flow

- simulator: `iPhone 16e (09C3102D-6824-4BA2-8CBE-F6348561F6E8)`
- automation launch used:
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_ENABLED=1`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_AUTH_MODE=guest`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_SAMPLE_VIDEO_PATH=/Users/hanfei/rork-hoopshighlights-ai_Final/backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4`
  - `SIMCTL_CHILD_HOOPS_AUTOMATION_AUTO_ANALYZE=1`
- screenshot: [`/tmp/phase4c-live/ios-smoke.png`](/tmp/phase4c-live/ios-smoke.png)

The screenshot confirms:

- the app reached `Review`
- the `Staging Debug Trace` card was visible
- live `requestId`, `uploadTraceId`, `inferenceAttemptId`, `modelVersion`, and `failureReason` fields were rendered

### Live shadow batch

Staging throughput became the limiting factor during broader back-to-back dispatch:

- a larger repeated batch hit `429 Rate exceeded` on the sixth request
- a second multi-item mixed batch also stalled under the same staging-throughput constraint

To keep the decision grounded in completed live results instead of partial failures, the official phase4c shadow evaluation used a completed serialized mixed batch of three real staging/product-path clips:

- made-dunk clip
- missed-layup clip
- transition clip

Artifacts:

- batch result dir: [`/tmp/phase4c-live/final3-results`](/tmp/phase4c-live/final3-results)
- audit overlay: [`/tmp/phase4c-live/final3-other-audit.jsonl`](/tmp/phase4c-live/final3-other-audit.jsonl)
- shadow report markdown: [`/tmp/phase4c-live/final3-shadow-report/shadow_eval_report.md`](/tmp/phase4c-live/final3-shadow-report/shadow_eval_report.md)
- shadow report json: [`/tmp/phase4c-live/final3-shadow-report/shadow_eval_report.json`](/tmp/phase4c-live/final3-shadow-report/shadow_eval_report.json)

Completed-batch summary:

- clip count: `3`
- flat labels: `{"Fast Break": 1, "Highlight": 2}`
- event families: `{"other": 2, "transition": 1}`
- shot subtypes: `{"layup": 1, "null": 1, "unknown": 1}`
- outcomes: `{"uncertain": 3}`
- uncertainty rate: `0.0000`
- `Highlight` dominance: `0.6667`
- `eventFamily=other` dominance: `0.6667`
- event detection precision / recall: `1.0 / 0.3333`
- event family accuracy: `0.0`
- miss-vs-made confusion: `{"expectedMadePredictedHighlight": 1, "expectedMadePredictedMiss": 0, "expectedMissPredictedHighlight": 0, "expectedMissPredictedMadeShot": 0}`

Audited predicted-`other` clips:

- eligible predicted-`other` clips: `2`
- audited predicted-`other` clips: `2`
- audit distribution: `{"real_event_missed_by_model": 2}`
- true model-miss rate within predicted-`other`: `1.0`
- true model-miss share of batch: `0.6667`

Per-clip behavior on the completed live batch:

- made dunk: predicted `other` -> `Highlight`
- missed layup: predicted `transition` -> `Fast Break`
- true transition: predicted `other` -> `Highlight`

## Comparison vs Phase 4b Baseline

Using the phase4b large-batch shadow artifacts as the baseline comparison:

- baseline `Highlight` dominance: `0.6964`
- phase4c completed-batch `Highlight` dominance: `0.6667`
- baseline `eventFamily=other` dominance: `0.4286`
- phase4c completed-batch `eventFamily=other` dominance: `0.6667`
- baseline mixed-batch unique labels: `3`
- phase4c completed-batch unique labels: `2`
- baseline uncertainty rate: `0.2679`
- phase4c completed-batch uncertainty rate: `0.0000`

Interpretation:

- the new detector reduced uncertainty by becoming confidently wrong
- it did not recover better shot-attempt separation
- it worsened the concentration of predicted `other` on the completed live batch
- the predicted-`other` audit confirms those `other` clips were true missed events, not benign non-events

## Acceptance Check

- `Highlight < 50%`: **fail** (`66.67%`)
- `eventFamily other < 40%`: **fail** (`66.67%`)
- clear shot-attempt separation: **fail**
- fewer audited true missed events inside predicted-`other`: **fail**
- no miss drift into `Made Shot`: **pass**
- no smoke regression: **pass**
- no simulator / trace-metadata regression: **pass**

## Decision

Phase 4c should be treated as a model-family rollout that **verified activation but failed quality**.

What succeeded:

- the new temporal detector family was trained, exported, deployed, and surfaced live in shadow metadata
- staging infra, Worker callback flow, and iOS Review trace rendering all remained intact

What failed:

- the detector still missed real events and collapsed them into `Highlight` / `other`
- the completed live shadow batch did not meet the acceptance bar
- audited predicted-`other` clips were still true model misses

Recommended follow-up:

- proceed to the next branch focused on the next detector family or a stronger in-domain event-localization model, rather than more threshold or prompt tuning on this detector path

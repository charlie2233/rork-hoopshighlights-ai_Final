# Phase 4d: Hybrid Proposal Detector And Open-Set Rejection

## Goal

Keep TriDet as a high-recall temporal proposal generator, add a proposal rejector plus calibrated gated classifiers, and verify on live staging whether the runtime stops collapsing into confident `dunk/made` predictions on non-events and weak events.

## Branch And Deploy

- Branch: `codex/phase4d-hybrid-proposal-detector-and-open-set-rejection`
- Verified base: `8e73ae7`
- Cloud Build: `995ca103-11e9-4abd-886d-f68ac69740a0`
- Cloud Run service: `hoopsclips-inference-staging`
- Cloud Run revision: `hoopsclips-inference-staging-00027-jpq`
- Cloud Run URL: `https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app`
- Inference version: `phase4d-hybrid-proposal-detector-and-open-set-rejection`
- Worker URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Runtime mode on staging: `shadow`

## What Changed

- TriDet is kept as the temporal proposal stage only.
- A phase4d proposal rejector is added with labels:
  - `real_event`
  - `non_event`
  - `setup`
  - `dead_ball`
  - `replay_or_reaction`
  - `ambiguous`
- Hierarchical heads stay gated behind proposal acceptance:
  - `eventFamily`
  - `outcome`
  - `shotSubtype`
- Calibration surfaces were added or updated for:
  - proposal eventness
  - proposal rejector
  - outcome head
- Shadow eval reporting now includes:
  - proposal acceptance rate
  - eventness calibration
  - accepted-shot outcome accuracy
  - rejected-proposal audit

## Validation

### Local Validation

- `services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_event_detector services.inference.tests.test_shadow_eval services.inference.tests.test_pipeline`
- `services/inference/.venv/bin/python services/inference/scripts/train_temporal_event_detector_candidates.py --output-dir /tmp/phase4d-candidates --write-models --write-model-architecture winner`
- `npm --prefix services/control-plane run typecheck`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'platform=iOS Simulator,id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' -derivedDataPath /tmp/HoopsClipsPhase4d CODE_SIGNING_ALLOWED=NO HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev build`

### Staging Health

- `/version` returned `phase4d-hybrid-proposal-detector-and-open-set-rejection`
- `/readyz` returned `ready`

### Worker Smoke

- Smoke job completed through the Worker path
- `jobId`: `3ae6c1950c404a788a56169f8e48598d`
- `uploadTraceId`: `d0e1e7ce8c094e2199cc8481d7976aa9`
- `inferenceAttemptId`: `3f09e565667e45978f72d19a352c7059`
- Final app-facing clip label remained `Highlight`
- Control-plane callback and trace hydration remained healthy

### Simulator Upload

- Simulator automation completed successfully against staging
- Review rendered the live `Staging Debug Trace` card
- Screenshot: ![phase4d iOS smoke](/tmp/phase4d-ios-smoke.png)

### Mixed Live Shadow Batch

- Batch size: `9`
- Result files: `/tmp/phase4d-batch/results/*.json`
- Shadow report:
  - [shadow_eval_report.md](/tmp/phase4d-batch/shadow-report/shadow_eval_report.md)
  - [shadow_eval_report.json](/tmp/phase4d-batch/shadow-report/shadow_eval_report.json)

## Shadow Metrics

- Flat label distribution: `{"Dunk": 9}`
- Event family distribution: `{"shot_attempt": 9}`
- Outcome distribution: `{"made": 9}`
- Shot subtype distribution: `{"dunk": 9}`
- Proposal acceptance rate: `1.0`
- Accepted-shot proposal outcome accuracy: `0.5`
- Eventness calibration:
  - `brierScore = 0.2694`
  - `positiveMeanScore = 0.8732`
  - `negativeMeanScore = 0.8808`
- Event detection precision / recall: `0.6667 / 1.0`
- Event spotter precision / recall: `0.6667 / 1.0`
- Uncertainty rate: `0.0`
- Highlight dominance: `0.0`
- EventFamily=`other` dominance: `0.0`
- Rejected proposal audit: no rejected proposals (`0/9`)
- Miss-vs-made confusion artifact: `expectedMissPredictedMadeShot = 0`

## Interpretation

Phase 4d removed the old `Highlight/other` collapse, but it did not solve the real failure mode. The runtime shifted into a different pathological mode:

- every shadow clip was accepted as a proposal
- every accepted proposal was verified as `real_event`
- every clip became `shot_attempt`
- every clip became `made`
- every clip became `dunk`
- uncertainty collapsed back to `0.0`

That means the proposal rejector and gated hierarchy did not create meaningful open-set rejection on this live batch. The model is still over-trusting weak or wrong proposals and then confidently forcing a single positive basketball outcome.

## Acceptance Check

- No collapse to a single confident positive label: failed
- `Highlight < 50%`: passed, but only because all clips collapsed to `Dunk`
- `eventFamily other < 40%`: passed, but only because all clips collapsed to `shot_attempt`
- Materially better shot-attempt precision than phase4c: not achieved on live behavior
- Outcome accuracy on accepted shot proposals > `0.333`: passed (`0.5`)
- Uncertainty no longer collapses to `0.0`: failed
- No smoke/simulator regression: passed

## Decision

Do not promote phase4d beyond shadow.

The infra and contract are healthy, but the model behavior is still not safe enough for live labels. The phase4d verifier did not reject enough proposals and allowed a full-batch `dunk/made` collapse. The next iteration needs stronger rejection supervision and/or stricter open-set behavior on near-event negatives before this stack is promotable.

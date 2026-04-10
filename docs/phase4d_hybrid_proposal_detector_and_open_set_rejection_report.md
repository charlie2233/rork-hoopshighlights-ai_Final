# Phase 4d: Hybrid Proposal Detector and Open-Set Rejection

Branch: `codex/phase4d-hybrid-proposal-detector-and-open-set-rejection`

Base verified state: `8e73ae7`

## Goal

Keep TriDet as a high-recall temporal proposal generator, add a proposal rejector plus calibrated gated hierarchy, and validate the combined stack on live staging in shadow mode without changing the control-plane contract.

## Code Changes

- Kept TriDet / ActionFormer as proposal generators only at runtime and moved final hierarchy behind proposal acceptance in [services/inference/app/runtime_models/temporal_event_detector.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py).
- Added second-stage proposal rejector training, export, and calibration in [services/inference/training/temporal_event_detector.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py).
- Extended shadow reporting with proposal acceptance, rejector outputs, and eventness calibration in [services/inference/scripts/run_shadow_eval.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py).
- Updated the deployed temporal bundle in [services/inference/models/temporal_event_detector_v1.json](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json).
- Kept staging rollout in shadow mode through [services/inference/cloudbuild.yaml](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml).

## Validation

### Local validation

- `services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_event_detector services.inference.tests.test_shadow_eval services.inference.tests.test_pipeline`
- `services/inference/.venv/bin/python services/inference/scripts/train_temporal_event_detector_candidates.py --output-dir /tmp/phase4d-candidates --write-models --write-model-architecture winner`
- `npm --prefix services/control-plane run typecheck`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'platform=iOS Simulator,id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' -derivedDataPath /tmp/HoopsClipsPhase4d CODE_SIGNING_ALLOWED=NO HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev build`

All of the above passed.

### Staging deploy

- Cloud Build: `995ca103-11e9-4abd-886d-f68ac69740a0`
- Cloud Run revision: `hoopsclips-inference-staging-00027-jpq`
- Cloud Run URL: [https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app](https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app)
- `/version` returned `phase4d-hybrid-proposal-detector-and-open-set-rejection`
- `/readyz` returned `ready`

### Worker-path smoke

- Job: `3ae6c1950c404a788a56169f8e48598d`
- Upload trace: `d0e1e7ce8c094e2199cc8481d7976aa9`
- Inference attempt: `3f09e565667e45978f72d19a352c7059`
- Final status: `completed`
- Result: `1` clip, shipped flat label `Highlight`, duration `4.5s`

### Simulator upload

- Built app path: `/tmp/HoopsClipsPhase4d/Build/Products/Staging-iphonesimulator/HoopsClips.app`
- Booted simulator: `iPhone 16e (09C3102D-6824-4BA2-8CBE-F6348561F6E8)`
- Late screenshot confirming Review + trace metadata: ![phase4d iOS smoke](/tmp/phase4d-ios-smoke-late.png)
- Visible trace card fields on Review:
  - requestId `22954c640b3b4e7aaba92028c2a2d9ce`
  - uploadTraceId `6c4f2c93973f47b79676a8c9f8179e51`
  - inferenceAttemptId `d09654bc1b2e409582e4b8df963f3142`

### Mixed live shadow batch

- Manifest size: `9` clips
- Output dir: `/tmp/phase4d-batch/results`
- Shadow report: `/tmp/phase4d-batch/shadow-report/shadow_eval_report.md`

Summary from `/tmp/phase4d-batch/shadow-report/shadow_eval_report.json`:

- Flat label distribution: `{"Dunk": 9}`
- EventFamily distribution: `{"shot_attempt": 9}`
- Outcome distribution: `{"made": 9}`
- ShotSubtype distribution: `{"dunk": 9}`
- Proposal acceptance rate: `1.0`
- Eventness calibration: `{"brierScore": 0.2694, "eligibleClips": 9, "negativeMeanScore": 0.8808, "positiveMeanScore": 0.8732}`
- Uncertainty rate: `0.0`
- Outcome accuracy on accepted shot proposals: `0.5`
- Highlight dominance: `0.0`
- EventFamily=`other` dominance: `0.0`
- Rejected proposal audit: no proposals were rejected
- Mixed-batch label spread: `1` unique label, `Dunk` at `100%`

Representative failure cases:

- Expected made dunk clip stayed `Dunk` / `shot_attempt` / `made`, which is acceptable.
- Expected miss layup clips were still labeled `Dunk` / `shot_attempt` / `made`.
- Expected `other` / uncertain clips were also labeled `Dunk` / `shot_attempt` / `made`.

## Verdict

Phase 4d failed the branch goal.

What improved:

- Accepted-shot outcome accuracy improved from the phase4c live value of `0.3333` to `0.5`.
- The control-plane contract stayed intact.
- Worker smoke, simulator upload, Review trace metadata, and shadow reporting all remained healthy.

What failed:

- The live shadow batch still collapsed to a single confident positive label.
- Uncertainty still collapsed to `0.0`.
- The proposal rejector did not reject any proposal on the mixed batch.
- Eventness remained poorly discriminative on live data: the mean proposal score for negatives (`0.8808`) was slightly higher than for positives (`0.8732`).
- The branch eliminated the phase4c `Highlight/other` failure only by replacing it with universal `Dunk/made`.

Acceptance criteria result:

- `no collapse to a single confident positive label`: failed
- `Highlight < 50%`: passed trivially but not meaningful
- `eventFamily other < 40%`: passed trivially but not meaningful
- `materially better shot_attempt precision than phase4c`: failed in practice
- `outcome accuracy on accepted shot proposals improves over 0.333`: passed (`0.5`)
- `uncertainty no longer collapses to 0.0`: failed
- `no smoke/simulator regression`: passed

## Decision

Keep phase4d in shadow mode only. It is not promotable. The remaining blocker is model behavior, not staging infrastructure or control-plane integration.

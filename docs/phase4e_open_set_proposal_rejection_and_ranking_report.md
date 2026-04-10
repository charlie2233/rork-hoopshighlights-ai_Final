# Phase 4e: Open-Set Proposal Rejection and Ranking

Branch: `codex/phase4e-open-set-proposal-rejection-and-ranking`

Base verified state: `8bab1e9`

## Goal

Keep `TriDet` as the high-recall temporal proposal engine, add a proposal-level open-set verifier plus proposal ranking and direct acceptance calibration, and validate whether that stack can stop the live runtime from accepting every proposal and collapsing into one confident positive basketball label.

## Code Changes

- Added proposal-level acceptance calibration and acceptance-aware shadow metadata in [services/inference/app/runtime_models/temporal_event_detector.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/runtime_models/temporal_event_detector.py).
- Added proposal acceptor training, calibration, open-set label heuristics, and stronger hard-negative weighting in [services/inference/training/temporal_event_detector.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_event_detector.py).
- Extended temporal training examples with event-localization timestamps in [services/inference/training/temporal_student.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_student.py).
- Updated shadow evaluation to score proposal acceptance from the calibrated acceptance signal instead of raw proposal eventness in [services/inference/scripts/run_shadow_eval.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_shadow_eval.py).
- Added phase4e bundle / round-trip coverage in [services/inference/tests/test_temporal_event_detector.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/tests/test_temporal_event_detector.py).
- Added additive control-plane compatibility coverage for shadow-only proposal verifier / ranker / acceptor fields in [services/control-plane/test/control-plane-structured-metadata.test.ts](/Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane/test/control-plane-structured-metadata.test.ts).
- Regenerated the deployed temporal detector bundle in [services/inference/models/temporal_event_detector_v1.json](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_event_detector_v1.json).

## Validation

### Local validation

- `services/inference/.venv/bin/python -m unittest services.inference.tests.test_temporal_event_detector services.inference.tests.test_shadow_eval services.inference.tests.test_pipeline`
- `npx tsx --test services/control-plane/test/control-plane-structured-metadata.test.ts`
- `npm --prefix services/control-plane run typecheck`
- `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final services/inference/.venv/bin/python services/inference/scripts/train_temporal_event_detector_candidates.py --output-dir /tmp/phase4e-candidates --write-models --write-model-architecture winner`
- `xcodebuild -project /Users/hanfei/rork-hoopshighlights-ai_Final/ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'platform=iOS Simulator,id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' -derivedDataPath /tmp/HoopsClipsPhase4e CODE_SIGNING_ALLOWED=NO HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev build`

All of the above passed.

### Offline candidate comparison

- Report: [`/tmp/phase4e-candidates/comparison_report.md`](/tmp/phase4e-candidates/comparison_report.md)
- JSON: [`/tmp/phase4e-candidates/comparison_report.json`](/tmp/phase4e-candidates/comparison_report.json)
- Winner: `tridet`
- Winner score: `4.8774`

Winning offline summary:

- Proposal acceptance rate: `0.5455`
- Accepted-shot outcome accuracy: `0.8`
- Uncertainty rate: `0.4545`
- Highlight dominance: `0.4545`
- EventFamily=`other` dominance: `0.4545`
- Rejected proposal true-negative rate: `1.0`

### Staging deploy

- Cloud Run revision: `hoopsclips-inference-staging-00028-gxx`
- Cloud Run URL: [https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app](https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app)
- `/version` returned `phase4e-open-set-proposal-rejection-and-ranking`
- Worker URL: [https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev](https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev)

### Worker-path smoke

- Job: `26d08c0449864ed3a3b0b26e1163e4f7`
- Upload trace: `871f8984dc7a41e6b871fd0a6374e067`
- Inference attempt: `fcf5653223ed44e3ab8daa10ae324911`
- Final status: `completed`
- Result: `1` clip shipped successfully through the unchanged control-plane contract

### Simulator upload

- Built app path: `/tmp/HoopsClipsPhase4e/Build/Products/Staging-iphonesimulator/HoopsClips.app`
- Booted simulator: `iPhone 16e (09C3102D-6824-4BA2-8CBE-F6348561F6E8)`
- Screenshot: ![phase4e iOS smoke](/tmp/phase4e-ios-smoke.png)
- Visible Review trace fields:
  - requestId `A8C1F34AF74846BF-B563714D5DCAA9EA`
  - uploadTraceId `b8b16-c6a347540e6859c3ed-cfec1f829`
  - inferenceAttemptId `d53464510a9e4d8d840f4c4cc4bdaeb9`
  - modelVersion `videomae:MCG-NJU/videomae-base-finetuned-kinetics`

### Mixed live shadow batch

- Manifest size: `8` uploads
- Output dir: `/tmp/phase4e-batch/results`
- Batch summary: [`/tmp/phase4e-batch/summary.json`](/tmp/phase4e-batch/summary.json)
- Shadow report markdown: [`/tmp/phase4e-batch/shadow-report/shadow_eval_report.md`](/tmp/phase4e-batch/shadow-report/shadow_eval_report.md)
- Shadow report json: [`/tmp/phase4e-batch/shadow-report/shadow_eval_report.json`](/tmp/phase4e-batch/shadow-report/shadow_eval_report.json)

Summary from `/tmp/phase4e-batch/shadow-report/shadow_eval_report.json`:

- Clip count: `12`
- Flat label distribution: `{"Dunk": 6, "Fast Break": 2, "Highlight": 4}`
- EventFamily distribution: `{"other": 4, "shot_attempt": 6, "transition": 2}`
- Outcome distribution: `{"made": 6, "uncertain": 6}`
- ShotSubtype distribution: `{"dunk": 6, "layup": 5, "null": 1}`
- Proposal acceptance rate: `0.6667`
- Eventness calibration: `{"brierScore": 0.4106, "eligibleClips": 12, "negativeMeanScore": 0.893, "positiveMeanScore": 0.8476}`
- Uncertainty rate: `0.3333`
- Accepted-shot outcome accuracy: `0.1667`
- Highlight dominance: `0.3333`
- EventFamily=`other` dominance: `0.3333`
- Rejected proposal audit: `{"eligibleRejectedClips": 4, "trueNegativeCount": 4, "trueMissCount": 0, "trueNegativeRate": 1.0, "trueMissRate": 0.0}`
- Mixed-batch label spread: `3` unique flat labels, dominant label `Dunk` at `50%`
- Split-other distribution: `{"non_event": 4}`
- Event spotter precision / recall: `0.75` / `1.0`
- Event detection precision / recall: `0.75` / `1.0`
- EventFamily accuracy: `0.6667`
- Outcome accuracy: `0.4167`

Representative live behavior:

- The verifier rejected the two longer `DEMO_VID` non-event proposals per upload as `non_event`, which is the first live phase in this line where proposal acceptance fell materially below `1.0`.
- The same `DEMO_VID` upload still produced one accepted `shot_attempt` / `made` / `Dunk` proposal per run, so open-set rejection is incomplete.
- Broadcast shot clips no longer collapsed into one flat label, but the accepted outputs still split incorrectly between `transition` / `Fast Break` / `uncertain` and `shot_attempt` / `Dunk` / `made`.
- The accepted-shot outcome head regressed badly on live data: only `16.67%` of accepted shot proposals matched the expected `made` vs `missed` outcome.

## Verdict

Phase 4e improved proposal rejection and broke the total single-label collapse, but it failed the branch goal.

What improved:

- Proposal acceptance rate dropped from the phase4d live value of `1.0` to `0.6667`.
- Uncertainty no longer collapsed to `0.0`; it improved to `0.3333`.
- `Highlight` dominance dropped below the target ceiling to `0.3333`.
- `eventFamily=other` dominance also dropped below the target ceiling to `0.3333`.
- Every rejected proposal in the live batch was a true negative (`trueNegativeRate = 1.0`), which means the verifier/ranker stack can reject obvious non-events without breaking the control-plane contract.
- Worker smoke, simulator upload, Review trace metadata, and shadow reporting all stayed healthy.

What failed:

- The stack still accepted too many weak proposals and routed them into confident `shot_attempt` / `made` / `Dunk` predictions.
- Accepted-shot outcome accuracy collapsed to `0.1667`, far below the acceptance bar of `> 0.5`.
- The new runtime no longer collapses to one label, but the dominant accepted positive label is still `Dunk` at `50%`, which is too concentrated for promotion.
- The accepted broadcast shot clips still show poor event-family calibration, alternating between `transition` / `uncertain` and `shot_attempt` / `made` instead of separating made vs missed shot attempts cleanly.

Acceptance criteria result:

- `proposal acceptance rate is meaningfully below 1.0`: passed (`0.6667`)
- `no collapse to a single confident positive label`: passed
- `Highlight < 50%`: passed (`0.3333`)
- `eventFamily other < 40%`: passed (`0.3333`)
- `accepted-shot outcome accuracy improves above 0.5`: failed (`0.1667`)
- `uncertainty no longer collapses to 0.0`: passed (`0.3333`)
- `no smoke/simulator regression`: passed

## Decision

Keep phase4e in shadow mode only. The open-set verifier and ranking layer are doing useful rejection work, but the accepted-proposal hierarchy is still not promotable because outcome quality regressed sharply on real staging clips.

# Phase 4: In-Domain Active Learning and Event Localization

Date: 2026-03-31
Branch: `codex/phase4-in-domain-active-learning-and-event-localization`
Verified commit: `81253ff`

## Rollout

- Inference service deployed to the durable Cloud Run staging endpoint:
  - URL: `https://hoopsclips-inference-staging-568888872909.us-central1.run.app`
  - Revision: `hoopsclips-inference-staging-00018-fsw`
  - Version: `phase4-in-domain-active-learning-and-event-localization`
- Control plane remained on the existing staging Worker:
  - URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Control-plane contract unchanged.
- Shadow path remained enabled through `runtimeFusionTemporalShadow`.

## Validation

### Local

- Targeted inference tests passed:
  - `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final services/inference/.venv/bin/python -m unittest services.inference.tests.test_perception_features services.inference.tests.test_shadow_eval services.inference.tests.test_pipeline`
- Control-plane typecheck passed:
  - `npm --prefix services/control-plane run typecheck`
- Staging simulator build passed with explicit Worker URL injection:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'platform=iOS Simulator,id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' -derivedDataPath /tmp/HoopsClipsPhase4 CODE_SIGNING_ALLOWED=NO HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev build`

### Worker-path smoke

- Smoke job completed end to end:
  - `jobId`: `6c52f986f7de48948aec210681dc01aa`
  - `uploadTraceId`: `6d4132c47c024157bb503fe9ce69b221`
  - `inferenceAttemptId`: `bcde730cce034cc180e52fb38db4caa3`
  - `finalStatus`: `completed`
  - returned label: `Highlight`
  - returned duration: `4.5s`
- The live job payload confirmed `runtimeFusionTemporalShadow` was populated on staging instead of collapsing to `null`.

### iOS staging flow

- Automated simulator upload flow reached Review and rendered the live staging trace card.
- App-driven cloud-analysis run completed cleanly:
  - `requestId`: `E1E02BBB27934CD4AEE786457D3CFF85`
  - `jobId`: `229c90f737d7429ea99b205f8e37a8c3`
  - `uploadTraceId`: `f0d29100c1a04ed3a58b1fbee1ed8054`
  - `inferenceAttemptId`: `776508e5c6ad48f4b7171c01899b5411`
  - `status`: `completed`
- Screenshot: `/tmp/phase4-ios-smoke-final.png`

## Mixed live shadow batch

Batch artifacts:
- Results: `/tmp/phase4-batch/results`
- Batch summary: `/tmp/phase4-batch/batch_summary.json`
- Shadow report JSON: `/tmp/phase4-batch/shadow-report/shadow_eval_report.json`
- Shadow report Markdown: `/tmp/phase4-batch/shadow-report/shadow_eval_report.md`

Per-job IDs:

| file | jobId | uploadTraceId | inferenceAttemptId | clipCount |
| --- | --- | --- | --- | --- |
| `make_2_3.20s.mp4` | `4d7b0b86aba54b68aceccfb67bf804a4` | `e19207e89f9f427692fa375aaea43282` | `5e1291df8e7046458dec7b54d47093ca` | `1` |
| `miss_2_3.13s.mp4` | `249052c58b0e4366963f3cd353180bd3` | `f40d1af2c55b419da0ef576f34db28c1` | `f9179421dd9b40309d28360525f35f71` | `1` |
| `miss_1_0.00s.mp4` | `1c70fbc11cce4b82ad76c9323bcd6547` | `4662683c924c4b439fceefff86297c66` | `95985c6fa5cb4058ae607effbe55396e` | `1` |
| `broadcast_08_lebron.mp4` | `a6ee4959693143829ecfa2f0ccfa0775` | `28a987212b734e3584c91ccf4a6a2d50` | `7aad088f964849e685d41614e05c425f` | `2` |
| `demo_00_0.0.mp4` | `30cd56ffb8034f8abb3f834379893ea2` | `9d838f96d59f46e4a4ab4ff5aeaf5194` | `5be069778f86456f9604c4ba32fffe6e` | `1` |
| `demo_01_4.0.mp4` | `214c9a6d8b17400ba191fa78d6380dad` | `f2f45f942846401a828df4659464e9c2` | `d311d60e61b44e16847fc8a876107b17` | `1` |
| `demo_02_8.0.mp4` | `2c710b25eb004c06b35e59003161de8a` | `7c0b3c7c40b24cbda6f23b7babba57c6` | `7aac7fbffe544107837b6caa8b9f539b` | `1` |
| `demo_03_12.0.mp4` | `cfff59965aa54ebea222475a06f8d633` | `91a521c79c7646529c0669d0650ba86b` | `399efa76ce614aa3ab4ddd7a878d6991` | `1` |

Shadow summary:

- `flatLabelDistribution = {'Dunk': 1, 'Fast Break': 3, 'Highlight': 5}`
- `eventFamilyDistribution = {'other': 5, 'shot_attempt': 1, 'transition': 3}`
- `outcomeDistribution = {'made': 1, 'missed': 1, 'uncertain': 7}`
- `shotSubtypeDistribution = {'dunk': 1, 'layup': 5, 'null': 3}`
- `uncertaintyRate = 0.5556`
- `highlightDominance = 0.5556`
- `eventFamilyOtherDominance = 0.5556`
- `missVsMadeConfusion = {'expectedMadePredictedHighlight': 1, 'expectedMadePredictedMiss': 0, 'expectedMissPredictedHighlight': 0, 'expectedMissPredictedMadeShot': 0}`
- `eventDetectionPrecision = 1.0`
- `eventDetectionRecall = 0.5`
- `eventFamilyAccuracy = 0.0`
- `outcomeAccuracy = 0.0`
- `shotSubtypeAccuracy = 0.0`
- `sourceDomainDistribution = {'broadcast': 2, 'live_shadow': 4, 'staging_smoke': 3}`
- `durationSummary = {'count': 9, 'medianSeconds': 4.2, 'p90Seconds': 4.75}`
- `mixedBatchLabelSpread = {'uniqueLabelCount': 3, 'dominantLabel': 'Highlight', 'dominantLabelShare': 0.5556, 'spreadScore': 0.4444, 'entropy': 1.3516}`

Notable examples:

- `demo_02_8.0.mp4` broke out of the collapse path and produced `Dunk`, `shot_attempt`, `made`, confidence `1.0`.
- `miss_2_3.13s.mp4` and `miss_1_0.00s.mp4` both surfaced as `Fast Break` / `transition` instead of defaulting to a made-shot-like label.
- `make_2_3.20s.mp4` still failed badly on the labeled anchor: the temporal shadow output was `Highlight`, `eventFamily=other`, `shotSubtype=layup`, `outcome=missed`.

## Acceptance result

Status: failed

What improved relative to phase 3f2:

- Flat-label spread increased from `2` labels to `3`.
- `Highlight` dominance dropped from `0.875` to `0.5556`.
- `eventFamily=other` dominance dropped from `0.875` to `0.5556`.
- Uncertainty dropped from `0.875` to `0.5556`.
- Outcome separation appeared in live shadow outputs: `made=1`, `missed=1`, `uncertain=7`.
- Safety held: no miss clip drifted into `Made Shot`.

Why this still failed the branch bar:

- `Highlight` missed the `< 50%` target.
- `eventFamily=other` missed the `< 40%` target.
- The mixed batch still did not show strong enough in-domain eventFamily coverage.
- The labeled anchor subset remained wrong on the hard shot examples.
- The runtime is operationally healthier, but the staged detector is still not reliable enough to promote.

## Conclusion

Phase 4 fixed the operational blocker from the earlier shadow path: live staging now returns populated temporal-student shadow outputs on real Worker-path jobs, the mixed batch is more diverse than the prior branch, and the simulator upload path still renders Review trace metadata correctly.

Phase 4 did not clear acceptance. The Highlight/other collapse is reduced but not broken. The right next step is to keep the durable staging endpoint, preserve the current contract, and continue with deeper in-domain event supervision and staged runtime training rather than more threshold or prompt tuning.

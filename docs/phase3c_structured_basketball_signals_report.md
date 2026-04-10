# Phase 3C: Structured Basketball Signals

## Summary

This branch adds a structured basketball-signal layer to the live inference path without changing the control-plane contract or the existing clip windowing policy.

The live stack still works end to end on staging:

- Cloudflare control plane accepted uploads and dispatched to the live external inference service.
- The staging iOS app still rendered the Review screen and staging trace metadata.
- The inference service now emits internal `eventFamily`, `shotSubtype`, and `outcome` fields derived from ball / rim / player signals instead of relying only on generic VideoMAE / X-CLIP action logits.

However, the branch does **not** meet the acceptance bar for flat label diversity. On the final live mixed batch, internal hierarchy improved, but all app-facing display labels still collapsed to `Highlight`.

## What Changed

- Added a perception layer for `basketball`, `rim`, and `player` detections and lightweight track summaries.
- Added structured basketball features such as:
  - `ballNearRim`
  - `ballAboveRim`
  - `ballArcApex`
  - `ballThroughHoopLikelihood`
  - `possessionChangeLikelihood`
  - `playerToRimDistance`
  - `ballCarrierSpeed`
  - `transitionSpeedScore`
  - `defenderProximityAtShot`
  - `shotReleaseCandidate`
  - `samePlayContinuityScore`
- Added hierarchical decision logic for:
  - `eventFamily = shot_attempt / turnover / defensive_event / transition / other`
  - `outcome = made / missed / blocked / uncertain`
  - `shotSubtype = dunk / layup / jumper / three / putback`
- Added an offline Qwen-based teacher-labeling path for audits and pseudo-label generation.
- Fixed a real model-path correctness bug so VideoMAE and X-CLIP now sample frames from each candidate window, not the entire source video.
- Added structured-signal eval scaffolding and targeted unit coverage.
- Fixed a regression where one miss scenario could be remapped to `made`.

## Validation

- Passed: `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final python3 -m unittest services.inference.tests.test_labels services.inference.tests.test_pipeline services.inference.tests.test_structured_signals services.inference.tests.test_teacher services.inference.tests.test_eval_report`
- Passed: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Staging -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/HoopsClipsPhase3c CODE_SIGNING_ALLOWED=NO HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev build`
- Passed: live staging smoke using the staging Worker and live external inference service routed through the phase-3c tunnel

## Live Staging Smoke

The staging Review screen rendered successfully with trace metadata after automatic analysis from the simulator build. The Review screen showed:

- `requestId`
- `uploadTraceId`
- `inferenceAttemptId`
- `modelVersion`
- `failureReason`

The smoke path remained backward-compatible with the current app.

## Final Live Mixed Batch

The final live batch used these files:

- `backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4`
- `backend/.external/HoopCut_FH/main/static/clips/miss_2_3.13s.mp4`
- `backend/.external/HoopCut_FH/main/static/clips/miss_1_0.00s.mp4`
- `backend/.external/HoopCut_FH/provided_test/DEMO_VID.MOV`

### Per-clip outcomes

| File | Job ID | Request ID | Upload Trace ID | Inference Attempt ID | Event Family | Shot Subtype | Outcome | Display Label | Duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `make_2_3.20s.mp4` | `d377436a94624c61995ef72b048b8dac` | `09ef0e1c-e4ab-45fb-9ad5-e796e8cb37e2` | `afd3df8d174b46fe885e0a6ae5cea0a9` | `2863659a1fe84cd3bde33eb7bf99d436` | `shot_attempt` | `dunk` | `uncertain` | `Highlight` | `4.50s` |
| `miss_2_3.13s.mp4` | `604b1f44295345e0918d9e6e57cc5bc2` | `a6ad9491-7f68-45bb-99a0-ab0e5725b886` | `b630593eadfa45cb9106eeba83ad1f6f` | `278299fab337458d93dfd30972f87698` | `shot_attempt` | `layup` | `missed` | `Highlight` | `4.50s` |
| `miss_1_0.00s.mp4` | `356a270a2e8042ca811358a297a541fe` | `06d6ddd1-df41-4849-bf8a-8087ece43c26` | `c9cd1a3d3a5f4be093c5ef907f4ca0c1` | `e86cb0ba69f548e88ebdcb9e893d5a02` | `other` | `null` | `uncertain` | `Highlight` | `4.20s` |
| `DEMO_VID.MOV` | `3d5f0de859f74eaca0063576b276af71` | `58c9c855-4b9a-4a7a-ba78-2c36b43fce8c` | `40f8ddb42ac94629a070543c31162a1b` | `d9df3fe8ac9744059553ccd4dfd53b4a` | `shot_attempt` | `jumper` | `uncertain` | `Highlight` | `4.75s` |

### Aggregate results

- Display label distribution:
  - `Highlight`: `4`
- Event family distribution:
  - `shot_attempt`: `3`
  - `other`: `1`
- Shot subtype distribution:
  - `dunk`: `1`
  - `layup`: `1`
  - `jumper`: `1`
  - `null`: `1`
- Outcome distribution:
  - `missed`: `1`
  - `uncertain`: `3`
- Duration summary:
  - minimum: `4.20s`
  - median: `4.50s`
  - maximum: `4.75s`

## Interpretation

### What improved

- Miss clips no longer default to `Made Shot`.
- Outcome separation is visible internally.
- Subtype separation is visible internally on the mixed batch:
  - `dunk`
  - `layup`
  - `jumper`
- Trace metadata and staging smoke flow remained stable.

### What did not improve enough

- App-facing display labels still collapsed to a single flat label on the mixed live batch.
- The new perception layer is still heuristic and fragile for amateur / fixed-camera footage.
- The eval scaffold is still too small to prove robust structured-signal generalization.
- The teacher-labeling path exists, but it is still an offline audit tool rather than a source of stronger runtime supervision.

## Acceptance Decision

This branch does **not** satisfy the Phase 3C acceptance criteria.

It succeeded at:

- keeping the control-plane contract stable
- preserving the staging smoke flow
- improving internal basketball hierarchy
- separating `missed` from `made` on at least one real miss clip

It failed at:

- showing meaningful flat display-label spread on the mixed live batch
- moving the live user-facing labels beyond generic `Highlight`

## Next Branch

Because structured signals alone still did not recover useful app-facing labels, the correct follow-up is:

- `codex/phase3c1-data-collection-and-teacher-labeling`

That next phase should focus on:

- collecting a larger stratified fixed-camera basketball dataset
- generating audited teacher labels and richer supervision artifacts
- measuring signal reliability for ball / rim / player perception
- separating runtime outputs from offline audit and pseudo-label pipelines more cleanly

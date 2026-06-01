# Phase Launch159 - AI Accuracy Depth

## Goal

Increase highlight recall before GPT editing, especially for selected-team workflows where uncertain jersey attribution should still be reviewable instead of disappearing.

## Architecture Guardrails

- Cloud remains responsible for analysis, GPT clip selection, team attribution, edit planning, rendering, and storage.
- iOS only forwards the cloud candidate pool, selected team, target length, and user note to the backend.
- No iOS analysis, local rendering, FFmpeg command generation, or fake AI state was added.

## Changes

- Raised cloud analysis candidate depth from 220 to 320 clips.
- Raised selected-team prefilter depth to 640 clips so the backend can scan more moments before trimming to the review pool.
- Raised GPT highlight editor Free/Pro candidate caps from 220 to 320.
- Raised team quick scan coverage:
  - max candidate clips: 320
  - rich candidates: 220
  - total clip-frame budget: 2560 default, 3200 max
  - structured-output token budget: 18000
- Raised the iOS cloud edit request candidate forwarding limit to 320 so the app can hand the deeper cloud pool back to AI Edit.
- Increased selected-team GPT sampling reserve for uncertain-but-reviewable clips from 10% to 25% of sampled GPT candidates.

## Product Notes

- 4:30 target reels were already supported by current TemplatePack and iOS duration options before this branch.
- Free daily video editing chances were already set to 3 in the cloud analysis backend.
- This branch improves recall and reviewability; the final render still uses deterministic validated EditPlan execution.

## Validation

- Passed `git diff --check`.
- Passed backend/GPT regression coverage:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest ios.backend.tests.test_pipeline_quality services.editing.tests.test_gpt_reranker`
  - 114 tests passed.
- Passed team quick scan regression coverage:
  - `PYTHONPATH=/tmp/hoopclips-launch159-pydeps:ios/backend /Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest ios.backend.tests.test_team_quick_scan`
  - 39 tests passed.
  - `/tmp/hoopclips-launch159-pydeps` only supplied missing local test dependencies (`fastapi`, `httpx`) and did not modify repo files.
- Passed focused iOS candidate-forwarding regression:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch159-derived-data test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve CODE_SIGNING_ALLOWED=NO -quiet`
- Existing Swift warnings remain around `VideoExportService` Sendable captures and `CloudAnalysisService` progress awaits. They were not introduced by this branch.

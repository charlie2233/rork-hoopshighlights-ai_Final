# Phase Launch146: Simple Safe Export

## Goal

Make Export AI Edit easier for first-time users while keeping all cloud-owned editing, GPT planning, template selection, and render validation intact.

## Changes

- Added a compact `Smart setup` card to AI Edit.
- Hid style, shape, and length controls behind a single `Change style, shape, or length` button by default.
- Kept all existing style/template/format/duration controls available for users who want them.
- Kept the optional side-note text box visible so users can say things like `more hype`, `focus on defense`, `NBA recap`, or `4:30 team reel`.
- Updated AI Edit UI smoke tests so they verify the simple default card first, then expand setup controls before checking templates.
- Preserved cloud ownership: iOS still sends structured choices and the side-note intent, while cloud owns clip selection, EditPlan validation, rendering, and storage.

## Compatibility Notes

- The new smart setup copy wraps on small phones and accessibility text sizes.
- The setup toggle uses SwiftUI-native state and respects Reduce Motion.
- Detailed controls remain adaptive grids, so small phones can scroll rather than truncating core labels.

## Validation

- `git diff --check`
- Backend/GPT sampling checks:
  - `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_two_twenty`
  - Result: `Ran 2 tests ... OK`
- Focused iOS unit test for cloud edit candidate request behavior:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve test`
  - Result: `** TEST SUCCEEDED **`
  - Result bundle: `.codex-build/derived/Logs/Test/Test-HoopsClips-2026.05.31_19-59-27--0700.xcresult`
- iOS Debug `build-for-testing`:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`
- Optional UI smoke after the next trusted-device/TestFlight window.
- No GitHub Actions were triggered.
- Unrelated root `HoopsClips.xcodeproj/` and `HoopsHighlightsAI.xcodeproj/` folders remained untracked and unstaged.

## Launch Notes

- This reduces the number of visible export decisions before the first render.
- The default path is now: optional note -> `Make My Reel` -> real cloud status -> preview/share.
- Users who know exactly what they want can still change template, shape, and length without iOS doing any local video editing or rendering.

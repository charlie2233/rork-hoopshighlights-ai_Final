# Phase Launch144: Simple Visible Candidate Flow

## Goal

Improve launch readiness by making the import-to-analysis path easier to read on small iPhones and giving cloud/GPT editing a larger, aligned candidate pool for better highlight accuracy.

## Changes

- Raised the cloud analysis and GPT edit candidate cap from `160` to `220`.
- Kept iOS, the editing service validator, GPT structured-output schemas, deploy defaults, and docs aligned to the same `220` cap.
- Increased the iOS cloud edit review reserve from roughly one quarter to one third of the request, with a higher minimum reserve, so blocks, steals, defensive stops, and uncertain team clips are more likely to reach the cloud editor.
- Expanded team quick-scan defaults so more candidate clips can receive team attribution before the user chooses a target team.
- Made the import screen analysis button title wrap across two lines, or three lines at accessibility text sizes, instead of hiding longer localized text.
- Made the analysis detail copy more legible by using normal caption sizing and theme text color instead of tiny low-opacity text.
- Refreshed the shipped app icon and in-app brand mark in both HoopClips asset catalogs so the launcher, sign-in, settings, and export watermark no longer fall back to the older badge.

## Architecture Guardrails

- Candidate generation, team scan, GPT selection, EditPlan validation, and rendering remain cloud-owned.
- iOS still only sends selected settings, user/team intent, source object keys, and candidate metadata.
- No local iOS video analysis, rendering, composition, FFmpeg commands, or full-video GPT upload was added.
- No secrets, R2 credentials, or presigned URLs are logged or documented.

## Validation

- `git fetch --prune origin`
- `git diff --check`
- Backend candidate and team quick-scan checks:
  - `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_two_twenty ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_backend_candidate_pool_env_is_clamped_for_review_safety ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_candidate_pool_limit_is_expanded_for_quality_but_bounded ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_prescan_settings_keep_interactive_team_scan_bounded`
  - Result: `Ran 4 tests ... OK`
- GPT reranker sampling checks:
  - `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_env_overrides_are_launch_bounded`
  - Result: `Ran 3 tests ... OK`
- Focused iOS cloud edit request test:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve test`
  - Result: `** TEST SUCCEEDED **`
  - Result bundle: `.codex-build/derived/Logs/Test/Test-HoopsClips-2026.05.31_19-49-27--0700.xcresult`
- iOS Debug build-for-testing:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`
- No GitHub Actions were triggered for this branch.
- Unrelated root `HoopsClips.xcodeproj/` and `HoopsHighlightsAI.xcodeproj/` folders remained untracked and unstaged.

## Launch Notes

- This should make the cloud editor more accurate by giving GPT more reviewed candidates while keeping deterministic validators and render safety in place.
- The UI change targets older/smaller phones and large Dynamic Type where one-line button titles were likely to truncate.
- The logo refresh is asset-only. It does not change runtime behavior, cloud contracts, or any editing/rendering path.
- Use `[skip ci]` for this branch unless a remote deploy/test run is explicitly needed.

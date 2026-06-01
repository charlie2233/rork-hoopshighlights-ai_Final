# Phase Launch148 Simple Export And Defensive Recall

## Goal

Keep moving HoopClips toward internal TestFlight readiness by making the Export screen easier to use by default and improving the cloud edit candidate pool for defensive highlights.

## Changes

- Export now shows a compact local export setup card when local fallback export is available.
- Advanced local export controls for theme, music, quality, format, and post-processing are hidden behind one button.
- Default local export theme changed from locked `Cinematic` to free `Vibrant`, so Free users are not blocked by a Pro-only default.
- GPT/cloud edit candidate recall now treats these labels as defensive review candidates:
  - `intercept`, `intercepted`, `interception`
  - `poke`, `poked`
  - `rip`, `ripped`
  - `stolen`
  - `reject`, `rejected`
  - `rim protection`

## Architecture Notes

- No local iOS analysis, AI edit planning, or production rendering was added.
- Cloud remains the owner of analysis, GPT selection, edit planning, rendering, and storage.
- The iOS change is only presentation/default configuration for the Export control surface.
- Defensive recall changes only decide which existing candidate clips are sent to cloud/GPT review; GPT still receives candidate clips, not full videos.

## Validation

- Added tests for free-compatible default export settings.
- Added tests that interceptions, poked-loose steals, and rejected-at-rim defensive clips remain available for GPT review.
- `git diff --check` passed.
- Focused Swift tests passed:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testDefaultLocalExportSettingsStayFreeAndCompatible -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestKeepsInterceptionsAndPokedLooseStealsForGptReview -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestKeepsExpandedDefensiveMomentsForGptReview test
```

- Candidate-pool regression bucket passed:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesReviewOnlyUncertainCandidatesWithoutAutoKeepingThem -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesStrongSelectedTeamReserveCandidate -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestTagsOverlappingSameMomentDuplicateGroups -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestDoesNotSendLatePreBasketShotCandidate test
```

- iOS Debug `build-for-testing` passed:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO build-for-testing
```

## Launch Notes

- This reduces the “too many export choices” feel without removing the controls for debug/local fallback builds.
- TestFlight/cloud-required builds still steer users through AI Edit, real cloud job status, preview, and share.

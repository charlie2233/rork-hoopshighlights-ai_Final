# Phase Launch149 Team Target Review Accuracy

## Goal

Improve selected-team highlight accuracy while keeping HoopClips ready for internal iOS TestFlight validation. When a user chooses a team before analysis/export, cloud edit should avoid confidently identified opponent clips, but still keep strong uncertain clips available for GPT/review instead of hiding possible good plays.

## Changes

- Added selected-team eligibility for cloud edit candidate export.
- Confident clips for the selected team remain eligible.
- Confident opponent-team clips are excluded from cloud edit candidate payloads.
- Strong uncertain/no-team-attribution clips remain eligible when `includeUncertain` is enabled, so GPT and the user can still review close calls.
- `includeUncertain: false` now disables that reserve path.
- Auto-keep remains strict: uncertain clips are not silently auto-kept as selected-team clips.
- Refreshed the iOS app icon and in-app `BrandMark` assets in both asset catalogs:
  - `ios/HoopsClips/Assets.xcassets`
  - `ios/HoopsClips/HoopsClips/Assets.xcassets`

## Architecture Notes

- No local iOS video analysis, AI edit planning, or production rendering was added.
- iOS still only sends selected team/control-surface intent plus existing candidate metadata to the cloud path.
- Cloud/GPT remains responsible for final semantic selection, EditPlan quality, rendering, and storage.
- Full videos are not sent to GPT by this iOS change.

## Tests

- Added coverage that selected-team cloud edit keeps strong uncertain candidates for review when `includeUncertain` is enabled.
- Added coverage that selected-team cloud edit excludes uncertain reserve candidates when `includeUncertain` is disabled.
- Existing selected-team auto-keep and review-reserve behavior remains covered.

## Validation

- `git diff --check` passed.
- Focused selected-team tests passed:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestKeepsUncertainTeamCandidateForSelectedTeamReview -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestCanDisableUncertainTeamCandidateReserve -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesStrongSelectedTeamReserveCandidate -only-testing:HoopsClipsTests/HoopsClipsTests/testKeepHighConfidenceRespectsSelectedHighlightTeam test
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

- This should improve perceived accuracy for team-specific edits: clear opponent plays are removed, while ambiguous but strong plays still survive for review.
- The new logo assets must ship in a fresh installed build/TestFlight build for iOS SpringBoard/App Library icon caches to update. If a device still shows the old icon after install, delete the old app build and reinstall the new one.

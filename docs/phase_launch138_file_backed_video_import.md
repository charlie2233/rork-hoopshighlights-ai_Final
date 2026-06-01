# Phase Launch138: File-Backed Video Import UX

## Goal

Reduce real-device confusion around long video imports. The Photos/File import path was already file-backed and avoided `Data.self`; this phase adds real phase updates while the app copies and opens the imported video.

## Changes

- Added `ProjectImportPhase` to the project store.
- `ProjectHistoryStore.createProjectFromImportedVideo(...)` reports these real import phases:
  - copying the source video into HoopClips storage
  - reading video metadata
  - generating the project preview thumbnail
  - saving/opening the project
- `HighlightsViewModel.loadVideo(...)` forwards import progress without changing the cloud-first analysis/render architecture.
- `VideoPlayerView` now shows the current real import phase instead of staying on a generic preparation message during the whole copy/thumbnail path.
- Refreshed the actual app icon and in-app `BrandMark` PNGs in both iOS asset catalogs with a cleaner product-style HoopClips mark.
- Clarified uncertain clip review copy so clips kept for human review explain why they were kept instead of looking skipped.

## Architecture Notes

- iOS still only handles import, playback, preview, upload, review, status, download, and share.
- No on-device production analysis, edit planning, rendering, composition, Remotion, or Canva runtime was added.
- Photos imports remain file-backed only; no full-video `Data.self` fallback is introduced.

## Validation

- Passed: `git diff --check`
- Passed: Debug simulator build for `HoopsClips` on iPhone 17 Pro.
- Passed: focused video import policy/preflight tests:
  - `testVideoImportPolicyUsesFileBackedVideoTypesOnly`
  - `testVideoImportPreflightAcceptsLongerFourMinuteThirtyEditSource`
  - `testVideoImportPreflightRejectsOversizedCloudUploadWithExactReason`
  - `testVideoImportPreflightRejectsInsufficientStorageWithExactReason`
- Passed: `testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming`
- Mixed: full `HoopsClipsTests` run reached 108 passing tests but still had unrelated crashes/failures in segmentation/cloud-service tests. The review-copy failure from that run is fixed in this branch.

## Notes

- This is meant to make long imports feel alive without fake AI/thinking text or artificial waits.
- The unrelated root Xcode folders remain untouched.

# Phase Launch120: Cloud Edit Duplicate Signals

Date: 2026-05-31
Branch: `codex/phase-launch120-cloud-edit-duplicate-signals`

## Goal

Improve GPT-led highlight quality by sending deterministic duplicate-moment signals with cloud edit candidate clips. This helps the backend/GPT editor reject redundant windows around the same play while keeping the candidate pool high recall.

## Architecture Boundary

- iOS still does not analyze, render, compose, or export production video.
- iOS only forwards metadata already present in the reviewed clip pool.
- Cloud backend remains responsible for final semantic selection, edit planning, validation, rendering, storage, and revision behavior.
- No full videos, presigned URLs, secrets, FFmpeg commands, or renderer instructions are sent or logged by this change.

## Implementation

- Added `duplicateGroup` assignment before building `CloudEditCandidateClip` payloads.
- Duplicate groups are based on existing clip metadata only:
  - same candidate family, such as shot, block, steal, fast break, or handle
  - high time-window overlap
  - close event centers
  - not explicitly attributed to different selected teams
- Group IDs are stable, compact labels such as `dup_shot_13_0`.
- Single clips are left ungrouped so the backend does not over-penalize unique moments.

## Quality Impact

This supports the GPT editor by marking likely duplicate candidates without shrinking the candidate pool. The backend can still keep uncertain clips for review, but it now receives a clearer signal when multiple candidate windows appear to describe the same highlight.

## Validation

Commands run:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestTagsOverlappingSameMomentDuplicateGroups \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDuplicateGroupsDoNotMergeDifferentAttributedTeams
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditPresetsExposeExpectedAspectRatiosAndDurations \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditPolicySummaryExposesFreemiumCopy \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditStatusCopyUsesRealCloudJobLanguageWithoutFakeThinking \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestEncodesOptionalUserPrompt \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesReviewOnlyUncertainCandidatesWithoutAutoKeepingThem \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditCandidateRankingReservesDefenseAndReviewClipsBeforeCap \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditCandidateRankingPrefersCompleteShotContextOverLatePreBasketWindow \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditCandidateRankingUsesBackendMinimumShotContext \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestDoesNotSendLatePreBasketShotCandidate \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestTagsOverlappingSameMomentDuplicateGroups \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDuplicateGroupsDoNotMergeDifferentAttributedTeams \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditProTemplatesAreRealAndDistinct \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditProUXFlagsDefaultToVisibleButNonPaymentUX \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditVersionFlagsDecodeLiveRenderKillSwitch \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditVersionFlagsReportMissingLaunchReadinessKeys \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditKillSwitchErrorsHaveFriendlyMessages \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRenderStatusDecodesAIWorkTimelineAndReceipt \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditJobResponseDecodesUncertainReviewClipIds
```

Results:

- `git diff --check`: passed
- Focused simulator tests: passed
- Test result bundle: `.codex-build/DerivedData/Logs/Test/Test-HoopsClips-2026.05.31_15-56-18--0700.xcresult`
- Wider cloud edit simulator test slice: passed
- Wider test result bundle: `.codex-build/DerivedData/Logs/Test/Test-HoopsClips-2026.05.31_16-00-16--0700.xcresult`

## Budget Notes

GitHub Actions budget is being conserved. This branch used local simulator tests and `[skip ci]` for the commit.

## Launch Notes

- This is safe for internal TestFlight because it only enriches the existing cloud edit request metadata.
- Backend validators and renderers remain deterministic.
- The unrelated untracked root Xcode project folders were intentionally not staged.

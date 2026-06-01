# Phase Launch132: Cloud Edit Defense Recall

## Goal

Improve highlight clipping quality by sending a larger, higher-recall candidate pool to the cloud edit/GPT planning path, especially for defensive basketball moments that are easy to miss.

## Changes

- Increased the iOS-to-cloud edit candidate request cap from `160` to `220`.
- Increased review-only reserve share from about 20% to about 25% of the cloud edit candidate pool.
- Boosted defensive and needs-review clips in candidate ranking so they survive the cap more often.
- Expanded defensive moment matching for cloud edit candidates:
  - blocks, contests, swats, rejections
  - steals, strips, takeaways, pickpockets
  - deflections, charges, loose-ball plays, forced turnovers
  - defensive stops and lockdown stops

## Architecture

- iOS still only sends compact clip metadata to the cloud.
- No full videos are sent to GPT.
- No local rendering, composition, FFmpeg, or production analysis was added.
- The renderer still executes only backend-validated `EditPlan` output.

## Validation

Commands to run:

```bash
git diff --check
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesReviewOnlyUncertainCandidatesWithoutAutoKeepingThem \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestKeepsExpandedDefensiveMomentsForGptReview \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditCandidateRankingReservesDefenseAndReviewClipsBeforeCap
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build-for-testing
```

Results:

- `git diff --check`: passed.
- Focused `HoopsClipsTests`: passed on iPhone 17 Pro simulator.
- Debug simulator build: passed.
- Debug simulator `build-for-testing`: passed.
- Existing unrelated warnings remain in `CloudAnalysisService.swift` and `VideoExportService.swift`.

## Notes

- Commit should use `[skip ci]` to preserve GitHub Actions budget.
- Preserve unrelated untracked root Xcode folders.

# Phase Launch129: AI Edit Simple Intent

## Goal

Make Export AI Edit simpler for normal users while improving cloud edit accuracy. Users can type ordinary requests like `NBA recap`, `30s vertical mixtape`, `coach review`, or `4:30`, and iOS safely maps those words to structured cloud edit choices before creating the backend job.

## Architecture

- iOS remains the control surface only.
- The app does not analyze, render, compose, or create FFmpeg commands.
- The side note is parsed only into safe request fields:
  - preset
  - Pro template when the plan allows it
  - aspect ratio
  - target duration
- The original sanitized note is still sent to the cloud backend for GPT/edit planning.
- Backend validators and policy limits still own final EditPlan safety.

## UX Changes

- The primary `Make My Reel` action now appears before the optional side-note card.
- The hero copy is shorter and clearer.
- The side-note field is taller, especially for accessibility text sizes.
- Placeholder text uses normal subtle text contrast instead of extra-faint copy.

## Intent Mapping

Examples:

- `make it NBA recap, 30s vertical`
  - Pro template: `nba_recap_pro_v1`
  - Free fallback preset: `full_game_highlight`
  - Aspect ratio: `9:16`
  - Duration: `30`
- `coach review 4:30 source`
  - Preset: `coach_review`
  - Aspect ratio: `source`
  - Duration: `270`
- `vertical 9:16 cinematic mixtape`
  - Pro template: `cinematic_mixtape_pro_v1`
  - Free fallback preset: `personal_highlight`
  - Aspect ratio: `9:16`
  - Duration: none, because `9:16` is an aspect ratio, not a time.

## Validation

Commands to run:

```bash
git diff --check
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
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserIntentParsesRecapShapeAndDuration \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserIntentParsesCoachReviewSourceAndLongDuration \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserIntentKeepsAspectRatioOutOfDuration \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditPolicySummaryExposesFreemiumCopy
```

Results:

- `git diff --check`: passed.
- Focused `HoopsClipsTests`: passed on `iPhone 17 Pro`.
- Debug simulator build: passed.
- Debug simulator `build-for-testing`: passed.
- Existing unrelated warnings remain in `CloudAnalysisService.swift` and `VideoExportService.swift`.

## Notes

- No CI run was intentionally triggered; commit messages should keep `[skip ci]` while Actions budget is tight.
- Untracked root Xcode folders should remain unstaged.

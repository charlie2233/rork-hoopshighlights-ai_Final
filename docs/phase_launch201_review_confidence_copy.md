# Phase Launch201: Review Confidence Copy

## Goal

Make HoopClips easier to trust during internal testing by keeping review wording honest and surfacing audio/crowd-pop review cues after analysis.

## Architecture

- Cloud remains responsible for analysis, GPT clip selection, edit planning, rendering, and storage.
- iOS only displays returned clip evidence, review state, and export controls.
- No local video analysis, rendering, composition, or FFmpeg behavior was added.
- No secrets, R2 credentials, or presigned URLs are logged or displayed.

## Changes

- Changed the first clip evidence row from `Why kept` to `Needs review` when a clip has team, audio, timing, or outcome uncertainty.
- Updated the review reason so skipped-but-reviewable audio cues do not imply they were already kept.
- Added a compact analysis-complete summary row for loud crowd/audio cues flagged for Review.
- Added focused tests for review copy and audio-cue summary behavior.

## Validation

Commands run locally:

```bash
git diff --check

xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16e' test -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkLoudAudioCueForVisualReview -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewDecisionDoesNotClaimSkippedAudioCueWasKept -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesIgnoreWeakAudioOnlyNoise -only-testing:HoopsClipsTests/HoopsClipsTests/testAudioCueReviewSummaryCountsOnlyVisibleReviewCues -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditStatusRefreshPolicyDoesNotBlockTransientVersionFailures

xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16e' build-for-testing

xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16e' build
```

Result:

- `git diff --check`: clean
- `** TEST SUCCEEDED **`
- `** TEST BUILD SUCCEEDED **`
- `** BUILD SUCCEEDED **`
- Result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.01_14-39-59--0700.xcresult`

## Launch Recommendation

Keep this enabled for internal TestFlight because it makes the AI review state more understandable without changing scoring thresholds, cloud rendering, or backend policy. Audio cues remain review hints only; users still verify the visible play outcome.

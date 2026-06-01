# Phase Launch200: Review Clarity Chips

## Goal

Make loud crowd/audio reactions visible to the user during clip review so possible highlights found from audio salience are easy to inspect instead of feeling hidden or random.

## Architecture

- Cloud remains responsible for analysis, GPT selection, edit planning, rendering, and storage.
- iOS only displays the cloud/runtime clip evidence, review badges, preview, and user controls.
- No local video analysis, rendering, composition, or FFmpeg behavior was added to iOS.
- No secrets, R2 credentials, or presigned URLs are logged or displayed.

## Changes

- Added an `Audio?` review badge for clips with very strong audio reaction evidence plus enough visual/motion activity.
- Kept weak audio-only noise out of review so loud but visually dead clips do not clutter the app.
- Updated the review decision copy to include audio as a reason a clip may need human review.
- Added focused iOS tests for the loud-audio review badge and weak-noise rejection.

## Validation

Commands run locally:

```bash
git diff --check

xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16e' test -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkMissingTeamAttributionStatusUncertain -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkLoudAudioCueForVisualReview -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesIgnoreWeakAudioOnlyNoise

xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16e' build-for-testing

xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16e' build
```

Result:

- `git diff --check`: clean
- `** TEST SUCCEEDED **`
- `** TEST BUILD SUCCEEDED **`
- `** BUILD SUCCEEDED **`
- Result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.01_14-28-36--0700.xcresult`

## Launch Recommendation

Keep this enabled for internal TestFlight because it improves review transparency for the new crowd-pop recall path without changing backend scoring, cloud rendering, or export policy. Continue watching real-device imports for noisy clips where high audio score does not match visible basketball action.

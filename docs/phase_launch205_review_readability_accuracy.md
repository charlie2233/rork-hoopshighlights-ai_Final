# Phase Launch205: Review Readability and Audio Accuracy

## Goal

Make the Review screen easier to read on small phones and large Dynamic Type, and align iOS review cues with the backend audio-reaction recall path.

## Change

- Review score rows now use `ViewThatFits` so score labels and percentages can fall back from one horizontal row to a stacked layout instead of squeezing text.
- Score labels and values get scale limits and accessibility values so Audio/Motion/Visual/Combined evidence remains readable.
- iOS review badges now recognize broader audio-reaction phrases such as `Audio Spike Cue`.
- iOS review badges now flag very loud audio peaks with some action context, matching the backend `super_loud_audio_pop` recall behavior.
- Weak audio-only noise remains unflagged unless there is enough visual, motion, or combined action context.

## Architecture

- This is iOS review UX and metadata interpretation only.
- iOS still does not perform production analysis, edit planning, composition, rendering, or FFmpeg work.
- Audio remains a review hint. It does not prove a made shot, block, steal, or other outcome without visual evidence.

## Validation

- Passed: `git diff --check`
- Passed: focused iOS audio badge tests
  - `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' -derivedDataPath /tmp/hoopclips-launch205-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkLoudAudioCueForVisualReview -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkSuperLoudAudioCueWithSomeActionContext -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesRecognizeAudioSpikeCuePhrase -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesIgnoreWeakAudioOnlyNoise`
  - Result: `** TEST SUCCEEDED **`
  - Result bundle: `/tmp/hoopclips-launch205-dd/Logs/Test/Test-HoopsClips-2026.06.01_15-49-51--0700.xcresult`
- Passed: iOS Debug simulator build
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch205-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build`
  - Result: `** BUILD SUCCEEDED **`

## Notes

- Root-level untracked Xcode project folders remain unrelated and must stay unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`
- Use `[skip ci]` for this local-validated slice unless remote CI becomes necessary.

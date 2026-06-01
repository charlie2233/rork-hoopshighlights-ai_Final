# Phase Launch196 - Team Choice Readability and Audio Cue Labels

## Goal

Make the pre-analysis choices easier to read on small phones and make cloud AI Edit candidate context clearer for GPT without moving analysis or rendering into iOS.

## Changes

- Team choice buttons use wider adaptive columns, taller tap targets, and up to three lines for normal Dynamic Type or four lines for accessibility sizes.
- Generic loud-audio candidates sent to cloud edit are relabeled as `Audio Pop Cue`.
  - Existing explicit labels such as `Crowd Reaction` are preserved.
  - Audio cues remain review candidates only; GPT/cloud must still verify visible outcome before selecting a highlight.
- Added a regression test for generic audio-pop labels in cloud edit requests.

## Architecture

- iOS remains the control surface for import, team choice, review, export setup, status, preview, save, and share.
- Cloud remains responsible for semantic clip selection, edit planning, validation, rendering, and storage.
- iOS does not send full videos to GPT and does not generate renderer commands.

## Validation

Commands to run:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestLabelsGenericAudioPopCueForGptReview -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestReservesCrowdPopCandidateForGptReview -only-testing:HoopsClipsTests/HoopsClipsTests/testTeamTargetChoicesRequireDetectedTeams
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build-for-testing
```

Results:

- `git diff --check`: passed.
- Focused iOS tests: passed on `iPhone 16e` simulator.
  - `testCloudEditRequestLabelsGenericAudioPopCueForGptReview`
  - `testCloudEditRequestReservesCrowdPopCandidateForGptReview`
  - `testTeamTargetChoicesRequireDetectedTeams`
  - Result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.01_13-39-29--0700.xcresult`
- Debug `build-for-testing`: passed on `iPhone 16e` simulator.

## Launch Note

This improves usability and GPT candidate clarity, but launch readiness still requires a real-device/TestFlight smoke from import through cloud analysis, AI Edit render, preview, revision, and share/open-in.

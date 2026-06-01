# Phase Launch197 - Simpler AI Edit Lengths and Crowd-Pop Focus

## Goal

Make AI Edit easier for non-technical TestFlight users while preserving longer reel support and improving highlight-selection guidance for loud crowd/audio reaction moments.

## Changes

- Added a `Crowd pops` quick focus button in AI Edit.
  - The note tells cloud AI editing to use loud crowd pops, bench reactions, and audio spikes as highlight clues.
  - It also keeps the safety rule that the play outcome must be visible before a clip is selected.
- Simplified visible reel length choices.
  - The first length picker view now emphasizes common choices instead of showing every possible duration.
  - A `More lengths` button reveals the full supported list when users want direct control.
  - Typed notes such as `4:30 team reel` still resolve against the full allowed duration set.
- Preserved cloud-first architecture.
  - iOS still sends structured choices and an optional side note.
  - Cloud remains responsible for clip selection, edit planning, validation, rendering, and storage.

## Validation

Commands run:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditLengthChoicesStartSimpleButKeepSelectedLongDurationVisible -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditLengthChoicesCanRevealAllAllowedDurations -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserIntentParsesTeamReelPhraseFromPromptPlaceholder -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build-for-testing
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build
```

Results:

- `git diff --check`: passed.
- Focused iOS tests: passed on `iPhone 16e` simulator.
  - Result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.01_13-47-23--0700.xcresult`
- Debug `build-for-testing`: passed on `iPhone 16e` simulator.
- Debug simulator build: passed on `iPhone 16e` simulator.

## Launch Note

This reduces Export decision fatigue and makes loud crowd/audio cues easier for users to request. It does not prove TestFlight readiness by itself; the real-device smoke still needs to cover import/upload, cloud analysis, AI Edit render, preview, revision, and share/open-in.

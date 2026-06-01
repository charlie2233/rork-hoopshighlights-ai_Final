# Phase Launch195 - Simple AI Edit and Audio Reaction Recall

## Goal

Make Export AI Edit easier to use on small phones while improving GPT-led highlight recall for loud crowd/audio reaction moments.

## Changes

- AI Edit now shows quick focus chips directly in the side-note card.
  - Users no longer need to open a hidden examples area before choosing common edit directions.
  - Chips keep Dynamic Type-safe sizing and multiline labels.
- Cloud edit candidate handoff now treats loud crowd/audio reaction clips as review-worthy candidates.
  - Audio pops are recall hints only.
  - GPT still validates visible outcome with sampled frames before selection.
  - iOS does not perform final analysis, edit planning, rendering, or export.
- Candidate ranking now reserves one audio-reaction candidate under pressure, similar to defensive highlights.
- Cloud edit prompt packing keeps typed user notes while preserving selected-team, defense, crowd/audio, visual-outcome, duplicate-rejection, and uncertain-review guardrails.

## Architecture

- iOS remains the control surface: import, upload, review, export setup, status, preview, save, and share.
- Cloud remains responsible for GPT selection, edit planning, rendering, storage, and validation.
- Audio reaction candidates are passed as compact clip metadata only. Full videos are not sent to GPT by iOS.

## Validation

Commands:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestReservesCrowdPopCandidateForGptReview -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesUserInstruction
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesGuardrailsForLongUserNote -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestReservesCrowdPopCandidateForGptReview
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build-for-testing
```

Results:

- `git diff --check`: passed.
- Focused iOS tests: passed.
  - `testCloudEditRequestReservesCrowdPopCandidateForGptReview`
  - `testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve`
  - `testCloudEditUserPromptBuilderPreservesUserInstruction`
  - `testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote`
  - `testCloudEditUserPromptBuilderPreservesGuardrailsForLongUserNote`
- Full `HoopsClipsTests`: passed.
  - Result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.01_13-30-26--0700.xcresult`
- Debug `build-for-testing`: passed.

## Launch Note

This improves candidate recall and usability, but it does not prove TestFlight launch readiness. A real-device smoke still needs import, cloud analysis, AI Edit render, preview, revision, save, and share.

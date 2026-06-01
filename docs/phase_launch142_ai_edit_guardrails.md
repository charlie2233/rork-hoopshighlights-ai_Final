# Phase Launch142: AI Edit Guardrails

## Goal

Make AI Edit simpler for users while improving highlight-selection accuracy. Users can still type short notes like `more hype`, `focus on defense`, or `4:30 team reel`, but HoopClips now keeps the cloud editor focused on basketball quality guardrails.

## Changes

- Preserved the optional AI Edit side note as the simple user control.
- Appended compact cloud-editing guardrails to typed notes so short prompts do not erase accuracy direction.
- Kept the existing 240-character prompt cap.
- Guardrails cover clear visible outcomes, made shots, blocks, steals, defensive stops, fast breaks, duplicate rejection, boring/unclear rejection, and uncertain team clips for Review.
- Updated the visible helper copy from `Default focus` to `Accuracy guardrails`.
- Updated the side-note placeholder to include a long-form example: `4:30 team reel`.

## Architecture Guardrails

- iOS still sends only structured edit intent and reviewed candidate clips.
- The cloud backend still owns GPT clip selection, ordering, EditPlan validation, rendering, storage, and revisions.
- No local video analysis, local production rendering, raw FFmpeg generation, or full-video GPT upload was added.

## Validation

- `git diff --check` passed.
- Focused iOS tests passed:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath .codex-build/derived \
  -skipPackagePluginValidation \
  COMPILER_INDEX_STORE_ENABLE=NO \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptAddsAccuracyGuidanceWhenUserLeavesNoteEmpty \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptCarriesSelectedTeamFocus \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesUserInstruction \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote \
  test
```

Result: `** TEST SUCCEEDED **`

Evidence: `.codex-build/derived/Logs/Test/Test-HoopsClips-2026.05.31_19-12-55--0700.xcresult`

- iOS Debug simulator `build-for-testing` passed:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath .codex-build/derived \
  -skipPackagePluginValidation \
  COMPILER_INDEX_STORE_ENABLE=NO \
  build-for-testing
```

Result: `** TEST BUILD SUCCEEDED **`

## Notes

- This phase intentionally avoids GitHub Actions to conserve CI budget unless a remote run becomes necessary.
- Unrelated untracked root Xcode folders remain untouched.

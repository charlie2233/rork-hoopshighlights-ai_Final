# Phase Launch95 Export Note Readability

## Goal

Make AI Edit easier for non-technical users and improve clip-selection intent quality without changing the cloud-first editing boundary.

## Change

- Added quick edit-note chips to the AI Edit side-note card.
- Included accuracy-focused prompts for defense, blocks, steals, clear outcomes, uncertain-but-reviewable moments, hype, and team recap flow.
- Kept the chips as adaptive grid buttons so labels wrap on small phones and larger Dynamic Type sizes.
- The chips write into the existing `userPrompt` field that is already sent to the cloud edit request.

## Architecture

- iOS still only collects structured user intent and displays status, preview, save, and share controls.
- Cloud still owns GPT clip selection, edit planning, validation, rendering, storage, and revisions.
- No local analysis, rendering, FFmpeg command generation, or timestamp logic was added.

## Validation

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch95-derived-data CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch95-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing
```

Result on 2026-05-31:

- `git diff --check`: passed.
- Debug simulator build: passed.
- Debug simulator build-for-testing: passed, including app, unit test, and UI test targets.

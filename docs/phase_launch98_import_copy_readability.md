# Phase Launch98 Import Copy Readability

## Goal

Make the first import screen easier to read on small iPhones and larger Dynamic Type settings.

## Change

- Let the main import button status wrap up to three lines so long Photos import messages do not clip.
- Switched the four import feature pills from a fixed two-column grid to an adaptive grid.
- Let feature pill labels wrap to two lines with stable minimum heights.
- Let the target highlight help copy wrap to three lines.

## Architecture

- iOS still only handles import, preview, status, review, share, and cloud controls.
- Cloud remains responsible for analysis, GPT clip selection, edit planning, rendering, and storage.
- No local video analysis, rendering, composition, export logic, or timestamp logic was added.

## Validation

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch98-derived-data CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch98-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing
```

Result on 2026-05-31:

- `git diff --check`: passed.
- Debug simulator build: passed.
- Debug simulator build-for-testing: passed, including app, unit test, and UI test targets.

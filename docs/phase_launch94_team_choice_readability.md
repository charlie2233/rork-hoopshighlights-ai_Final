# Phase Launch94 Team Choice Readability

## Goal

Make the pre-analysis team choice easier to use on small iPhones and with larger text sizes, while preserving the cloud-first analysis pipeline.

## Change

- Replaced the tight horizontal team-choice row with an adaptive grid.
- Let scanned team status text wrap instead of truncating jersey-color labels.
- Let team button labels use two lines for longer detected labels.
- Increased team button height for accessibility text sizes.

## Why

The team choice is part of the accuracy path: users must confirm `All teams` or a detected jersey-color team before analysis. If labels are squeezed or hidden, users can pick the wrong team or think the app is stuck.

## Architecture

- iOS still only displays team choices and sends structured selection.
- Cloud still owns team scan, analysis, clipping, edit planning, rendering, and storage.
- No local analysis, rendering, export, or timestamp logic was added.

## Validation

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-team-choice-derived-data CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-team-choice-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing
```

Result on 2026-05-31:

- `git diff --check`: passed.
- Debug simulator build: passed.
- Debug simulator build-for-testing: passed, including app, unit test, and UI test targets.

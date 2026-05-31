# Phase Launch96 History Card Readability

## Goal

Make saved projects easier to read and reopen on small iPhones and larger text sizes.

## Change

- Replaced the horizontal scrolling History badges with adaptive wrapping badge grids.
- Let project update dates, team labels, export badges, and action buttons wrap instead of hiding text.
- Switched History action buttons to an adaptive grid so Open/Delete remain easy to tap on narrow screens.
- Updated the project detail sheet so metrics, timeline timestamps, and long source/status/team rows wrap cleanly.

## Architecture

- iOS still only displays saved project state and opens/previews local saved files.
- Cloud remains responsible for analysis, GPT edit planning, rendering, storage, and revisions.
- No local video analysis, rendering, export, or timestamp logic was added.

## Validation

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch96-derived-data CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch96-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing
```

Result on 2026-05-31:

- `git diff --check`: passed.
- Debug simulator build: passed.
- Debug simulator build-for-testing: passed, including the app, unit test, and UI test targets.

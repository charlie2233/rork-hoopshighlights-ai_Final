# Phase Import2: File-Backed Import Polish

## Goal

Reduce the real-device "Preparing video" hang after importing large videos from Photos or Files.

## Changes

- Kept Photos import file-backed. No `Data.self` video fallback is used.
- Kept support for `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie` file representations.
- Moved project creation/persistence for imported videos through a background `ProjectHistoryStore` inside a detached task.
- Left UI state changes in `HighlightsViewModel` on the main actor after the persisted project is ready.

## Architecture

- iOS still only imports, stores a local project copy, previews, uploads, and shows status.
- No iOS analysis, AI edit planning, rendering, composition, or export logic was added.
- Cloud remains responsible for analysis, GPT clip selection, edit planning, rendering, revisions, and storage.

## Expected Impact

Large video imports should no longer tie up the main actor while the project directory, source video copy/move, metadata read, and thumbnail creation are happening. The import card should keep updating, and successful imports should open without requiring an app restart.

## Validation

Completed local commands:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build-for-testing
```

Results:

- `git diff --check` passed.
- iOS Debug simulator build passed.
- iOS Debug simulator `build-for-testing` passed.

## Real-Device Follow-Up

Retest on iPhone with a long Photos video:

1. Import from Photos.
2. Confirm the status card advances past Preparing video.
3. Confirm the project opens without force quitting.
4. Confirm History contains only one project copy for that import.

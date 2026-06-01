# Phase Launch192 - History Share Readability

## Goal

Make the History project detail sheet easier to use on small iPhones and larger Dynamic Type settings.

## Change

- Shortened project action copy:
  - `Play Latest Export` -> `Play Export`
  - `Share Latest Export` -> `Share`
  - long helper subtitles -> short action-oriented subtitles
- Reduced empty preview copy to `Choose Source or Export below.`
- Made History detail action rows stack vertically at accessibility Dynamic Type sizes so titles and subtitles have room to wrap.
- Added line limits and scale factors to action title/subtitle text so words remain visible instead of being squeezed.
- Added a small `HistoryProjectActionCopy` source of truth with a focused test for readable copy length.

## Architecture

- This is iOS control-surface polish only.
- No local video analysis, rendering, composition, export, or AI planning logic was added.
- Share still uses the existing iOS share sheet for the saved export file.

## Validation

Run locally:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testHistoryProjectActionsUseShortReadableCopy
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build-for-testing
```

Results:

- `git diff --check`: passed.
- Focused `testHistoryProjectActionsUseShortReadableCopy`: passed after tightening the SwiftUI helper to return its composed row explicitly.
- Debug `build-for-testing`: passed.

## Launch Note

This improves the History/Share usability path but does not complete internal TestFlight readiness. The launch gate still needs real installed-app smoke and live cloud render proof.

# Phase iOS Import Recovery Readability

## Goal

Make real-device import testing less frustrating on large Photos videos and keep the import screen readable on small iPhones and larger Dynamic Type.

This does not change HoopClips cloud-first architecture. iOS still only imports local source files, shows status, and hands analysis/editing/rendering to the backend.

## Changes

- The Photos import path remains file-backed only. No full-video `Data` fallback was added.
- The import title and subtitle wrap with explicit line limits, scaling, and fixed vertical sizing so translated or larger text does not hide.
- After the first slow-import reminder, HoopClips now exposes the `Check History` recovery action instead of waiting for the longer 45-second reminder.
- The slow-import copy now says: `Still copying the video. If it already finished, check History.`
- The History shortcut first tries to reconcile a completed import, then opens History. This helps the case where iOS finished saving the project but the import screen still looks busy.
- The cancel action uses the same adaptive action layout as the History shortcut, so both controls remain tappable and readable on narrow screens.
- Added stable accessibility identifiers for the import recovery buttons:
  - `import.status.checkHistoryButton`
  - `import.status.cancelButton`

## User Impact

On real iPhone testing, imports sometimes completed successfully but the import surface stayed visible until the app was restarted. The existing recovery code could reconcile saved projects, but the user-facing History escape hatch appeared too late. This makes the recovery route visible earlier without changing video processing ownership or pretending the backend/import has done work it has not done.

If a tester sees a long `Preparing video` / `Still saving the project` state, they can check History directly instead of force-closing and reopening the app.

## Validation

Run after this change:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=A46E2157-77ED-42CE-959D-65C068681A47' build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=A46E2157-77ED-42CE-959D-65C068681A47' build-for-testing
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=A46E2157-77ED-42CE-959D-65C068681A47' test-without-building -only-testing:HoopsClipsTests
```

Recommended device smoke when an iPhone is connected:

1. Import a large Photos video.
2. Wait for the slow import status card.
3. Tap `Check History`.
4. Confirm saved project appears if the import completed in the background.
5. Confirm Cancel still stops an active import.

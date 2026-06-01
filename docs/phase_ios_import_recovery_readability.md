# Phase iOS Import Recovery Readability

## Goal

Make real-device import testing less frustrating on large Photos videos and keep the import screen readable on small iPhones and larger Dynamic Type.

This does not change HoopClips cloud-first architecture. iOS still only imports local source files, shows status, and hands analysis/editing/rendering to the backend.

## Changes

- The import title and subtitle now wrap with explicit line limits, scaling, and fixed vertical sizing so translated or larger text does not hide.
- When a video import is long-running, HoopClips now shows a `Check History` action inside the import status card.
- The History shortcut first tries to reconcile a completed import, then opens History. This helps the case where iOS finished saving the project but the import screen still looks busy.
- The cancel action now uses the same adaptive action layout as the History shortcut, so both controls remain tappable and readable on narrow screens.

## User Impact

If a tester sees a long `Preparing video` / `Still saving the project` state, they can check History directly instead of force-closing and reopening the app.

## Validation

Run after this change:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=A46E2157-77ED-42CE-959D-65C068681A47' build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=A46E2157-77ED-42CE-959D-65C068681A47' build-for-testing
```

Recommended device smoke when an iPhone is connected:

1. Import a large Photos video.
2. Wait for the long-running status card.
3. Tap `Check History`.
4. Confirm saved project appears if the import completed in the background.
5. Confirm Cancel still stops an active import.

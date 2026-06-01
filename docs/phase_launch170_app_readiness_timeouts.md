# Phase Launch170 - App Readiness Timeouts

Branch: `codex/phase-launch170-app-readiness-timeouts`

## Goal

Reduce user-facing friction from the cloud editing status/version check on Export AI Edit. The status probe should be quick background validation, not something that makes the user feel stuck before rendering.

## Implemented

- Reduced the iOS cloud edit version/status request timeout from 30 seconds to 8 seconds.
- Kept existing behavior where status-check timeouts do not block AI Edit rendering.
- Updated the CloudEditService contract test to assert the faster timeout.

## Import Audit

The current Photos import path already has the important large-video safeguards:

- File-backed Photos transfer only.
- No `Data.self` fallback.
- Supports `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- Persisted project copy runs off the main actor.
- Import watchdog recovers if the video finishes loading while the UI is still showing import progress.

## Tests

- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:HoopsClipsTests/CloudEditServiceTests` passed.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17'` passed.
- `git diff --check` passed.

## Launch Notes

- No cloud rendering behavior changed.
- No secrets, storage keys, or presigned URLs are exposed.
- No local iOS analysis/rendering/composition was added.

# Phase Launch173 Stability Feedback Context

## Goal

Make internal TestFlight crash/random-quit reports easier to act on without exposing secrets or media URLs.

## Change

- `LaunchTelemetry` now stores a sanitized support summary when the previous app session did not end in a normal terminal state.
- Settings > Support shows an `App health note` when that summary exists.
- The Support form includes the sanitized stability summary in the feedback payload.
- A `Report app quit` button switches the form to bug-report mode and prefills a concise diagnostic note.

## Safety

The summary uses existing HoopClips redaction for:

- URLs
- upload/edit object keys
- signed query values
- long failure text

No presigned URLs, R2 credentials, tokens, source file URLs, or media payloads are included.

## Validation

Run locally:

```bash
git diff --check
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:HoopsClipsTests/LaunchTelemetryTests
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17'
```

## Launch Note

This does not diagnose every crash by itself. It gives internal testers a low-friction path to report where the app was and what checkpoint was last recorded, which should make random-quit triage faster.

# Phase Launch157 - Account Session Reset

## Goal

Tighten the signed-out/account-switch path so a previous user's active HoopClips video, clips, team targeting, cloud edit source, and verification state cannot leak into the next visible session.

## Architecture Guardrails

- iOS remains the control surface for import, review, export configuration, preview, download, and share.
- No local AI analysis, cloud rendering, GPT planning, or FFmpeg behavior changed.
- No secrets, credentials, or presigned URLs are logged.

## Changes

- `AuthService.signOut()` now clears transient auth state before removing the persisted user:
  - loading state
  - error message
  - email verification code
  - phone verification code
  - pending email verification target
  - pending phone verification target
- `AuthService.setUser(_:)` clears stale loading/error state when a new user is accepted.
- Added iOS regression coverage for:
  - sign-out clearing stale verification state
  - project reset clearing visible video, clips, export URL, cloud source, team selection, and opponent state.

## Validation

Fresh local validation:

- `git diff --check` passed.
- Targeted Debug simulator test passed on iPhone 17 Pro simulator:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch157-derived-data test -only-testing:HoopsClipsTests/HoopsClipsTests/testSignOutClearsTransientVerificationState -only-testing:HoopsClipsTests/HoopsClipsTests/testResetProjectClearsVisibleVideoForAccountBoundary CODE_SIGNING_ALLOWED=NO`
  - Result: `** TEST SUCCEEDED **`

## Launch Notes

This reduces the chance that testers see the previous account's project after signing out and signing into a different account. It does not replace the required real-device TestFlight smoke.

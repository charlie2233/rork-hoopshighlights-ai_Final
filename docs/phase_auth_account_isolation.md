# Phase Auth Account Isolation

## Goal

Fix the launch-readiness issue where signing out and signing in with another account could leave the old video or Cloud Locker state visible.

## Changes

- `HighlightsViewModel` now supports auth-scoped cloud install IDs.
- The root app applies the current auth scope on launch, sign-in, sign-out, and account switch.
- Account boundary resets now always send the user back to Player and hide paywall state, even when no visible project is loaded.
- `AIEditView` clears local AI Edit jobs, previews, revision state, render history, share URLs, and locker errors when the cloud identity changes.

## Privacy Behavior

- Signed-out state keeps the legacy install ID key for backward compatibility.
- Authenticated users get stable per-account cloud IDs stored locally with a hashed auth-scope defaults key.
- Cloud Edit / Cloud Locker requests still use the backend `installID` field, but iOS now supplies an account-scoped value.
- No videos are analyzed, rendered, or composed locally for this change.
- No secrets, R2 credentials, or presigned URLs are logged.

## Validation Plan

- `git diff --check`
- Targeted iOS tests for auth-scoped install IDs.
- iOS Debug build-for-testing.

## Launch Notes

This does not replace backend auth. It reduces same-device account leakage risk for the current internal TestFlight path by separating Cloud Locker/Edit identity per signed-in user and clearing local AI Edit state on identity change.

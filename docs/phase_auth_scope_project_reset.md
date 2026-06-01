# Phase Auth Scope Project Reset

## Goal

Fix the tester-reported case where signing out and signing into another account can leave the previous account's video visible in the player.

## Change

- Added a persisted visible-project auth scope key in `ContentView`.
- On app launch, HoopClips compares the current auth scope against the last scope that was allowed to show a project.
- If the scope changed while the app was closed, the player state is cleared before the main app opens.
- Live sign-out/account-switch flows still clear the player and return to the Player tab.
- `VideoPlayerView` is keyed by auth scope so local `AVPlayer` and import state do not survive account changes.
- Added `HighlightsViewModel.clearVisibleProjectForAuthenticationBoundary()` so auth resets clear the visible project without re-saving it as the active project for the next account.
- Split the selected-team cloud edit reserve gate so strong matched clips still reach GPT, low-signal matched clips do not crowd the candidate pool, and uncertain team clips remain reviewable when the user allows them.

## Privacy

The persisted scope marker uses the existing hashed/scoped install-ID key derivation instead of storing the raw auth user ID. No secrets, credentials, or presigned URLs are logged.

## Evidence Commands

```bash
git status --short --branch
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-import-history-bft CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation build-for-testing -quiet
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-import-history-bft CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -only-testing:HoopsClipsTests
```

## Evidence Result

Verified locally on 2026-06-01:

- `git diff --check` passed.
- `HoopsClipsTests` passed on iPhone 17 Pro simulator with 139 tests.
- Debug `build-for-testing` passed for generic iOS Simulator.

## Manual Smoke

Recommended on device:

1. Sign in as account A.
2. Import a video and confirm it appears in Player.
3. Sign out and confirm the app returns to the import/home player state.
4. Sign in as account B.
5. Confirm account A's video is not still visible in Player.
6. Force quit and reopen while signed into account B.
7. Confirm account A's video is still not restored as the current player video.

## Remaining Work

- Project history is still local-device history, not a fully per-account cloud locker. That should be handled in the Cloud Locker phase.
- This phase does not change cloud analysis, GPT selection, rendering, or storage.

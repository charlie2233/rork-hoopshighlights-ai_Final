# Phase Launch193 - Cloud Status Nonblocking

## Goal

Make Export/AI Edit simpler and less scary when the lightweight cloud status check times out before a real edit request.

## Change

- Added `CloudEditStatusRefreshPolicy` for iOS Export status checks.
- Transient version-check failures now stay as warnings:
  - URL timeout
  - gateway timeout / `http_504`
  - temporary HTTP 408/429/500/502/503 style responses
- Real configuration failures still block rendering:
  - missing cloud edit config
  - invalid version response
  - auth/non-transient backend errors
- Shortened the user-facing transient copy to:
  - `Cloud status is slow. You can still start the edit.`

## Architecture

- iOS remains the control surface only.
- A failed status ping does not fake backend work or fake readiness.
- The actual edit/render request still uses the real cloud job response and can fail honestly if the backend is down.
- No local rendering, analysis, composition, or export was added.

## Validation

Commands:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditStatusRefreshPolicyDoesNotBlockTransientVersionFailures -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditStatusRefreshPolicyBlocksRealConfigFailures
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build-for-testing
```

Results:

- `git diff --check`: passed.
- Focused `CloudEditStatusRefreshPolicy` tests: passed.
- Debug `build-for-testing`: passed.

## Launch Note

This improves the "Cloud editing version check failed; request timed out" experience, but it does not prove launch readiness by itself. Internal TestFlight still needs a real installed-app cloud render smoke.

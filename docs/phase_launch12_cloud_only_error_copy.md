# Phase Launch12: Cloud-Only Error Copy

Date: 2026-05-23
Branch: `codex/phase-launch12-cloud-only-error-copy`

## Goal

Keep iOS AI Edit launch copy aligned with the cloud-first architecture. When the backend disables live rendering, iOS must show a real cloud-disabled state and must not imply a local render fallback for AI Edit.

## Changes

- Updated the iOS friendly backend message for `ai_edit_live_render_disabled`.
- Removed the phrase `local render fallback` from the AI Edit live-render disabled path.
- Strengthened the iOS unit test so the message must mention the cloud-paused state and must not contain `local render` or `fallback`.

## Validation

Commands:

```bash
git diff --check
Build iOS Apps plugin: test_sim HoopsClips Debug iPhone 17 Pro with -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditKillSwitchErrorsHaveFriendlyMessages CODE_SIGNING_ALLOWED=NO
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -skip-testing:HoopsClipsUITests -skip-testing:HoopsClipsUITestsLaunchTests CODE_SIGNING_ALLOWED=NO -resultBundlePath /tmp/hoopclips-launch12-unit.xcresult
xcrun xcresulttool get test-results summary --path /tmp/hoopclips-launch12-unit.xcresult
```

Results:

- `git diff --check`: passed.
- Build iOS Apps targeted selector returned success but reported `0` tests counted, so it was not used as proof.
- `xcodebuild test` with UI tests skipped succeeded.
- `/tmp/hoopclips-launch12-unit.xcresult`: `result=Passed`, `totalTestCount=61`, `passedTests=61`, `failedTests=0`, `skippedTests=0`.
- `HoopsClipsTests/testCloudEditKillSwitchErrorsHaveFriendlyMessages()` passed in the log.
- No iOS local analysis/rendering/composition/export behavior changes.
- No backend render behavior changes.

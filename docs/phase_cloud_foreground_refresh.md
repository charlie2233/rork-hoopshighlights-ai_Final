# Phase Cloud Foreground Refresh

Branch: `codex/phase-cloud-foreground-refresh`

## Goal

Make the "you can switch apps after cloud handoff" promise easier to trust during internal TestFlight smoke. When users leave HoopClips and come back, the app should reconnect to real backend state instead of leaving old analysis or AI Edit status on screen.

## Change

- Player foreground return now attempts to resume an in-flight cloud analysis job through `HighlightsViewModel.resumeInFlightCloudAnalysisIfNeeded()`.
- The resume path is guarded so only one foreground resume task runs at a time.
- AI Edit foreground return now refreshes cloud edit version/status and Cloud Locker render history.
- AI Edit syncs the currently visible render from fetched backend history when the render job or active revision matches.
- Added `CloudEditForegroundRefreshPolicy` so render-history matching is deterministic and unit-testable.

## Architecture Notes

- iOS still does not analyze, plan, render, compose, or export production video locally.
- The app only refreshes real backend job state after the cloud handoff has happened.
- No fake ETA, fake thinking text, artificial waits, full video GPT upload, FFmpeg command generation, or local render fallback was added.
- Import/upload still asks users to keep HoopClips open until handoff; cloud analysis and cloud AI Edit can continue after the backend job starts.

## Validation

Local validation completed on June 2, 2026 without using GitHub Actions:

```bash
xcodebuildmcp test_sim -only-testing:HoopsClipsTests
xcodebuildmcp build_sim
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' -derivedDataPath /Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClipsCodex build-for-testing CODE_SIGNING_ALLOWED=NO
git diff --check
```

Results:

- `HoopsClipsTests`: 175 passed, 0 failed, 0 skipped.
- Debug simulator build: passed.
- Debug build-for-testing: passed.
- `git diff --check`: passed.
- Test result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-02T08-13-37-184Z_pid26025_cae7c2b5.xcresult`.
- Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-02T08-15-07-066Z_pid26025_f929d836.log`.

## Remaining Launch Notes

- Needs real-device/TestFlight smoke where the tester starts cloud analysis, switches apps, returns, and confirms Review updates from backend state.
- Needs the same smoke for AI Edit render/revision: start render, switch apps, return, confirm latest preview/share state from real backend status.

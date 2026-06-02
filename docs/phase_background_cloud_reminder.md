# Phase Background Cloud Reminder

Branch: `codex/phase-background-cloud-reminder`

## Goal

Make it clear to testers that cloud analysis and AI Edit jobs keep running after cloud handoff, even if they switch to another app. The app should not imply local iOS rendering or fake progress.

## What Changed

- Tightened AI Edit reminder copy before starting a render:
  - cloud source is ready
  - start AI Edit
  - safe to switch apps after that
  - HoopClips keeps the cloud job attached
- Tightened queued/rendering guidance in AI Edit status:
  - cloud job keeps running
  - user can switch apps
  - reopen HoopClips for latest status or finished video
- Expanded iOS regression tests for AI Edit background reminder copy.

## Existing Behavior Confirmed

- Analysis upload still tells users to keep HoopClips open during upload.
- After cloud handoff, analysis reminder says it is safe to switch apps.
- AI Edit uses `scenePhase` foreground refresh to update cloud version and render history when the app becomes active again.
- Render history sync reconnects visible render state from backend render rows.

## Architecture Notes

- The backend owns analysis, planning, rendering, and storage.
- iOS does not run local analysis, rendering, composition, or export for these cloud jobs.
- The copy avoids fake "thinking", fake ETA, and artificial wait claims.

## Validation

Local validation completed on June 2, 2026 without using GitHub Actions:

```bash
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests/HoopsClipsTests
XcodeBuildMCP build_sim
git diff --check
```

Results:

- Focused iOS tests: passed, 138 tests.
- Debug simulator build: passed.
- `git diff --check`: passed.

Evidence:

- Test result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-02T08-58-01-220Z_pid26025_3e920b3c.xcresult`
- Test build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-06-02T08-58-01-220Z_pid26025_7e2cb98a.log`
- Debug build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-02T08-59-30-502Z_pid26025_06002745.log`

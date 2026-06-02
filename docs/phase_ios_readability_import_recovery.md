# Phase iOS Readability Import Recovery

Branch: `codex/phase-ios-readability-next-fix`

## Goal

Make the Photos/import recovery path shorter, clearer, and more honest on small iPhone screens while preserving the cloud-first launch architecture.

## What Changed

- Tightened import status copy so long Photos imports do not hide or overflow important words.
- Changed the persistent import detail to tell users to keep HoopClips open while the local import is still running.
- Kept recovery action copy focused on `Check History`, matching the tester observation that a project can finish saving and appear after relaunch/history recovery.
- Kept the background-job promise attached only to real cloud analysis/edit jobs after upload or cloud handoff.

## Background Job Behavior

This phase does not add local background rendering or local analysis.

- Import/Photos handoff: users should keep HoopClips open until the source file is copied into the app.
- Cloud analysis: after upload/cloud handoff, backend analysis can keep running and HoopClips can reconnect to real job status.
- AI Edit/render: after the cloud edit or render job starts, HoopClips can reconnect to real render status/history.

Relevant existing copy and tests:

- `CloudAnalysisProgressCopy.detail(...)` tells users to keep HoopClips open during upload, then switch apps after cloud handoff.
- `CloudAnalysisProgressCopy.backgroundReminder(...)` says cloud analysis remains attached after handoff.
- `AIEditBackgroundJobCopy.reminder(...)` says AI Edit/render jobs keep running in cloud only when a cloud source exists.
- Tests assert this copy avoids fake "thinking", fake ETA, and local-job promises.

## Validation

Local validation completed on June 2, 2026 without using GitHub Actions:

```bash
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests/HoopsClipsTests
XcodeBuildMCP build_sim
git diff --check
python3 scripts/submission_readiness_preflight.py --skip-live --archive-path ios/build/HoopsClips-InternalStaging-Build14.xcarchive --json
```

Result:

- HoopClips unit target: passed, 138 tests, 0 failures.
- Debug simulator build: passed, 0 warnings, 0 errors.
- `git diff --check`: passed.
- Pre-commit local submission preflight: failed with `fail=7, pass=23, warn=4`.
  - One failure was expected because the branch still had tracked/untracked phase changes before commit.
  - Remaining failures were the known launch blockers listed below.

Evidence:

- Test result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-02T09-29-46-326Z_pid26025_a4d0ba19.xcresult`
- Test build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-06-02T09-29-46-326Z_pid26025_7c30e0f9.log`
- Debug build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-02T09-31-57-947Z_pid26025_6a227fe3.log`

The earlier focused filter selected zero tests, so it is not counted as evidence.

## Remaining Blockers

This is a copy/readability phase. It does not clear the remaining Apple submission gates:

1. Installed TestFlight smoke is still unproven on a real iPhone.
2. Launch-grade human label review and accuracy evidence are incomplete.
3. Latest CI/deploy preflight status still needs current green evidence before spending more GitHub Actions minutes.
4. Live staging Worker/editing route probes still need a controlled rerun when backend credentials and budget are ready.

# Phase iOS Copy Accuracy Guardrails

Branch: `codex/phase-ios-copy-compatibility-pass`

## Goal

Make HoopClips simpler on small phones while improving the cloud editor instructions that guide GPT-led clip selection.

## What Changed

- Shortened cloud analysis background/reminder copy so visible status text fits better on compact iPhones and larger Dynamic Type.
- Kept the background message honest:
  - uploads still ask users to keep HoopClips open
  - after upload/handoff, users can switch apps and reopen for real backend job status
- Tightened default AI Edit guardrails sent to the cloud editor:
  - prefer complete action-to-result clips
  - avoid late fragments
  - include makes, blocks, steals, turnovers, and stops
  - treat defense as valid without a made shot
  - use crowd/audio pops only as clues and verify the visual outcome
  - reject duplicates and dead-ball moments
- Updated the `Clear outcomes` quick prompt to nudge full action-to-result editing while still leaving strong uncertain plays for Review.

## Architecture Notes

- iOS still sends only user intent, status copy, selected team, template, duration, aspect ratio, and candidate metadata.
- Cloud/backend still owns analysis, GPT clip selection, EditPlan generation, validation, rendering, and storage.
- No local iOS video analysis, composition, rendering, or FFmpeg command generation was added.
- The prompt remains bounded by the backend `userPrompt` limit.

## Validation

Local validation completed on June 2, 2026 without using GitHub Actions:

```bash
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests/HoopsClipsTests
XcodeBuildMCP build_sim
git diff --check
python3 scripts/submission_readiness_preflight.py --skip-live --archive-path ios/build/HoopsClips-InternalStaging-Build14.xcarchive --json
```

Results:

- HoopClips unit target: passed, 138 tests, 0 failures.
- Debug simulator build: passed, 0 warnings, 0 errors.
- `git diff --check`: passed.
- Local submission readiness preflight: failed with `fail=5, pass=25, warn=3`.
  - Available iPhone device check passed.
  - Launch remains blocked by human-reviewed accuracy evidence, stale failed main workflows, stale deploy preflight SHA, and unproven installed TestFlight smoke.

Evidence:

- Test result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-02T18-39-59-583Z_pid26025_e63b2b9e.xcresult`
- Test build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-06-02T18-39-59-583Z_pid26025_28fd6e9d.log`
- Debug build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-02T18-41-27-650Z_pid26025_7fa6bb0b.log`

## Launch Notes

This is a UX/readability and cloud-edit-intent improvement. It does not clear launch gates for:

- installed TestFlight real-device smoke
- human-reviewed accuracy evidence
- current green deploy/upload workflow evidence
- live staging Worker/editing probes

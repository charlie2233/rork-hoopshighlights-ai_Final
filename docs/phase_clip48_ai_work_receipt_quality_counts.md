# Phase Clip48: AI Work Receipt Quality Counts

## Goal

Make internal beta evidence show whether uncertain selected-team clips and defensive highlights survived into the rendered AI Edit.

## Change

- AI Work Receipt now includes:
  - `teamUncertainCandidateCount`
  - `teamUncertainSelectedClipCount`
  - `defensiveSelectedClipCount`
- Receipt summary rows now call out selected uncertain-team clips and defensive highlights.
- iOS decodes the new receipt fields and continues displaying server-provided summary rows.

## Why

The product goal is not just to keep plausible blocks, steals, forced turnovers, and jersey-color edge cases in Review. Internal testers also need proof after render that the cloud editor included or excluded those clips intentionally. This improves launch smoke evidence without moving analysis, GPT selection, or rendering into iOS.

## Architecture

- Cloud remains responsible for clip quality signals, GPT selection, edit planning, rendering, and work receipts.
- iOS only decodes and displays receipt metadata.
- No local video analysis, rendering, composition, or FFmpeg command generation was added to iOS.

## Validation

- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/models.py services/editing/tests/test_editing_service.py`
  - Passed with no compiler output.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Passed: 86 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Passed: 40 tests.
- `mcp__xcodebuildmcp__.session_show_defaults`
  - Confirmed `ios/HoopsClips.xcodeproj`, scheme `HoopsClips`, Debug, simulator `iPhone 17 Pro` (`7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`), derived data `/tmp/hoopclips-clip45-dd`.
- `mcp__xcodebuildmcp__.build_sim` with `CODE_SIGNING_ALLOWED=NO`
  - Passed. Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-27T06-32-01-910Z_pid97875_3c37c238.log`.
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests`
  - Passed. `xcresulttool` summary: 71 passed, 0 failed, 0 skipped.
  - Result bundle: `/tmp/hoopclips-clip45-dd/Logs/Test/Test-HoopsClips-2026.05.26_23-32-30--0700.xcresult`.
- `git diff --check`
  - Passed with no whitespace errors.

## Launch Recommendation

During internal beta, compare these receipt counts with user Review decisions and labeled footage. Use `teamUncertainSelectedClipCount` as a recall-review signal, not as confirmed selected-team precision.

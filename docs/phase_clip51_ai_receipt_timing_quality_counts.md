# Phase Clip51: AI Receipt Timing Quality Counts

## Goal

Show timing/context quality evidence in the AI Work Receipt after render, so internal beta can audit whether selected clips avoid tiny or pre-basket-only windows.

## Change

- AI Work Receipt now includes:
  - `timingQualitySelectedClipCount`
  - `timingIssueCandidateCount`
  - `timingIssueSelectedClipCount`
- Receipt summary rows now call out selected clips with weak timing/context, or confirm selected clips passed context checks.
- iOS decodes the new receipt fields and continues displaying server-provided summary rows.

## Why

The offline evaluator now scores `clipTimingQuality`, but internal testers also need render-level evidence. This makes the cloud receipt show whether the final AI Edit selected clips with enough setup/outcome context, without moving analysis or rendering into iOS.

## Architecture

- Cloud remains responsible for timing checks, GPT selection, edit planning, rendering, and work receipts.
- iOS only decodes receipt metadata and displays server summary rows.
- No local iOS analysis, rendering, composition, or FFmpeg command generation was added.

## Validation

- `git diff --check` - passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` - 89 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` - 42 tests passed.
- Build iOS Apps `build_sim` with `CODE_SIGNING_ALLOWED=NO` - Debug simulator build succeeded for `HoopsClips` on iPhone 17 Pro.
- Build iOS Apps `test_sim` with `CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests` - 71 tests passed.

## Launch Recommendation

Use these receipt counts alongside the labeled `clipTimingQuality` eval. Treat timing issues as launch-smoke blockers for the affected footage until the clip window, candidate generation, or GPT selection path is corrected.

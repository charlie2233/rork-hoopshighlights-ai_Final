# Phase: AI Long Reel Quality + AI Edit Readability

Branch: `codex/phase-ai-long-reel-readability`

## Goal

Improve the real app and AI editing path, not logo work:

- Keep GPT-led 4:30 highlight edits from collapsing into a short best-of reel.
- Preserve more clear clips when the candidate pool supports a long requested reel.
- Make the AI Edit format controls readable on small phones and accessibility text sizes.

## Backend AI Changes

- Raised the very-long reel underfill target from 34 to 42 clips when the candidate pool is deep enough.
- Raised the very-long reel duration floor ratio from 55% to 67% of the requested duration.
- Added explicit GPT guidance for reels near 4:30: build a fuller offense/defense/transition/story edit instead of over-pruning to only the flashiest plays.
- Kept the existing cloud-only architecture: GPT still selects and plans from existing candidate clips and sampled keyframes only. It does not receive full videos and does not generate renderer commands.

## iOS App Changes

- Improved the AI Edit `Video Shape` buttons so title/subtitle text wraps at Dynamic Type sizes instead of clipping.
- Increased the adaptive grid minimum width and button height for small phones/accessibility sizes.
- Kept iOS as the control surface only: upload/status/options/preview/share. No local render or local analysis was added.

## Validation

Local validation completed without using GitHub Actions minutes:

- `git diff --check` passed.
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 77 tests.
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v` passed: 42 tests.
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v` passed: 57 tests.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing` passed with `** TEST BUILD SUCCEEDED **`.

## Notes

- This does not spend GitHub Actions minutes.
- Unrelated root Xcode folders remain untracked and unstaged.

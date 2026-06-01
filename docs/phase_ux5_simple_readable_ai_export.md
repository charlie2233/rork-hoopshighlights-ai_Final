# Phase UX5: Simple Readable AI Export

Date: 2026-06-01
Branch: `codex/phase-ux5-simple-readable-ai-export`

## Goal

Keep the work focused on app usability and AI clipping quality. No icon/logo work is included in this phase.

## Changes

- Simplified the AI Edit prompt area by hiding optional quick examples behind a single "Show edit examples" control.
- Made AI Edit option headers wrap better for Dynamic Type and smaller phones.
- Raised GPT long-reel underfill guardrails so 4:30 edits require a deeper kept-clip story when the candidate pool supports it.
- Documented that broad GPT candidate review can stay high while Free daily edit chances remain 3.

## Architecture

- Cloud backend still owns GPT clip selection, edit planning, validation, rendering, storage, and revision logic.
- iOS remains a control surface for export configuration, status, preview, download, and share.
- GPT still receives compact candidate metadata and sampled keyframes only.
- No full videos, FFmpeg commands, storage keys, or raw renderer instructions are sent to or accepted from GPT.

## Evidence

- `git diff --check` passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py` passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_long_target_duration_requires_deeper_gpt_backfill_floor services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_underfilled_gpt_result_falls_back_when_full_pool_was_sampled services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_caps_are_applied_before_openai_call -v` passed: 3 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 76 tests.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination generic/platform=iOS\ Simulator build-for-testing` passed with `** TEST BUILD SUCCEEDED **`.

## Remaining Blockers

- Real installed iPhone/TestFlight smoke is still needed for import, team scan, Review, AI Edit, cloud render, preview, More Hype revision, revised preview, and share/open-in.
- The "Preparing video" Photos import hang still needs the file-backed import fix if it reproduces again.
- Launch-grade 85% selected-team/highlight accuracy still needs a labeled real-footage eval bundle.
- Live staging Worker/editing version and kill-switch probes still need to be rerun when the backend is deployed.


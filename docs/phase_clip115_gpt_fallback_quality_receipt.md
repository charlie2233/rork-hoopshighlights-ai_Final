# Phase Clip115: GPT Fallback Quality Receipt

## Goal

Make the AI Work Receipt honest when GPT-led highlight editing is disabled, missing credentials, or falls back before applying decisions. The fallback path should still show which clips remain render-worthy and which candidates were rejected for timing, team targeting, or manual-review uncertainty.

## What Changed

- `gpt_reranker._with_fallback` now populates fallback `keptClipIds`, `rejectedClipIds`, and `rejectedReasonCounts`.
- Fallback receipt evidence uses the same deterministic render-quality gate as EditPlan generation:
  - tiny clips are rejected
  - shot-like clips missing setup/outcome context are rejected
  - selected-team opponent clips are rejected
  - selected-team uncertain clips remain review-only instead of render-selected
- Blocks and steals that meet non-shot/defensive quality gates remain eligible in fallback receipts.

No renderer commands, source videos, presigned URLs, storage keys, or local paths are sent to GPT or logged. This is receipt/quality accounting only; deterministic rendering remains validator-bound.

## Validation

- Red check: `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_disabled_gpt_fallback_receipt_reports_quality_rejections -v` failed before implementation because fallback `keptClipIds` was empty.
- Green check: `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 57 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed: 184 tests.
- `/Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py` passed.
- `git diff --check` passed.

## Launch Notes

This improves internal QA visibility but does not prove the 85% launch target by itself. Submission still needs a labeled footage report covering selected-team mode, all-teams mode, made/missed shots, blocks, steals, opponent clips, uncertain-review clips, and bad timing windows.

# Phase Clip116: Fallback Receipt Surface

## Goal

Surface fallback clip-quality decisions in the AI Work Receipt so internal reviewers can see what happened when GPT-led editing is disabled or unavailable. This keeps review evidence honest for the exact launch risks the product cares about: tiny clips, pre-basket-only shot windows, selected-team opponents, uncertain team ownership, and defensive highlights.

## What Changed

- Feature-flag-disabled GPT now uses the same fallback quality receipt path as missing-key/source/API fallback.
- Fallback receipts now include:
  - render-worthy fallback clip count
  - rejected fallback clip count
  - rejected reason counts
  - summary rows for disabled/fallback reason, kept render-worthy clips, rejected quality/team reasons, and uncertain review candidates
- The existing raw receipt fields remain unchanged, so iOS continues to display server-provided `summaryRows` without schema churn.

Cloud ownership remains intact. The backend reports deterministic quality decisions and render state; iOS only displays the receipt/status.

## Validation

- Red check: `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_render_existing_edit_job_without_resending_plan -v` failed before implementation because feature-flag-disabled fallback reported `gptRerankKeptClipCount=0`.
- Green focused check: same test plus `test_ai_work_receipt_summarizes_gpt_fallback_quality_rejections` passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v` passed: 45 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 57 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed: 184 tests.
- `/Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/editing_app/main.py services/editing/editing_app/models.py services/editing/tests/test_editing_service.py services/editing/tests/test_gpt_reranker.py` passed.
- `git diff --check` passed.

## Launch Notes

This improves internal QA visibility and reduces the chance that fallback behavior hides bad clip windows. It still does not prove the 85% launch goal; that requires the real labeled footage report plus live TestFlight/cloud smoke evidence.

# Phase GPT Caption Outcome Guard

## Goal

Improve GPT-led edit quality by preventing validated clips from carrying misleading captions into the final EditPlan. A good steal, block, miss, or defensive stop should not render with a made-shot caption such as `BUCKET` just because GPT or `planEdit` suggested it.

## Change

- Added backend caption sanitation after GPT clip-decision validation.
- Empty GPT captions now fall back to a short outcome-safe caption.
- Captions that conflict with the validated outcome are replaced with an outcome-safe default:
  - `made`: `BUCKET`
  - `missed`: `GOOD LOOK`
  - `blocked`: `BLOCKED`
  - `steal`: `STEAL`
  - `forced_turnover`: `FORCED TURNOVER`
  - `defensive_stop`: `DEFENSIVE STOP`
- Non-conflicting defensive captions such as `MADE HIM MISS` are preserved.

## Architecture

This stays cloud-first. GPT can suggest captions, but backend validation still owns final EditPlan-safe text. The change does not add iOS analysis, iOS rendering, FFmpeg command generation, local composition, or full-video GPT upload.

## Validation

- Passed: focused GPT reranker caption tests.
- Passed: `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - 101 tests.
- Passed: `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - 110 tests.
- Passed: `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v`
  - 57 tests, including local render/revision coverage.
- Passed: `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py`
- Passed: `git diff --check`.

## Launch Note

This improves visible user quality and accuracy for final edits, especially defense/crowd-reaction workflows where GPT may correctly keep a clip but choose hype text that implies the wrong outcome.

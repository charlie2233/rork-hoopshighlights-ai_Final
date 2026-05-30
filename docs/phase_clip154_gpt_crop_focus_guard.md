# Phase Clip154 GPT Crop Focus Guard

Branch: `codex/phase-clip154-gpt-crop-focus-guard`

## Goal

Keep GPT-led edit suggestions inside deterministic cloud-renderer bounds by making `suggestedEdit.cropFocus` a closed renderer-safe enum. GPT can guide crop focus, but it cannot invent crop/render directives or smuggle commands through a free-form crop string.

## Changes

- Added shared `CropFocus` values: `center_action`, `ball`, `rim`, `shooter`, `team`, `source`.
- `GPTHighlightSuggestedEdit.cropFocus` now validates against that enum.
- `EditPlanClip.cropMode` now validates against the same enum.
- Vertical/widescreen plans normalize a GPT `source` crop request back to `center_action`; `source` remains reserved for source-aspect plans.
- The OpenAI structured output schema already exposed the same crop-focus enum; tests now lock that contract.

## Architecture Notes

- Cloud backend still owns GPT selection, edit planning, validation, and render execution.
- iOS behavior is unchanged.
- GPT still cannot output FFmpeg commands, shell commands, storage keys, or exact render instructions.
- Renderer execution remains deterministic: crop mode is selected from a known backend enum and interpreted by the FFmpeg renderer.

## Validation

Local validation run on this branch:

- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v` passed: 97 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 61 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v` passed: 53 tests, including local FFmpeg render paths.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v` passed: 50 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py` passed.
- `git diff --check` passed.

## Launch Impact

This is not the remaining TestFlight gate. It is a low-risk GPT edit-safety and quality guard that prevents malformed crop-focus suggestions from reaching the deterministic EditPlan path.

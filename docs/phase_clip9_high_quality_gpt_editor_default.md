# Phase Clip9 High Quality GPT Editor Default

## Goal

Bias HoopClips GPT-led highlight editing toward clip quality while cost is not the main constraint for the internal beta. The backend still owns GPT selection, edit planning, validation, rendering, and storage. iOS remains only the upload/review/status/preview/share control surface.

## Change

- Updated the default GPT highlight editor model from `gpt-4.1-mini` to `gpt-4.1`.
- Kept both environment overrides intact:
  - `HOOPS_AI_CLIP_GPT_MODEL`
  - `HOOPS_GPT_HIGHLIGHT_RERANK_MODEL`
- Added a regression test so the default stays quality-oriented unless explicitly overridden.
- Updated `services/editing/README.md` to document the new quality-beta default and override path.

## Rationale

The GPT editor is judging sampled basketball keyframes for setup, release/event, ball path, rim/outcome, watchability, caption quality, duplicate rejection, and story order. For this phase, a higher-quality vision-capable model is more aligned with the product goal than the mini default.

Official OpenAI docs list `gpt-4.1` as supporting image input, the Responses API, and Structured Outputs. That matches the existing HoopClips payload, which uses Responses API image inputs and strict JSON schema output.

## Validation Evidence

- Red test before implementation:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_default_model_prioritizes_full_quality_vision_editor -v`
  - Result before code change: failed because the default was `gpt-4.1-mini`.
- Green test after implementation:
  - Same command.
  - Result: passed.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 26 tests passed.
- Full editing service tests:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 66 tests passed.
- Hygiene:
  - `python3 -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py`
  - `git diff --check`
  - Result: passed.

## Launch Notes

- Staging/prod can still pin a different model through environment config without code changes.
- This phase does not send full videos to GPT, does not add iOS rendering, and does not let GPT generate FFmpeg commands.
- Watch OpenAI usage during internal beta because Free uses up to 8 clips and 8 keyframes per clip in the current quality-beta defaults.

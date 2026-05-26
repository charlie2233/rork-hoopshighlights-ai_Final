# Phase Clip15 Shot Trajectory Quality Context

## Goal

Improve GPT-led highlight selection by making the vision editor prove the basketball shot sequence more explicitly. A kept made or missed shot should show a visible shot release and a visible rim/result moment, not just a late basket frame, label, or implied outcome.

## Change

- Added `releaseVisible` to GPT highlight quality signals.
- Added `rimResultVisible` to GPT highlight quality signals.
- Updated the strict OpenAI Structured Outputs schema so both fields are required.
- Added shot-tracker payload guidance: made/missed shots require visible release and rim/result evidence.
- Added backend validation that rejects made/missed shot decisions when:
  - `releaseVisible` is false
  - `rimResultVisible` is false

## Architecture

- GPT still judges only existing candidate clips and sampled keyframes.
- GPT still cannot create timestamps, FFmpeg commands, file paths, URLs, or storage keys.
- The backend validator remains the source of truth before clips feed EditPlan generation.
- No iOS, rendering, storage, or local video processing behavior changed.

## Quality Rationale

This makes HoopClips closer to a real basketball shot tracker while keeping GPT in the final editor role. A model can now distinguish:

- setup visible, but release missing
- release visible, but rim/result missing
- rim aftermath visible, but no proof the shot went in
- complete setup, release, ball path, rim/result, and follow-through

That should reduce dumb clips that start right before a basket or overclaim a make from weak evidence.

## Validation Evidence

- Focused GPT payload/schema test:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment -v`
  - Result: 1 test passed.
- Focused backend validation test:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_kept_clips_without_full_shot_context -v`
  - Result: 1 test passed.
- Static compile:
  - `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py`
  - Result: passed.
- Final static checks:
  - `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py services/editing/tests/test_editing_service.py ios/backend/tests/test_edit_plan_agent.py && git diff --check`
  - Result: passed.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 30 tests passed.
- Backend edit-plan agent suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 54 tests passed.
- Backend suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 92 tests passed.
- Editing service suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 70 tests passed.

## Launch Notes

- This is a contract change for GPT output. Deploy with `ai_clip_gpt_editor_enabled` controlled by the existing feature flag.
- Existing deterministic fallback still works when GPT is disabled or unavailable.
- This branch does not prove live TestFlight or staging render readiness.

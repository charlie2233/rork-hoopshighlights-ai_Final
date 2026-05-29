# Phase Clip125: Non-Shot Action Context Floor

## Goal

Prevent fallback/deterministic cloud editing from selecting contextless non-shot action clips. A fast break, hustle play, loose ball, or generic highlight still needs enough setup and follow-through for the moment to make sense.

## What Changed

- Added shared non-shot action context thresholds:
  - minimum lead-in: `1.2s`
  - minimum follow-through: `0.8s`
  - minimum non-shot action duration: `2.5s`
- `nativeShotSignals.timingWindowOk` now reflects non-shot action context instead of passing every non-shot clip longer than `2.0s`.
- `is_plan_quality_eligible_clip` now requires non-shot action clips to pass duration, score, watchability, and event-context checks.
- Non-shot context scoring now caps contextless action clips below eligibility-quality levels.
- GPT non-shot sampling now imports the shared planner thresholds so GPT and deterministic fallback use the same floor.

## Why This Matters

GPT sampling already rejected generic action clips that started right on the event or ended before the play resolved. The fallback planner did not, so GPT-disabled or GPT-unavailable paths could still select a high-scoring but confusing action snippet. This phase makes the deterministic safety net match the GPT quality bar.

## Validation

- Red check before implementation:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_rejects_contextless_non_shot_action_clip -v`
  - Result: failed because `late_fast_break` was still plan-quality eligible with only `0.2s` of lead-in.
- Focused green checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_rejects_contextless_non_shot_action_clip ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_rejects_contextless_defensive_event_clip services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_quality_filter_keeps_generic_non_shot_on_strict_context_floor -v`
  - Result: 3 tests passed.
- Edit/GPT backend checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py`
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker -v`
  - Result: 150 tests passed.
- Service/pipeline checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service ios.backend.tests.test_pipeline_quality -v`
  - Result: 94 tests passed.
- Script checks:
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 78 tests passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.

## Launch Notes

This improves fallback clip quality for non-shot basketball action. It does not prove the 85% target by itself; launch still needs a real labeled cloud-path team/highlight accuracy report and installed TestFlight smoke.

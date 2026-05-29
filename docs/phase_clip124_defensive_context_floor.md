# Phase Clip124: Defensive Context Floor

## Goal

Prevent fallback/deterministic cloud editing from selecting blink defensive clips. Blocks, steals, forced turnovers, and defensive stops are valid highlights, but they still need visible setup and outcome context.

## What Changed

- Added shared defensive event context thresholds:
  - minimum lead-in: `0.6s`
  - minimum follow-through: `0.5s`
  - minimum defensive clip duration: `2.0s`
- `nativeShotSignals.timingWindowOk` now fails for defensive clips whose event center is too close to the start or end.
- `is_plan_quality_eligible_clip` now requires defensive clips to pass duration, score, and event-context checks.
- Defensive context scoring now caps contextless defensive events below eligibility-quality levels.
- GPT defensive sampling now imports the shared planner thresholds so GPT and deterministic fallback use the same floor.

## Why This Matters

The GPT path already rejects contextless blocks and steals before OpenAI review, but the deterministic fallback planner could still keep a high-scoring defensive label with no visible setup. This made the app more vulnerable when GPT is disabled, unavailable, or intentionally bypassed by a kill switch.

This does not make blocks and steals less important. It makes them better: a selected defensive highlight should show the challenge, possession/control change or result, and enough context for the user to understand the play.

## Validation

- Red check before implementation:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_rejects_contextless_defensive_event_clip -v`
  - Result: failed because `nativeShotSignals.timingWindowOk` was `True` for a block whose event center was `0.1s` after clip start.
- Focused green checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_rejects_contextless_defensive_event_clip ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_keeps_clear_non_shot_defense_clip services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_quality_filter_keeps_defensive_window_with_event_context_before_gpt -v`
  - Result: 3 tests passed.
- Edit/GPT backend checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py`
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker -v`
  - Result: 149 tests passed.
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

This improves the fallback quality floor for defensive highlights. It does not prove the 85% target by itself; launch still needs a real labeled cloud-path team/highlight accuracy report and installed TestFlight smoke.

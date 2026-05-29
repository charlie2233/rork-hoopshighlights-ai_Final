# Phase Clip52: Mixed Defensive Shot Event Quality

## Goal

Keep real defensive highlights when candidate labels mix defensive events with shot words, such as `Steal Finish` or `Steal Layup`.

## Change

- Added a shared defensive-event classifier for backend edit planning and GPT reranking.
- Defensive-event candidates now use defensive context expansion before shot context expansion.
- Defensive-event candidates with shot-like labels use defensive keyframes instead of shot-arc/rim-entry keyframes.
- Shot-context keyframe requirements no longer drop defensive-event clips just because their labels include words like `finish` or `layup`.
- GPT validation can keep `steal`, `forced_turnover`, and `defensive_stop` outcomes for mixed defensive/shot labels when quality signals and sampled defensive frame roles support the play.

## Why

The product goal is selected-team highlights that include blocks, steals, forced turnovers, and other defensive plays. A label like `Steal Finish` is not always a pure shot-tracker problem. If the event center is the steal or possession change, requiring shot-release/rim-entry proof can reject a good defensive highlight before GPT gets to judge it.

## Architecture

- Cloud remains responsible for candidate filtering, GPT frame sampling, GPT validation, edit planning, and rendering.
- iOS behavior is unchanged.
- GPT still uses sampled keyframes and structured JSON only.
- No full videos, FFmpeg commands, storage keys, or presigned URLs are sent to GPT.

## Validation

- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py` - passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_mixed_defensive_shot_labels_use_defensive_context_before_gpt ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_keeps_mixed_steal_finish_as_defensive_outcome ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_defensive_event_classifier_ignores_stop_and_pop_shot_label -v` - 3 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` - 90 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` - 133 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` - 42 tests passed.
- `git diff --check` - passed.

## Launch Recommendation

Keep this gate in the 85% labeled-footage eval set with examples for `Steal Finish`, `Steal Layup`, `Blocked Shot`, `Defensive Stop`, and opponent-team defensive plays. These examples should prove that selected-team defensive highlights are retained while opponent and low-confidence clips remain reviewable or rejected.

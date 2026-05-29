# Phase Clip44: Block Tracking Quality Gate

## Goal

Make GPT-kept block highlights require the same kind of visible event proof expected from a basketball tracker, instead of trusting a loose label or unclear contact moment.

## Change

- `blocked` GPT outcomes now require visible player/control evidence and visible ball path/control.
- GPT block tracking citations are checked against sampled frame roles, not just defensive-only role names.
- The GPT payload now tells the model that blocked shots require visible challenge, ball path/control, player control, and outcome evidence.

## Why

The user wants blocks and steals included, but only when the play is actually clear. A block without visible ball control or a sampled evidence role should stay out of the final AI edit rather than becoming a fake highlight. Uncertain team or event clips can still remain in Review before the final AI edit.

## Safety

- GPT still receives sampled keyframes and compact clip metadata only.
- GPT still cannot generate FFmpeg commands, file paths, URLs, storage keys, or renderer instructions.
- Rendering remains deterministic through the validated EditPlan path.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_block_without_visible_ball_control -v` -> 1 test passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_blocked_keep_requires_sampled_challenge_and_outcome_roles -v` -> 2 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_block_without_visible_ball_control ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_keeps_selected_and_uncertain_team_steals -v` -> 2 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 129 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 85 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 40 tests passed.
- `git diff --check` -> passed.
- `git diff --cached --check` -> passed.

## Launch Recommendation

Keep this gate enabled for internal beta. Labeled beta clips should include blocked shots with visible ball path, unclear contests, and sampled-role mismatch cases so the 85% target measures both recall and false-positive control.

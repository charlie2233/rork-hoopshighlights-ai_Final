# Phase Clip33: Defensive GPT Outcomes

## Goal

Make GPT-led highlight selection treat steals, forced turnovers, and defensive stops as real highlight outcomes instead of forcing them into `blocked` or `unclear`.

## Change

- GPT structured output now accepts:
  - `steal`
  - `forced_turnover`
  - `defensive_stop`
- The OpenAI payload explicitly tells GPT to use these outcomes for non-scoring defensive highlights.
- Backend validation keeps those defensive outcomes only when the clip has:
  - visible event and outcome
  - full play context
  - visible player and ball control
  - clean camera
  - minimum non-shot candidate quality
- Selected-team filtering still excludes confident opponent clips before GPT and before deterministic rerank application. Uncertain team-attribution clips remain reviewable when `includeUncertain` is true.
- Missed shots now require visible ball path, matching the made/missed shot-tracker-quality rule.

## Safety

GPT still cannot create clips, exact timestamps, FFmpeg commands, file paths, URLs, or storage keys. The renderer still executes only deterministic, validated `EditPlan` JSON.

## Validation

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_edit_plan_agent.py -v` -> 67 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services/editing/tests/test_gpt_reranker.py -v` -> 38 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 114 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 78 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 39 tests passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py` -> passed.
- `git diff --check` -> passed.

## Launch Recommendation

Include labeled steals, forced turnovers, defensive stops, blocks, makes, misses, opponent highlights, and uncertain jersey-color clips in the internal 85% accuracy eval set. Defensive clips should be judged separately from scoring clips so recall does not hide weak steal/turnover behavior.

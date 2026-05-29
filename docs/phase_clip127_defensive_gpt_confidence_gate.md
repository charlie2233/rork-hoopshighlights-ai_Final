# Phase Clip127: Defensive GPT Confidence Gate

## Goal

Make GPT-led defensive highlights more trustworthy. Steals, forced turnovers, and defensive stops should remain valid highlights, but GPT must provide confident defensive outcome evidence before those clips can enter the deterministic EditPlan.

## What Changed

- Added `MIN_GPT_DEFENSIVE_OUTCOME_CONFIDENCE = 0.65` to the shared backend editing validator.
- Rejected kept GPT decisions for `steal`, `forced_turnover`, and `defensive_stop` when `shotResultEvidence.outcomeConfidence` is below the defensive confidence floor.
- Added the same floor to the GPT reranker payload under `requiredDefensiveTracking.minimumOutcomeConfidence`.
- Updated GPT instructions to use `unclear` or `keep=false` when a non-scoring defensive outcome is guessed.
- Added regression coverage showing:
  - a steal with sampled challenge/possession-change/recovery roles but low defensive outcome confidence is rejected
  - the same steal with confident outcome evidence is kept
  - the OpenAI payload tells GPT about the defensive confidence floor

## Why This Matters

The user wants blocks and steals included, but not weak or guessed highlights. Shots already require visible release, ball flight, rim result, and confidence checks. This phase gives non-scoring defensive outcomes a comparable confidence gate so GPT cannot promote a questionable steal or stop just because the sampled roles are present.

## Validation

- Red check before implementation:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_defensive_keep_requires_sampled_possession_change_roles -v`
  - Result: failed because a low-confidence GPT steal was kept.
- Focused green check:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_defensive_keep_requires_sampled_possession_change_roles -v`
  - Result: 1 test passed.
- Payload + defensive validator focused check:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_defensive_keep_requires_sampled_possession_change_roles -v`
  - Result: 2 tests passed.
- Backend edit/GPT regression suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py && PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent services.editing.tests.test_editing_service -v`
  - Result: 198 tests passed.
- Pipeline quality suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Result: 48 tests passed.
- Script/preflight unit suite:
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 78 tests passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.

## Launch Notes

This improves defensive precision for selected-team and all-team edits. It does not prove the 85% target by itself; launch still needs a real labeled cloud-path team/highlight accuracy report across made shots, misses, blocks, steals, forced turnovers, opponent clips, uncertain review clips, and bad-window negatives.

# Phase Clip49: Blocked Shot Defensive Sampling

## Goal

Make GPT judge blocked-shot highlights from defensive event frames instead of generic shot/rim aftermath frames.

## Change

- Block-like clips now use defensive source-window expansion before GPT keyframe extraction, even when their label also contains `shot`.
- `Blocked Shot` candidates now sample defensive roles such as `challenge`, `possessionChange`, `recovery`, and `defenseOutcome`.
- Shot-like metadata is still preserved, so the validator can treat the play as a blocked shot while requiring visible challenge/outcome evidence.

## Why

The user goal is high-quality selected-team highlights that include blocks and steals, without tiny or late pre-basket clips. A label like `Blocked Shot` should be evaluated around the defender's challenge and the blocked outcome, not only around the shot/rim timing path. This improves GPT's visual evidence for blocks while keeping deterministic validation in the backend.

## Architecture

- Cloud remains responsible for source-window expansion, GPT keyframe sampling, GPT selection, validation, edit planning, and rendering.
- GPT still receives only sampled frames and compact candidate metadata.
- iOS behavior is unchanged.

## Validation

- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_blocked_shot_uses_defensive_context_and_keyframes_before_gpt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_blocked_shot_candidates_use_defensive_challenge_keyframes -v`
  - Passed: 2 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py`
  - Passed with no compiler output.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Passed: 88 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Passed: 131 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Passed: 40 tests.

## Launch Recommendation

Include labeled blocked-shot examples in the internal accuracy set, especially clips where the ball/rim aftermath is ambiguous but the defender challenge and possession result are visible.

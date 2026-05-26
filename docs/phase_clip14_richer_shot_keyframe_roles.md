# Phase Clip14 Richer Shot Keyframe Roles

## Goal

Improve GPT-led clip selection by giving the vision editor a fuller basketball story for each high-budget shot candidate. With 8 frames per clip, GPT should see setup, release, event/result, rim/outcome, and a post-outcome/reaction frame, not just generic mid-action context.

## Change

- Added a `postOutcome` sampled-keyframe role for 8-frame shot candidates.
- Made `postOutcome` a required shot-context role when the tier/settings provide 8 frames per clip.
- Kept lower-budget role requirements unchanged:
  - 7 frames: `preEvent`, `release`, `outcome`, `rim`
  - 6 frames: `preEvent`, `release`, `outcome`
  - 5 frames: `preEvent`, `outcome`
  - 4 frames: `preEvent`

## Quality Rationale

The user goal is not cheap clipping near a basket; it is better-than-basic basketball editing. The extra post-outcome frame helps GPT distinguish a clean make, miss, block, celebration/reaction, or dead aftermath after the ball/rim event. This should improve semantic keep/reject decisions, captions, and slow-motion suggestions while still sending only sampled keyframes from existing candidate windows.

## Validation Evidence

- Red tests before implementation:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_pro_sampling_adds_shot_setup_and_outcome_roles -v`
  - Result before code change: failed because `postOutcome` was missing from sampled roles and required shot-context roles.
- Green focused tests after implementation:
  - Same command.
  - Result: 2 tests passed.
- Regression fixture check:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_shot_candidates_missing_context_are_dropped_without_losing_complete_candidates -v`
  - Result: 1 test passed. Complete shot candidates keep the new `postOutcome` role, while incomplete candidates are still filtered before GPT.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 30 tests passed.
- Editing service suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 70 tests passed.
- Backend suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 92 tests passed.
- Static checks:
  - `python3 -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py && git diff --check`
  - Result: passed.

## Launch Notes

- No iOS code changed.
- No full videos are sent to GPT.
- No renderer, FFmpeg command-generation, storage, or presigned URL behavior changed.

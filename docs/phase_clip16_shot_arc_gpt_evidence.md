# Phase Clip16 Shot Arc GPT Evidence

## Goal

Make GPT-led clip selection more like a basketball shot tracker plus editor. The model should see enough sampled evidence to judge release, ball flight, rim/result, and aftermath instead of keeping clips that start right before a basket or only show late rim activity.

## Change

- Raised quality-beta GPT keyframe caps from 8 to 10 frames per clip:
  - Free: still up to 8 candidate clips, now up to 10 frames per clip.
  - Pro/internal: still up to 30 candidate clips, now up to 10 frames per clip.
- Added shot-arc sampled keyframe roles:
  - `shotArcEarly`
  - `shotArcLate`
- At the 10-frame budget, shot candidates now require:
  - `preEvent`
  - `release`
  - `shotArcEarly`
  - `outcome`
  - `shotArcLate`
  - `rim`
  - `postOutcome`
- Added `shotArcVisible` to GPT `qualitySignals`.
- Backend validation rejects made/missed shot decisions when GPT keeps a clip but says `shotArcVisible` is false.
- Sampled frames are returned in chronological order so GPT receives a cleaner visual sequence.

## Architecture

- GPT still receives only sampled JPEG keyframes from existing candidate clips.
- GPT does not receive full videos, source URLs, storage keys, presigned URLs, or FFmpeg commands.
- GPT may judge shot quality, captions, story order, crop focus, and slow-motion suggestions.
- Deterministic backend validation still owns whether GPT decisions can feed EditPlan generation.
- Renderer behavior is unchanged.

## Quality Rationale

HoopClips should not keep a clip just because the label says made shot or because the camera catches the rim after the play. The 10-frame sequence gives GPT enough visual context to compare:

- the shooter setup before the event
- the release frame
- early and late ball arc frames
- the rim/result frame
- post-outcome follow-through or reaction

That makes the expensive GPT path more useful for internal beta quality, especially when youth basketball footage has shaky camera motion, small balls, and unclear rim outcomes.

## Validation Evidence

- Focused GPT sampling and schema tests:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_pro_sampling_adds_shot_setup_and_outcome_roles services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits -v`
  - Result: 3 tests passed.
- Focused backend validation test:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_kept_clips_without_full_shot_context -v`
  - Result: 1 test passed.
- Static compile:
  - `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_editing_service.py`
  - Result: passed.
- Final static checks:
  - `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_editing_service.py && git diff --check`
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

- This intentionally increases GPT image payload cost in quality-beta mode.
- The existing `ai_clip_gpt_editor_enabled` kill switch still controls GPT reranking.
- Existing deterministic fallback still works when GPT is disabled, unconfigured, or unavailable.
- This branch does not prove live TestFlight or staging render readiness.

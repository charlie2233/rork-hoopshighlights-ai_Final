# Phase Clip18 Frame Role Shot Tracking Evidence

## Goal

Make GPT-led clip selection behave more like a basketball shot tracker plus editor. A kept made shot should not be accepted just because GPT says the make is visible; it must anchor that claim to sampled frame roles that show release, ball flight, rim/result, and ball entry or net/rim reaction.

## Change

- Added `shotTrackingEvidence` to GPT highlight decisions:
  - `ballVisibleFrameRoles`
  - `rimVisibleFrameRoles`
  - `releaseFrameRole`
  - `resultFrameRole`
  - `ballEntersRimFrameRole`
  - `netOrRimReactionVisible`
  - `trajectoryContinuity`
  - `reason`
- Updated the strict Structured Outputs schema so `shotTrackingEvidence` is required for every GPT decision.
- Added model-facing shot tracker rules:
  - made shots require release/result frame-role proof
  - made shots require at least two ball-visible tracking frames
  - made shots require continuous trajectory
  - made shots require a frame proving entry or visible net/rim reaction
- Added backend validation that rejects kept made/missed clips when GPT cannot provide frame-role tracking proof.
- Added a regression case for a made-shot claim with good broad quality signals and result evidence, but no sampled frame proving ball entry.

## Architecture

- GPT still receives only sampled JPEG keyframes from existing candidate windows.
- GPT does not receive full videos, source URLs, storage keys, presigned URLs, or FFmpeg commands.
- GPT may describe semantic shot tracking evidence from sampled frames.
- Backend validation owns whether GPT output is allowed into EditPlan generation.
- FFmpeg, CV/runtime candidate generation, exact timestamps, deterministic rendering, storage, and policy checks remain backend-owned.

## Quality Rationale

The previous phase required explicit result evidence, which prevents many guessed makes. This phase goes one level lower: GPT must name which sampled frame roles show the shot story. That gives the validator a stricter shape to reject:

- clips that only show a late rim or aftermath
- clips where GPT cannot identify the release frame
- clips where the ball is visible in too few sampled frames
- clips where the made-shot claim has no entry frame or net/rim reaction
- clips that have plausible labels but no trackable shot sequence

This intentionally favors beta quality over token/image cost.

## Validation Evidence

- Focused GPT schema tests:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_schema_matches_highlight_decision_contract -v`
  - Result: 2 tests passed.
- Focused backend validation test:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_kept_clips_without_full_shot_context -v`
  - Result: 1 test passed.
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

- Existing GPT kill switches and deterministic fallbacks still apply.
- This change does not enable public cloud cutover, TestFlight submission, or production rendering.
- Live staging proof still requires current deploy credentials and post-install smoke evidence.

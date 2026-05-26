# Phase Clip23 Shot Sequence Quality

## Goal

Tighten GPT-led highlight selection so made baskets are kept only when GPT cites a real shot sequence, not a generic late `finish` frame or a reaction-only aftermath. This continues the cloud-only clip-quality work: the backend owns GPT validation and EditPlan inputs; iOS stays a control surface.

## Change

- Added validation that rejects GPT decisions when `rimEntry` was sampled but `shotTrackingEvidence.ballEntersRimFrameRole` cites a generic frame such as `finish`.
- Made `netOrRimReactionVisible` supporting evidence only. It no longer replaces the required made-shot entry and follow-through frame-role citations.
- Updated GPT payload rules and instructions so the model must use `rimEntry` as the ball-entry tracking frame when sampled.
- Added regressions for both failure modes before changing production validation.

## Architecture

- GPT still receives only existing candidate clips and sampled JPEG keyframes.
- GPT may judge shot clarity and story value, but it cannot invent clip IDs, timestamps, FFmpeg commands, storage keys, source URLs, or render instructions.
- Deterministic backend validators still gate GPT output before EditPlan generation and cloud rendering.

## Validation Evidence

- Regression red/green:
  - `test_gpt_highlight_rerank_rejects_generic_ball_entry_tracking_when_rim_path_was_sampled` failed before the validator change, then passed.
  - `test_gpt_highlight_rerank_rejects_made_shot_without_followthrough_frame_even_with_net_reaction` failed before the validator change, then passed.
- Focused suites:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 60 tests passed.
- Syntax:
  - `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py services/editing/tests/test_editing_service.py`
  - Result: passed.
- Backend discovery:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 98 tests passed.
- Editing-service discovery:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 74 tests passed.
- Launch script/preflight discovery:
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 34 tests passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.

## Launch Notes

- This is backend-only quality hardening.
- No iOS analysis, rendering, composition, or export behavior changed.
- Existing GPT/editor feature flags and fallbacks still apply.

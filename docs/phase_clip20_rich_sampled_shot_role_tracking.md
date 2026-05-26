# Phase Clip20 Rich Sampled Shot Role Tracking

## Goal

Make GPT-led highlight selection behave more like a real shot tracker when the backend has already paid for richer sampled frames. If HoopClips sends `release`, shot-arc, `rim`, or `postOutcome` keyframes, GPT must use those specific roles as evidence instead of falling back to generic `eventCenter` and `finish` claims.

## Change

- Added backend validation for rich sampled shot roles:
  - sampled `release` requires `releaseFrameRole=release`
  - sampled `shotArcEarly` or `shotArcLate` requires at least one arc role in `ballVisibleFrameRoles`
  - sampled `outcome`, `shotArcLate`, `rim`, or `postOutcome` requires `resultFrameRole` to cite one of those richer result roles
  - sampled `rim` or `postOutcome` requires `rimVisibleFrameRoles` to cite a rim/post-outcome role
- Added GPT prompt/context rules telling the model to cite rich sampled roles when they exist.
- Added regression tests for:
  - direct backend rejection of generic frame-role proof when rich roles were sampled
  - full GPT reranker rejection when GPT ignores rich sampled release/rim evidence

## Architecture

- GPT still receives only existing candidate clip metadata plus sampled JPEG keyframes.
- GPT does not receive full videos, source URLs, storage keys, presigned URLs, local paths, or FFmpeg commands.
- The cloud backend still owns validation, EditPlan generation, rendering, storage, and policy.
- iOS behavior is unchanged.

## Quality Rationale

Earlier phases forced GPT to provide shot result evidence and frame-role tracking evidence. Phase Clip19 made sure GPT could not cite frame roles that were not sampled. This phase goes one step further: when richer roles are sampled, GPT must actually use them.

That matters for the user-visible failures we are trying to remove:

- a clip that starts right before the basket should not pass as a full made-shot highlight
- a late rim-only or aftermath-only clip should not pass because GPT says `finish` looks good
- a real made shot should show setup, release, ball flight, rim/result, and aftermath when those frames are available

This intentionally favors internal beta quality over minimizing the GPT vision payload.

## Validation Evidence

- Syntax and whitespace:
  - `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py services/editing/tests/test_editing_service.py`
  - `git diff --check`
  - Result: passed.
- Focused rich-role tests:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_generic_tracking_when_rich_roles_were_sampled services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_decision_must_use_rich_sampled_shot_roles_when_available -v`
  - Result: 2 tests passed.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 32 tests passed.
- Backend edit-plan agent suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 56 tests passed.
- Backend discovery suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 94 tests passed.
- Editing service discovery suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 72 tests passed.

## Launch Notes

- Existing GPT/editor kill switches and deterministic fallbacks still apply.
- This is a backend-only quality guardrail and does not enable public cloud cutover.
- Live staging proof still depends on deploy credentials, current Worker deployment, and installed TestFlight smoke evidence.

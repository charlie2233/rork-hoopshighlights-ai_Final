# Phase Clip22 Rim Entry Path Sampling

## Goal

Improve GPT-led clip selection by giving the model basketball-specific visual evidence for made-shot judgment. The model should not keep a made basket just because a generic rim, finish, or late aftermath frame looks plausible. At the quality-beta 10-frame budget, sampled frames now include a dedicated rim-entry path:

- `rimApproach`
- `rimEntry`
- `belowRim`

## Change

- Added dedicated rim-entry path frame roles to the backend `ShotTrackingFrameRole` contract.
- Updated GPT keyframe sampling so the 10-frame quality path captures setup, release, early arc, late arc, rim approach, rim entry, and below-rim follow-through.
- Updated GPT payload rules and strict schema so the model can cite dedicated rim-entry path roles.
- Updated backend validation so, when dedicated rim-entry path frames are sampled, GPT must cite those specific roles instead of generic `finish` or broad rim/result proof.
- Kept staging Cloud Build default `_AI_CLIP_GPT_KEYFRAMES_PER_CLIP=8` behind the existing launch gate; the richer 10-frame shot-tracker path is available only through an explicit quality-beta substitution override until live OpenAI/staging smoke proves it.

## Architecture

- Cloud backend owns keyframe extraction, GPT selection, validation, EditPlan generation, rendering, storage, and policy.
- GPT still receives only existing candidate clips plus sampled JPEG keyframes.
- GPT does not receive full videos, source URLs, storage keys, presigned URLs, local paths, or FFmpeg commands.
- iOS remains unchanged: upload, status, preview, download, share, and user controls only.

## Validation Evidence

- Syntax:
  - `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_editing_service.py`
  - Result: passed.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 34 tests passed.
- Backend edit-plan agent suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 58 tests passed.
- Backend discovery:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 96 tests passed.
- Editing-service discovery:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 74 tests passed.
- Launch script/preflight discovery:
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 34 tests passed.

## Launch Notes

- This is backend-only quality hardening and does not enable public cloud cutover.
- Staging defaults remain conservative. Use an explicit deploy-time substitution override for `_AI_CLIP_GPT_KEYFRAMES_PER_CLIP=10` during quality-beta smoke.
- Existing GPT/editor kill switches and deterministic fallbacks still apply.
- CI remains dependent on GitHub Actions being able to check out the repository.

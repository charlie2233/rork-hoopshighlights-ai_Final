# Phase Clip10 Uncertain Shot Caption Sanity

## Goal

Keep HoopClips fallback edit captions honest when the native/CV pipeline only has enough evidence for a shot attempt. The cloud backend still owns analysis, GPT selection, edit planning, validation, rendering, and storage. iOS remains the upload/review/status/preview/share control surface.

## Change

- Added a regression test for deterministic fallback edit planning with a candidate labeled `Shot Attempt`.
- Updated fallback caption selection so uncertain shot, jumper, three, or layup attempts use `GOOD LOOK`.
- Preserved `BUCKET` only for labels that already claim a shot or bucket without the uncertain attempt wording.

## Rationale

Recent quality work made the native classifier stop overclaiming made shots when the source evidence only shows setup, release, motion, or incomplete outcome context. The deterministic fallback planner still captioned any label containing `shot` as `BUCKET`, which could turn a carefully uncertain `Shot Attempt` into an overconfident made-basket caption.

This keeps fallback captions aligned with the stronger CV/GPT outcome gates: attempts are valid highlight candidates, but they should not be marketed as makes unless the analysis or GPT-validated edit result supports that outcome.

## Validation Evidence

- Red test before implementation:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_does_not_caption_uncertain_shot_attempt_as_bucket -v`
  - Result before code change: failed because the fallback caption was `BUCKET`.
- Green test after implementation:
  - Same command.
  - Result: passed.
- Edit-plan suite:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 51 tests passed.
- Pipeline-quality suite:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Result: 17 tests passed.
- Full backend suite:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -v`
  - Result: 88 tests passed.
- Full editing service suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 66 tests passed.
- Hygiene:
  - `python3 -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py`
  - `git diff --check`
  - Result: passed.

## Launch Notes

- No iOS code changed.
- No renderer behavior, FFmpeg commands, video upload paths, or GPT prompt payloads changed.
- This complements the GPT-led editor by keeping the non-GPT fallback path quality-safe when GPT is disabled or unavailable.

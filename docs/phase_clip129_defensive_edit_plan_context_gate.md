# Phase Clip129: Defensive EditPlan Context Gate

## Goal

Prevent GPT revisions or future plan-edit patches from rendering defensive highlights that are clipped too tightly around the event. Blocks and steals should include setup plus visible outcome/recovery context, not a tiny slice that starts on the steal or cuts away before the result.

## What Changed

- Extended `EditPlan` validation in `ios/backend/app/editing.py` for defensive clips:
  - `defensive_context_missing_setup` when the rendered source window starts too close to the event center.
  - `defensive_context_missing_outcome` when the rendered source window ends before enough defensive outcome context is visible.
- Applied the defensive check before shot-like validation so labels such as `Blocked Shot` follow the defensive context floor.
- Added a regression test that mutates an otherwise valid plan into two bad defensive trims:
  - a steal that begins only 0.1s before the event.
  - a steal that cuts away 0.4s after the event.

## Validation

- Red check before implementation:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_edit_plan_validation_rejects_trimmed_defensive_context -v`
  - Result: failed because `defensive_context_missing_setup` was missing.
- Second red check:
  - Same focused command after adding the outcome assertion.
  - Result: failed because `defensive_context_missing_outcome` was missing.
- Focused green check:
  - Same focused command.
  - Result: passed.
- Editing service suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v`
  - Result: 48 tests passed.
- GPT/edit-plan/pipeline quality suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent ios.backend.tests.test_pipeline_quality -v`
  - Result: 199 tests passed.
- Compile check:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/tests/test_editing_service.py`
  - Result: passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.
- Clean submission preflight:
  - `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Result: `pass=22 warn=2 fail=8`.
  - Remaining blockers: missing launch-grade labeled footage report proving 85% selected-team/highlight quality, unavailable connected iPhone for installed smoke, skipped live Worker/editing probes, stale main-branch CI relative to this commit, unproven installed TestFlight smoke, unproven Worker editing route, missing Cloudflare deploy credential proof, and unproven live iOS kill-switch state through the Worker.

## Launch Notes

This is a backend/render-safety guard only. It does not change iOS responsibilities and does not move analysis or rendering onto the device. It makes final cloud plans more robust against dumb defensive highlight trims while preserving blocks and steals as valid highlight families when they have enough context.

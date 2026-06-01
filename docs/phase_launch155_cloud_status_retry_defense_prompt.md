# Phase Launch155 Cloud Status Retry and Defense Prompt Accuracy

## Goal

Make Export AI Edit easier to trust on slower networks and improve GPT-led defense intent when users ask for turnovers or loose-ball plays.

## Changes

- Added a visible `Retry status check` button when the non-blocking cloud status check fails.
- Improved wrapping and scaling for the AI Edit cloud status message and active work phrase so words stay visible on smaller phones and accessibility text sizes.
- Expanded backend user-prompt intent detection so `turnovers`, `deflections`, `charges`, `takeaways`, `loose ball`, and `pressure` map to defense-focused GPT editing.
- Updated iOS default AI Edit guardrail copy and the `Focus defense` quick prompt to include forced turnovers.

## Architecture

- iOS still only retries the cloud `/v1/editing/version` status check and sends user intent.
- Backend/cloud remains responsible for GPT clip selection, EditPlan validation, rendering, and storage.
- No iOS analysis, rendering, composition, or local export behavior was added.
- The retry button does not fake backend work; it starts a real status request.

## Validation

Passed on June 1, 2026:

```sh
git diff --check
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_user_prompt_turnover_language_maps_to_defense_focus -v
python3 -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py
XcodeBuildMCP build_sim
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests
```

- Backend turnover/defense intent test passed: 1 passed, 0 failed.
- Python compile passed for `ios/backend/app/editing.py` and `ios/backend/tests/test_edit_plan_agent.py`.
- iOS Debug simulator build passed with no warnings.
- `HoopsClipsTests` passed: 121 passed, 0 failed, 0 skipped.

## Launch Notes

- A real-device TestFlight smoke still needs to verify that the status retry stays readable and that cloud renders complete from the real staging backend.

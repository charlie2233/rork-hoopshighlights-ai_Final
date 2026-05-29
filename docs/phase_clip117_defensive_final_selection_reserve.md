# Phase Clip117: Defensive Final Selection Reserve

## Goal

Keep selected-team highlight edits from becoming scoring-only reels when strong blocks or steals are present but ranked below several made shots. The backend should still favor complete, high-confidence clips, but a short final EditPlan should preserve defensive highlight variety for the chosen team.

## What Changed

- `select_best_clips` now reserves one block-family and one steal-family clip when GPT has not supplied explicit story ordering.
- The reserve only uses clips that already passed duplicate removal and plan-quality filtering.
- The reserve appends a defensive clip when target duration allows, or replaces the weakest non-defensive, non-GPT-anchored selected clip when the reel is already full.
- Defensive family detection covers blocked shots, blocks, contests, steals, strips, and forced defensive turnovers.
- GPT-led story order remains authoritative when present; this hardening only improves deterministic fallback planning.

This keeps the cloud-first boundary intact. iOS still sends reviewed candidate metadata and selected-team intent; cloud backend owns final clip selection, EditPlan validation, rendering, storage, and quality receipts.

## Validation

- Red check before the implementation:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_short_selected_team_plan_reserves_blocks_and_steals_when_scoring_fills_reel -v`
  - Failed because the 30s selected-team reel selected only scoring clips: `dark_make_1`, `dark_make_2`, `dark_make_5`, `dark_make_3`.
- Green focused checks:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_short_selected_team_plan_reserves_blocks_and_steals_when_scoring_fills_reel ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_plan_keeps_defensive_blocks_and_steals ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_applies_story_order_to_edit_plan ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_story_order_opener_and_closer_survive_short_reel_cutoff -v`
- Green backend suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Passed 185 tests.
- Green GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Passed 57 tests.
- Green editing service suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v`
  - Passed 45 tests, including local render, revision, retention, and render-history privacy checks.

## Launch Notes

This improves fallback edit quality for selected-team reels, especially when users want team-specific highlights that include defensive plays. It does not replace the remaining submission gates: real-device TestFlight smoke, live staging Worker/version/kill-switch proof, Cloudflare deploy credential proof, current main workflow proof, and launch-grade labeled footage accuracy evidence remain required before App Store submission.

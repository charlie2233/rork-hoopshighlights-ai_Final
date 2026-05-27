# Phase Clip39: Defensive Team Scan Frame Roles

## Goal

Improve team attribution for blocks, steals, forced turnovers, and defensive stops during the pre-analysis team scan. These plays should belong to the defender's team, and uncertain ownership should remain reviewable instead of being guessed.

## Change

- Team Quick Scan now labels defensive clip keyframes with ownership-aware roles.
- Blocks and contests sample:
  - `defenseSetup`
  - `challenge`
  - `defenseOutcome`
- Steals, strips, forced turnovers, defensive stops, pressure, and lockdown clips sample:
  - `defenseSetup`
  - `possessionChange`
  - `recovery`
- The OpenAI quick-scan payload now includes a compact `defensiveFrameRoles` rule explaining how those roles should be used.
- Non-defensive clips keep the existing `startContext`, `eventCenter`, `finishContext`, and `midAction` sampling.

## Safety

- GPT still receives only sampled JPEG frames and compact candidate metadata.
- GPT still cannot receive full videos, storage keys, presigned URLs, or renderer commands.
- iOS behavior is unchanged: upload, choose team, start analysis, review clips.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_defensive_quick_scan_samples_possession_change_roles ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_frame_extraction_uses_defensive_roles_for_blocks_and_steals ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_payload_can_attribute_expanded_selected_team_candidate_pool -v` -> 3 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 123 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 40 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 84 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use this with action-anchored team quick scan and the labeled accuracy harness. Do not claim the 85% target until labeled footage proves selected-team precision, selected-team recall with uncertain clips, highlight precision/recall, and defensive-event recall.

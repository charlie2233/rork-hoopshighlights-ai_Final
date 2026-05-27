# Phase Clip41: Offensive Team Scan Frame Roles

## Goal

Improve selected-team attribution for made shots, layups, dunks, jumpers, and finishes during the pre-analysis team quick scan.

## Change

- Scoring candidate clips now use ownership-aware quick-scan frame roles:
  - `ballHandlerSetup`
  - `release`
  - `rimResult`
  - `followThrough`
- The Team Quick Scan prompt tells GPT to use setup/release frames to identify the shooter or finisher team, then use rim result/follow-through to confirm the play.
- Defensive roles from the previous phase still take priority for blocks, steals, forced turnovers, and defensive stops.

## Safety

- GPT still receives only sampled JPEG frames and compact candidate metadata.
- GPT still cannot receive full videos, storage keys, presigned URLs, file paths, or FFmpeg instructions.
- iOS behavior is unchanged.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_scoring_quick_scan_samples_shooter_release_roles ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_frame_extraction_uses_scoring_roles_for_made_shots ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_payload_can_attribute_expanded_selected_team_candidate_pool -v` -> 3 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 126 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 85 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 40 tests passed.

## Launch Recommendation

Use this with defensive team-scan roles and action-anchored candidate sampling. The 85% target still requires labeled footage evaluation before any public accuracy claim.

# Phase Clip60 Scan-Backed Team Start Guard

## Goal

Make selected-team analysis require a cloud quick-scan-backed team option. A stale client, malformed request, or skipped scan should not be able to start selected-team analysis and then keep every unattributed clip as uncertain.

## Behavior

- Team quick scan results are now persisted on the analysis job as `detected_teams` plus `team_scan_status`.
- Starting analysis with `teamSelection.mode = "team"` requires at least one persisted detected team.
- The selected team must match a persisted quick-scan team by `teamId` or `colorLabel`.
- If no scan-backed option exists, the backend returns `team_scan_required`.
- If the selected team does not match scan-backed teams, the backend returns `team_selection_unavailable`.
- `All teams` still starts without team scan.

## Product Impact

This is a defense-in-depth guard for the user-facing team picker. iOS already hides team choices until jersey colors are detected, but the backend now enforces the same rule. Uncertain clips remain reviewable only after the user chooses a real detected team, which better supports selected-team precision while preserving recall for ambiguous blocks, steals, and scoring plays.

## Validation

- `python3 -m py_compile ios/backend/app/api.py ios/backend/app/job_store.py ios/backend/app/models.py ios/backend/tests/test_team_quick_scan.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_start_rejects_selected_team_without_scan_backed_option ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_start_rejects_selected_team_not_returned_by_scan ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_start_all_teams_does_not_require_team_scan ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_team_scan_endpoint_runs_before_start_and_start_accepts_selection -v` -> 4 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 149 tests passed.

## Launch Notes

Keep this guard enabled for internal beta. It does not prove the 85% real-world target by itself; that still requires labeled footage evals covering selected-team makes, misses, blocks, steals, confident opponent clips, and uncertain jersey-color clips.

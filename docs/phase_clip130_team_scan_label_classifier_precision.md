# Phase Clip130: Team Scan Label Classifier Precision

## Goal

Improve quick-scan team attribution precision before analysis starts. The team scanner should use shooter/rim-result frames for offensive shot labels like `Stop and Pop Jumper`, and should not treat a plain `Turnover` as a defensive highlight unless the label says forced, defensive, steal, or strip.

## What Changed

- Tightened `ios/backend/app/team_quick_scan.py` label classification:
  - `Stop and Pop Jumper` now follows scoring ownership roles: ball-handler setup, release, rim result, and follow-through.
  - Plain `Turnover` now follows generic event context instead of defensive ownership frames.
  - `Forced Turnover`, steals, strips, pressure, lockdown, and defensive-stop labels still follow defensive ownership roles.
- Added regression tests in `ios/backend/tests/test_team_quick_scan.py` so this cannot drift back.

## Why This Matters

The user chooses a team from the quick scan before analysis. If the quick scan asks GPT to judge the wrong ownership frames, selected-team analysis can start from bad labels. This phase prevents a common basketball phrase, `stop and pop`, from being misread as a defensive stop, while still preserving real blocks, steals, and forced turnovers.

## Validation

- Red check before implementation:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_stop_and_pop_jumper_uses_scoring_roles_not_defensive_stop ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_plain_turnover_uses_generic_roles_not_defensive_ownership -v`
  - Result: failed because both labels were using defensive ownership roles.
- Focused green check:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_defensive_quick_scan_samples_possession_change_roles ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_stop_and_pop_jumper_uses_scoring_roles_not_defensive_stop ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_plain_turnover_uses_generic_roles_not_defensive_ownership -v`
  - Result: 3 tests passed.
- Team quick-scan suite:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v`
  - Result: 31 tests passed.
- Pipeline quality suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Result: 48 tests passed.
- Compile check:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py`
  - Result: passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.
- Clean submission preflight:
  - `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Result: `pass=22 warn=2 fail=8`.
  - Remaining blockers: missing launch-grade labeled footage report proving 85% selected-team/highlight quality, unavailable connected iPhone for installed smoke, skipped live Worker/editing probes, stale main-branch CI relative to this commit, unproven installed TestFlight smoke, unproven Worker editing route, missing Cloudflare deploy credential proof, and unproven live iOS kill-switch state through the Worker.

## Launch Notes

This keeps cloud analysis in charge. No iOS local analysis or rendering was added. The change improves the cloud quick scan that feeds the iOS team chooser and selected-team analysis.

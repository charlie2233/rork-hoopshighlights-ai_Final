# Phase Clip126: Turnover Defensive Guard

## Goal

Keep defensive highlight accounting honest for turnovers. Blocks, steals, forced turnovers, and defensive stops should count as defensive highlights, but a plain or unforced turnover should not be promoted as defense from label text alone.

## What Changed

- Tightened `is_defensive_event_like_clip` so plain `Turnover` and `Unforced Turnover` are not defensive events.
- Preserved defensive classification for:
  - blocks and blocked shots
  - steals and strips
  - defensive stops
  - explicit defense/pressure/lockdown clips
  - forced or defensive turnovers
- Removed the old broad defensive token tuple that made `turnover` and `forced` independently defensive.
- Added receipt coverage so AI Work Receipt does not report a defensive highlight for plain turnover clips.

## Why This Matters

The user asked for blocks and steals to be real highlights, and for team-selected reels to be accurate. Counting a plain turnover as defense can inflate defensive recall, mislead the AI Work Receipt, and make a selected-team reel look better than it is. This guard keeps defensive accounting tied to clear defensive action or validated GPT outcomes.

## Validation

- Red check before implementation:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_defensive_event_classifier_requires_forced_or_defensive_turnover_context services.editing.tests.test_editing_service.EditingServiceTests.test_ai_work_receipt_does_not_count_plain_turnover_as_defense -v`
  - Result: failed because plain `Turnover` was classified and counted as defense.
- Focused green checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_defensive_event_classifier_requires_forced_or_defensive_turnover_context services.editing.tests.test_editing_service.EditingServiceTests.test_ai_work_receipt_does_not_count_plain_turnover_as_defense ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_plan_keeps_defensive_blocks_and_steals -v`
  - Result: 3 tests passed.
- Backend edit/GPT regression suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_editing_service.py && PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_editing_service services.editing.tests.test_gpt_reranker -v`
  - Result: 198 tests passed.
- Pipeline quality suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Result: 48 tests passed.
- Script/preflight unit suite:
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 78 tests passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.
- Submission readiness preflight:
  - `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Result: `pass=22 warn=2 fail=8`.
  - Remaining blockers:
    - Missing launch-grade labeled footage team/highlight accuracy report; 85% selected-team/highlight quality is still unproven.
    - Connected iPhone is detected but unavailable for install/smoke testing.
    - Live Worker and direct editing probes were intentionally skipped.
    - Main-branch Cloud Edit Deploy Preflight and iOS Internal TestFlight Upload workflow runs are stale relative to this checkout.
    - Installed TestFlight smoke, live Worker route, Cloudflare deploy credential proof, and live iOS kill-switch proof remain documented launch blockers.

## Launch Notes

This improves selected-team and AI Work Receipt precision for defensive highlights. It does not prove the 85% target by itself; launch still needs a real labeled cloud-path team/highlight accuracy report and installed TestFlight smoke.

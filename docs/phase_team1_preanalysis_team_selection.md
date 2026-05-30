# Phase Team1 Preanalysis Team Selection

## Goal

Verify and harden the HoopClips flow where users pick which team the highlight is for before full analysis starts.

## Current Architecture

- iOS imports the video and immediately starts a cloud team quick scan when cloud analysis is enabled.
- The scan uploads the source once, samples frames in the cloud, and asks the backend/GPT team scan to label teams by jersey color.
- iOS then shows `All teams` plus detected jersey-color teams before the Analyze button.
- Analysis is blocked until the user confirms `All teams` or one detected team.
- Cloud analysis receives the selected `teamSelection`; iOS does not do local team detection, local analysis ownership, rendering, or export composition.
- `mode=all` keeps highlights from both teams and does not require a detected team.

## Accuracy Behavior

- Team quick scan sends sampled frames and candidate metadata only, never full videos, storage keys, full URLs, or FFmpeg commands to GPT.
- For scoring clips, ownership is the shooter/finisher team.
- For blocks, steals, defensive stops, and forced turnovers, ownership is the defender who made the play.
- Selected-team filtering keeps confident selected-team clips and removes confident opponent clips.
- When `includeUncertain=true`, uncertain clips stay in Review with auto-keep and slow-motion disabled.
- When `includeUncertain=false`, uncertain clips are excluded from the selected-team review pool.

## Changes

- Added backend tests proving create-time selected-team intent survives the upload/team-scan/start split even when `/start` does not resend `teamSelection`.
- Added backend tests proving create-time `All teams` can start without a team scan.
- Added selected-team filtering tests proving blocks and steals are kept for the selected team, opponent clips are excluded, and uncertain clips are either review-only or excluded depending on `includeUncertain`.

## Validation

Focused tests:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest \
  ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_create_time_selected_team_survives_scan_and_start_without_resending_selection \
  ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_create_time_all_teams_starts_without_scan \
  ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_selected_team_filter_keeps_defensive_clips_and_excludes_uncertain_when_disabled \
  ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_selected_team_filter_keeps_uncertain_for_review_but_disables_auto_keep
```

Result: 4 tests passed.

Broader backend tests:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests
```

Result: 202 tests passed.

Additional checks:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/tests/test_team_quick_scan.py`
- `git diff --check`
- `python3 scripts/submission_readiness_preflight.py --json`

Submission preflight result:

- Git hygiene passed on branch `codex/phase-team1-preanalysis-team-selection`.
- Still blocked by launch-grade team accuracy evidence, unavailable connected iPhone smoke, stale staging Worker `/v1/editing/version`, stale live editing feature flags/gitSha, and the secret-gated deploy preflight needing provider repair.

## Launch Recommendation

Keep this cloud-first behavior for internal TestFlight: imported video -> cloud team quick scan -> user picks `All teams` or detected jersey-color team -> cloud analysis -> Review. Do not add iOS-side team analysis. The remaining launch blocker for proving 85% selected-team quality is a labeled footage run through `scripts/evaluate_team_highlight_accuracy.py`.

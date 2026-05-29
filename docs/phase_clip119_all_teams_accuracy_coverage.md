# Phase Clip119: All-Teams Accuracy Coverage

## Goal

Make the launch accuracy gate cover both user choices after import: a selected jersey-color team and `All teams`. The product promise is not only "pick one team"; users can also choose all teams, and blocks/steals should still count as highlights in that mode.

## What Changed

- `evaluate_team_highlight_accuracy.py` now includes `allTeamsCaseCount` in metrics and evidence.
- Default launch thresholds now require at least one all-teams eval case through `minAllTeamsCases=1`.
- Eval cases now carry explicit `teamMode` (`team` or `all`); preflight rejects reports with missing team-mode evidence.
- `build_team_highlight_eval_payload.py` now emits `teamMode` from labels or cloud analysis `teamSelection`.
- Defensive recall now counts all-teams defensive highlights by normal keep/review behavior instead of selected-team ownership confidence.
- Submission preflight now requires `minAllTeamsCases` to be default-or-stricter and rejects reports missing `casesMissingTeamMode`.

## Why This Matters

Without this gate, a launch report could pass while only proving selected-team behavior. That would leave the `All teams` path under-tested, including whether all-team edits keep valid blocks and steals instead of treating them as out-of-scope selected-team events.

## Validation

- Red checks before implementation:
  - selected-team-only default readiness report passed when it should fail without all-teams coverage.
  - evaluator had no `allTeamsCaseCount` metric.
  - all-teams defensive recall failed because kept blocks/steals were still gated by selected-team confidence.
- Green focused checks:
  - `python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_default_readiness_requires_all_teams_coverage scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_selected_team_eval_counts_uncertain_review_and_defensive_events scripts.test_build_team_highlight_eval_payload.BuildTeamHighlightEvalPayloadTests.test_build_payload_matches_real_analysis_predictions_and_review_uncertain_clip scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_team_accuracy_report_passes_launch_grade_default_evidence -v`
  - `python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_all_teams_defensive_recall_uses_keep_without_selected_team_gate -v`
- Green script suite:
  - `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/build_team_highlight_eval_payload.py scripts/submission_readiness_preflight.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py scripts/test_submission_readiness_preflight.py`
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 76 tests passed.

## Launch Notes

This improves what the 85% report must prove. It still does not create the real labeled-footage report or remove the live launch blockers. Submission remains blocked until the scan-backed report passes on real footage and the TestFlight/device/cloud checks are proven current.

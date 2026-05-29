# Phase Clip118: Scan-Backed Accuracy Evidence

## Goal

Make the 85% selected-team/highlight accuracy gate prove the actual product flow: a cloud quick scan finds jersey-color team options, the user chooses a team, then analysis/highlight selection runs for that team. A launch report should not pass if it only proves generic cloud analysis output without scan-backed team-choice evidence.

## What Changed

- `build_team_highlight_eval_payload.py` now carries scan evidence into each eval case:
  - `teamScanJobId`
  - `selectedTeamColorLabel`
  - normalized `detectedTeams`
- `evaluate_team_highlight_accuracy.py` now reports missing scan-choice evidence:
  - `casesMissingTeamScanJobId`
  - `casesMissingDetectedTeamOptions`
  - `casesMissingSelectedTeamColorLabel`
  - `casesMissingSelectedTeamDetectedOption`
- `submission_readiness_preflight.py` now rejects launch accuracy reports where any of those scan-evidence counts are missing or nonzero.
- Tests cover the payload builder, evaluator evidence summary, and preflight rejection for reports that skip the quick-scan team chooser proof.

## Why This Matters

The user-facing flow depends on choosing `All teams` or a detected jersey-color team before analysis. The old readiness evidence could prove the 85% metrics against labeled cloud output, but it did not prove that each case came from the pre-analysis team scan. This phase makes the launch gate stricter without exposing video URLs, storage keys, secrets, or presigned URLs.

## Validation

- Red checks before implementation:
  - evaluator test failed because `AccuracyEvidenceSummary` had no scan evidence fields.
  - payload builder test failed because `teamScanJobId`, `selectedTeamColorLabel`, and `detectedTeams` were absent.
  - preflight test failed because missing quick-scan evidence was accepted.
- Green focused checks:
  - `python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_selected_team_eval_counts_uncertain_review_and_defensive_events -v`
  - `python3 -m unittest scripts.test_build_team_highlight_eval_payload.BuildTeamHighlightEvalPayloadTests.test_build_payload_matches_real_analysis_predictions_and_review_uncertain_clip -v`
  - `python3 -m unittest scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_team_accuracy_report_rejects_missing_quick_scan_evidence -v`
- Green script suite:
  - `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/build_team_highlight_eval_payload.py scripts/submission_readiness_preflight.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py scripts/test_submission_readiness_preflight.py`
  - `python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_build_team_highlight_eval_payload scripts.test_submission_readiness_preflight -v`
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 74 tests passed.

## Launch Notes

This does not create the real labeled footage report; it makes the report harder to fake or accidentally weaken. Internal launch still needs a real scan-backed, cloud-path labeled run that passes default thresholds and covers selected-team makes, misses, blocks, steals, forced turnovers, opponent highlights, uncertain-review clips, and bad timing windows.

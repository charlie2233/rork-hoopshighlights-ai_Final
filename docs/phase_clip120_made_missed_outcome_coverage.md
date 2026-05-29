# Phase Clip120: Made/Missed Outcome Coverage

## Goal

Make the launch accuracy gate prove valid shot-tracker-style coverage for both made and missed shots. A report should not pass from generic shot-outcome evidence if it never proves a clear miss or never proves a made basket.

## What Changed

- `evaluate_team_highlight_accuracy.py` now tracks:
  - `madeShotOutcomeEvidenceClipCount`
  - `missedShotOutcomeEvidenceClipCount`
- Default thresholds now require:
  - `minMadeShotOutcomeEvidenceClips = 1`
  - `minMissedShotOutcomeEvidenceClips = 1`
- The CLI accepts explicit overrides for small fixtures:
  - `--min-made-shot-outcome-evidence-clips`
  - `--min-missed-shot-outcome-evidence-clips`
- `submission_readiness_preflight.py` now checks those thresholds and metrics in launch reports.
- The eval fixture now includes a valid missed jumper with visible ball path, rim/result, and clear-miss evidence.
- Made/missed coverage is credited only after the shot outcome evidence validator passes, so weak or label-only shot records do not satisfy the hard-case gate.

## Why This Matters

The user goal calls out shot-tracker quality: HoopClips should know when the ball goes in and should avoid bad pre-basket clips. Made shots and missed shots fail in different ways, so launch proof needs both families. This keeps the 85% gate from being satisfied by only easy made buckets, blocks, or aggregate shot evidence.

## Validation

- Red checks before implementation:
  - a default readiness report with no missed-shot clip still passed.
  - the evaluator had no made/missed outcome evidence counters.
  - a missed-shot clip with invalid rim/result evidence could satisfy the family coverage counter.
- Green checks:
  - `python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_default_readiness_requires_missed_shot_outcome_coverage scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_selected_team_eval_counts_uncertain_review_and_defensive_events scripts.test_build_team_highlight_eval_payload.BuildTeamHighlightEvalPayloadTests.test_build_payload_matches_real_analysis_predictions_and_review_uncertain_clip scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_team_accuracy_report_passes_launch_grade_default_evidence -v`
  - `python3 -m unittest scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_team_accuracy_report_requires_hard_case_metrics -v`
  - `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/build_team_highlight_eval_payload.py scripts/submission_readiness_preflight.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py scripts/test_submission_readiness_preflight.py`
  - `python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_build_team_highlight_eval_payload scripts.test_submission_readiness_preflight -v`
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`

## Launch Notes

This is an evidence-gate hardening step. It does not replace the real labeled-footage run or live TestFlight/cloud smoke proof. The launch report still needs real cloud-analysis outputs joined to manual labels, with selected-team mode, all-teams mode, made shots, missed shots, blocks, steals, opponent highlights, uncertain review clips, and bad-window negatives.

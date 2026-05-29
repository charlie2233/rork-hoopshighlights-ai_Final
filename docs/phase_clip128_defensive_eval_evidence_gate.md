# Phase Clip128: Defensive Eval Evidence Gate

## Goal

Make the 85% launch-grade accuracy report prove defensive GPT outcome quality, not just recall. Steals, forced turnovers, and defensive stops should count as real highlights only when the exported evidence shows confident defensive outcome proof.

## What Changed

- Extended `scripts/evaluate_team_highlight_accuracy.py` so non-scoring defensive GPT outcomes are evaluated as outcome-evidence clips:
  - `steal`
  - `forced_turnover`
  - `defensive_stop`
- Added `MIN_EVAL_DEFENSIVE_OUTCOME_CONFIDENCE = 0.65`, matching the backend GPT validation floor.
- Required defensive outcome evidence to include:
  - `qualitySignals.eventVisible`
  - `qualitySignals.outcomeVisible`
  - visible ball/player control
  - clean camera and full play context
  - defensive frame-role evidence such as `challenge`, `possessionChange`, `recovery`, or `defenseOutcome`
- Updated the launch-grade eval fixture so selected-team steals and forced turnovers include explicit GPT defensive evidence.
- Added regression coverage that fails a low-confidence GPT steal in the 85% evaluator.

## Why This Matters

The backend already rejects low-confidence GPT defensive outcomes. The launch evaluator also needs to enforce that contract, or an accuracy report could pass by counting guessed steals/forced turnovers as recalled highlights without proving the model had visible evidence. This phase aligns the proof gate with the cloud validator.

## Validation

- Red check before implementation:
  - `python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_defensive_outcome_low_confidence_fails_outcome_quality -v`
  - Result: failed because defensive outcomes were not counted as outcome-evidence clips.
- Focused green check:
  - `python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_defensive_outcome_low_confidence_fails_outcome_quality scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_selected_team_eval_counts_uncertain_review_and_defensive_events scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_default_readiness_requires_valid_missed_shot_outcome_evidence -v`
  - Result: 3 tests passed.
- Script/preflight unit suite:
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 79 tests passed.
- Script compile check:
  - `python3 -m py_compile scripts/evaluate_team_highlight_accuracy.py scripts/test_team_highlight_accuracy_eval.py scripts/test_build_team_highlight_eval_payload.py`
  - Result: passed.
- Pipeline quality suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Result: 48 tests passed.
- Backend edit/GPT regression suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent services.editing.tests.test_editing_service -v`
  - Result: 198 tests passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.
- Clean submission preflight:
  - `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Result: `pass=22 warn=2 fail=8`.
  - Remaining blockers: missing launch-grade labeled footage report proving 85% selected-team/highlight quality, unavailable connected iPhone for installed smoke, skipped live Worker/editing probes, stale main-branch CI relative to this commit, unproven installed TestFlight smoke, unproven Worker editing route, missing Cloudflare deploy credential proof, and unproven live iOS kill-switch state through the Worker.

## Launch Notes

This does not create the missing real labeled-footage report. It makes that report harder to fake or overclaim: selected-team steals and forced turnovers now need confidence and frame-role evidence before they help the launch-grade outcome-evidence score.

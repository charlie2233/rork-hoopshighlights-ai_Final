# Phase Clip131: Pipeline Turnover Label Precision

## Goal

Keep the backend analysis pipeline from treating plain turnovers as defensive highlights before GPT or Review. Real defensive plays still matter, but a generic `Turnover` label should not be reserved, expanded, or counted as a defensive event unless the label clearly says forced, defensive, steal, or strip.

## What Changed

- Tightened `ios/backend/app/pipeline.py` defensive label classification:
  - `Turnover` and `Unforced Turnover` are no longer defensive labels.
  - `Forced Turnover` and `Defensive Turnover` remain defensive labels.
  - Existing block, steal, strip, pressure, lockdown, and defensive-stop labels remain defensive.
- Added a regression test in `ios/backend/tests/test_pipeline_quality.py`.

## Why This Matters

The team quick scan and GPT editor depend on the ordinary pipeline to create a high-recall, decent-precision candidate pool. A broad turnover classifier could reserve or expand generic mistakes as defensive highlights, which weakens clip choice and can crowd out better blocks, steals, or shots.

## Validation

- Red check before implementation:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_defensive_label_classifier_requires_forced_turnover_context -v`
  - Result: failed because plain `Turnover` was classified as defensive.
- Focused green check:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_defensive_label_classifier_requires_forced_turnover_context ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_defensive_label_classifier_ignores_stop_and_pop_jumpers -v`
  - Result: 2 tests passed.
- Pipeline quality suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Result: 49 tests passed.
- Team quick-scan suite:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v`
  - Result: 31 tests passed.
- Compile check:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py`
  - Result: passed.
- GPT/edit-plan/pipeline regression suite:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent ios.backend.tests.test_pipeline_quality -v`
  - Result: 200 tests passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.
- Clean submission preflight:
  - `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Result: `pass=22 warn=2 fail=8`.
  - Remaining blockers: missing launch-grade labeled footage report proving 85% selected-team/highlight quality, unavailable connected iPhone for installed smoke, skipped live Worker/editing probes, stale main-branch CI relative to this commit, unproven installed TestFlight smoke, unproven Worker editing route, missing Cloudflare deploy credential proof, and unproven live iOS kill-switch state through the Worker.

## Launch Notes

This is cloud-backend analysis behavior only. It does not move analysis, rendering, composition, or export to iOS. It improves the candidate pool feeding selected-team review and GPT-led editing.

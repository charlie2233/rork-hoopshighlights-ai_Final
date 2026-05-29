# Phase Clip134 Analysis Defensive Diagnostics

Date: 2026-05-29
Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Expose the same defensive-highlight categories in cloud analysis diagnostics that the launch accuracy evaluator now requires.

Internal testers should be able to inspect an analysis result and see whether selected-team Review preserved blocks, steals, forced turnovers, and defensive stops without reading logs or exposing video/storage details.

## Change

- Added `forcedTurnoverReviewSegments` to `CloudDiagnostics`.
- Added `defensiveStopReviewSegments` to `CloudDiagnostics`.
- Populated both from the existing defensive label family classifier in `_analysis_team_diagnostic_counts`.

## TDD Evidence

Red test before implementation:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_team_diagnostics_split_forced_turnovers_and_defensive_stops -v
```

Initial result:

```text
FAILED (failures=1)
AssertionError: None != 1
```

Green focused result:

```text
Ran 1 test in 0.000s
OK
```

Broader validation:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality scripts.test_team_highlight_accuracy_eval scripts.test_submission_readiness_preflight scripts.test_build_team_highlight_eval_payload scripts.test_launch_provider_input_handoff -v
```

Result:

```text
Ran 105 tests in 0.756s
OK
```

## Launch Notes

This is evidence plumbing, not the final 85% proof. It makes cloud analysis outputs easier to audit while the real launch-grade labeled-footage report is still missing.

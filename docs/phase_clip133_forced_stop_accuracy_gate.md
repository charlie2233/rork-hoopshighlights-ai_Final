# Phase Clip133 Forced Stop Accuracy Gate

Date: 2026-05-29
Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make the launch-grade selected-team/highlight accuracy proof cover the defensive plays HoopClips now treats as real highlights: blocks, steals, forced turnovers, and defensive stops.

Before this phase, the default evaluator separately required selected-team block and steal coverage, but forced turnovers and defensive stops could be hidden inside the generic defensive-event count. That made the 85% proof weaker than the GPT/editor behavior.

## Change

- Added launch thresholds:
  - `minSelectedTeamForcedTurnovers`
  - `minSelectedTeamDefensiveStops`
- Added report metrics:
  - `selectedTeamForcedTurnoverCount`
  - `selectedTeamDefensiveStopCount`
- Updated `submission_readiness_preflight.py` so launch reports missing either metric fail submission readiness.
- Updated the launch-grade positive fixture so a passing report proves both categories.
- Kept narrow unit fixtures explicit by setting the new thresholds to `0` when those tests are not launch-grade coverage tests.

## TDD Evidence

Red test before implementation:

```bash
python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_default_readiness_requires_forced_turnover_and_defensive_stop_coverage -v
```

Initial result:

```text
FAILED (failures=1)
AssertionError: 'pass' != 'fail'
```

Green focused validation:

```bash
python3 -m unittest scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_default_readiness_requires_forced_turnover_and_defensive_stop_coverage scripts.test_team_highlight_accuracy_eval.TeamHighlightAccuracyEvalTests.test_selected_team_eval_counts_uncertain_review_and_defensive_events -v
```

Result:

```text
Ran 2 tests in 0.001s
OK
```

Broader evaluator/preflight validation:

```bash
python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_submission_readiness_preflight scripts.test_build_team_highlight_eval_payload -v
python3 -m unittest scripts.test_team_highlight_accuracy_eval scripts.test_submission_readiness_preflight scripts.test_build_team_highlight_eval_payload scripts.test_launch_provider_input_handoff -v
```

Result:

```text
Ran 52 tests in 0.102s
OK
Ran 55 tests in 0.175s
OK
```

## Launch Notes

This does not create the missing launch-grade labeled-footage report. It makes that report harder to overclaim: default readiness now needs real selected-team forced-turnover and defensive-stop examples, with the same timing/team/outcome proof gates used for the rest of the highlight set.

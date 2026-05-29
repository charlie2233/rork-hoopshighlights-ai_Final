# Phase Clip37: Uncertain Team Review Reserve

## Goal

Keep plausible selected-team highlights visible for user Review even when team ownership is below the confident `0.85` threshold. This supports the beta rule that uncertain clips should stay reviewable instead of being silently dropped.

## Change

- Selected-team analysis still filters out confident opponent clips.
- Matched clips remain ordered by the existing cloud ranking.
- When `includeUncertain` is true, the final visible Review list reserves a small number of slots for uncertain team-attribution clips before applying the `max_returned_clips` cap.
- For very short visible lists, at least one uncertain clip can survive; for larger lists the reserve is `max(2, max_returned_clips / 6)`, bounded by the number of uncertain clips.
- `All teams` mode and `includeUncertain: false` keep the existing straight top-N trimming behavior.

## Why

The previous selected-team path correctly marked low-confidence jersey/color ownership as `uncertain`, but the last step was a plain top-N slice. If confident selected-team makes filled the list, an uncertain block, steal, or forced-turnover candidate could be eligible yet absent from Review. That weakened the user-facing safety net for the 85% accuracy target.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_selected_team_visible_results_reserve_uncertain_review_clips ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_selected_team_visible_results_can_exclude_uncertain_when_requested -v` -> 2 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 120 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 40 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 84 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use this with the labeled team/highlight accuracy eval. Do not claim the real-footage 85% target until the eval set includes uncertain jersey-color blocks, steals, forced turnovers, confident selected-team makes, and confident opponent clips.

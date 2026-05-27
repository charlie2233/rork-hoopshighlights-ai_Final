# Phase Clip53: Best Uncertain Review Reserve

## Goal

When the user chooses a team before full analysis, keep uncertain-but-plausible clips in Review without letting weak uncertainty crowd out better selected-team moments.

## Change

- Selected-team Review trimming now reserves uncertain clips by quality, not by first-seen order.
- The reserved uncertain slot favors clips with valid duration/context, auto-keep signal, combined score, confidence, visual score, and motion score.
- Analysis-side defensive label detection now tokenizes labels so `Stop and Pop Jumper` stays a shot, while `Defensive Stop` and `Steal Finish` remain defensive-event candidates.

## Why

The goal is high recall with reviewable uncertainty. If HoopClips is not sure which team made a play, the app should show the best uncertain clips for human review, especially blocks and steals, instead of reserving space for whichever uncertain clip happened to appear first.

## Architecture

- Cloud backend owns the Review candidate pool and team-attribution uncertainty handling.
- iOS behavior is unchanged; it continues to display the cloud-returned Review clips and badges.
- No rendering, composition, or local analysis was added to iOS.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py` passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_selected_team_visible_results_reserve_best_uncertain_review_clip ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_defensive_label_classifier_ignores_stop_and_pop_jumpers ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_selected_team_visible_results_reserve_uncertain_review_clips -v` passed, 3 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed, 135 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` passed, 90 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed, 42 tests.
- `git diff --check` passed.

## Launch Recommendation

Add labeled internal footage with weak uncertain moments before strong uncertain steals/blocks. The 85% eval should prove the strong uncertain defensive clip is retained for review while confident opponent clips stay excluded.

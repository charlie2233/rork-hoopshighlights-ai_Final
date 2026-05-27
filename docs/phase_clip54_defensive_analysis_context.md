# Phase Clip54: Defensive Analysis Context

## Goal

Keep blocks, steals, and mixed defensive labels in the cloud analysis Review pool even when the label also contains shot words like `Blocked Shot` or `Steal Finish`.

## Change

- Cloud analysis now checks defensive-event labels before shot-like labels when normalizing candidate clips.
- Mixed defensive labels use defensive context expansion instead of being rejected for missing full shot lead-in/rim-entry timing.
- Native timing signals now treat defensive-event clips with defensive lead/follow-through thresholds while preserving shot-like metadata and blocked-shot outcome hints.
- Hybrid quality scoring treats defensive-event labels as defensive context, so early blocks and steals are not punished as bad shot windows.

## Why

The user chooses a team before analysis, and HoopClips must keep that team's defensive highlights too. A `Blocked Shot` near the start of a source clip can be a great highlight even when it cannot satisfy made-shot setup timing. GPT still judges sampled frames later, but the backend must first preserve the candidate with enough defensive context for Review and AI Edit.

## Architecture

- Cloud backend owns candidate normalization, team filtering, GPT selection, and edit planning.
- iOS behavior is unchanged; it displays the cloud-returned Review candidates and status.
- No local iOS analysis, rendering, composition, or FFmpeg command generation was added.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py` passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_normalization_keeps_early_blocked_shot_as_defensive_context ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_normalization_keeps_early_steal_finish_as_defensive_context ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_defensive_label_classifier_ignores_stop_and_pop_jumpers ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_normalization_expands_tiny_shot_clip_with_event_center -v` passed, 4 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed, 137 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` passed, 90 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed, 42 tests.
- `git diff --check` passed before staging.

## Launch Recommendation

Add labeled internal clips where `Blocked Shot` and `Steal Finish` happen near the beginning of the uploaded video or source segment. The 85% eval should prove they remain reviewable for the selected team while true shot labels like `Stop and Pop Jumper` still use shot timing.

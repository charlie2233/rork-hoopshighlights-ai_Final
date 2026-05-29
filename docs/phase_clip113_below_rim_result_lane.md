# Phase Clip113: Below-Rim Result Lane

## Goal

Improve cloud candidate generation for made/missed shot moments by giving the native visual detector a separate lower-frame result signal. The intended product effect is fewer clips anchored on release-only motion and more event centers near the basket/net result that GPT can review with richer keyframes.

## What Changed

- `ios/backend/app/pipeline.py` now extracts a fifth visual signal for lower-half motion when sampling source frames.
- Existing four-value visual signal tests and callers remain supported; missing lower-lane data falls back to center motion.
- Outcome context scoring now uses a result-focused score that weights center and lower/below-rim motion more heavily than release/upper-body motion.
- Setup scoring still uses the existing upper/center shot-context score, so generic lower-frame noise alone does not become a shot boundary.

This stays cloud/backend-owned. iOS continues to upload, show team options, start analysis, review clips, and display/share rendered output.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_uses_below_rim_result_lane_over_release_motion -v` passed: 1 test.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_shot_motion_over_audio_only_spike ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_rim_outcome_over_release_in_sequence ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_rim_result_over_release_spike_with_follow_through ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_uses_below_rim_result_lane_over_release_motion ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_rejects_release_only_spike_without_followthrough ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_does_not_shift_to_dead_aftermath ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_ignores_low_quality_camera_motion ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_ranking_prefers_complete_shot_context_over_later_audio_spike ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_detect_shot_boundaries_extracts_visual_event_from_source -v` passed: 9 tests.
- `/Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py` passed.
- `git diff --check` passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed: 184 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 56 tests.

## Launch Notes

This is another accuracy improvement, not final launch proof. The 85% goal still requires a launch-grade labeled footage evaluation report with team/color selection, all-teams mode, blocks, steals, made/missed shots, uncertain-review accounting, and real cloud analysis job IDs.

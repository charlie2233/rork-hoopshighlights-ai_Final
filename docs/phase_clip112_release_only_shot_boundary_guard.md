# Phase Clip112: Release-Only Shot Boundary Guard

## Goal

Improve native clip selection before GPT by making HoopClips less likely to trust a release-only spike as the basket/result moment. The user-facing outcome should be fewer clips that start right before the basket or show only a tiny fragment of a shot.

## What Changed

- `ios/backend/app/pipeline.py` now requires native visual shot-boundary candidates to have both:
  - setup context before the event, and
  - outcome/follow-through context after the event.
- The visual event scorer now weights follow-through/outcome context more strongly so the selected boundary anchors closer to the rim/result frame instead of the release.
- A release/setup frame that is immediately followed by a stronger result-like frame is filtered out as setup, not accepted as the basket event.

This remains a cloud/backend change. iOS still only uploads, lets the user choose a team or all teams, shows Review/status/preview/share, and sends controls to the backend.

## Why

GPT-led editing is only as good as the candidate windows it receives. If native analysis anchors `eventCenter` on a release spike or camera motion, GPT may receive frames that miss the rim result and the renderer may preserve a weak window. This guard keeps weak release-only candidates out of the high-confidence shot boundary path before GPT receives sampled keyframes.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_shot_motion_over_audio_only_spike ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_rim_outcome_over_release_in_sequence ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_rim_result_over_release_spike_with_follow_through ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_rejects_release_only_spike_without_followthrough ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_does_not_shift_to_dead_aftermath ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_ranking_prefers_complete_shot_context_over_later_audio_spike ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_detect_shot_boundaries_extracts_visual_event_from_source -v` passed: 7 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed: 183 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 56 tests.

## Launch Notes

This improves pre-GPT candidate quality but does not prove the 85% selected-team/highlight target by itself. Submission still requires the launch-grade labeled-footage accuracy report, available wired iPhone TestFlight smoke, current staging deploy, Worker `/v1/editing/version`, and green required GitHub checks.

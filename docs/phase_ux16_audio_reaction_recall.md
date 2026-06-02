# Phase UX16 - Audio Reaction Recall

## Goal

Improve cloud highlight recall for the real-game pattern where a very loud or repeated crowd pop happens right after a basketball highlight.

## Architecture

- Cloud analysis extracts the audio profile and creates recall candidates.
- iOS does not run audio recognition, analysis, rendering, composition, or export.
- Audio reaction cues are hints for GPT/editor review, not proof of a make, block, steal, or other outcome.
- Renderer behavior remains deterministic and validator-owned.

## Changes

- High-salience audio reactions now keep a wider pre-pop window so GPT sees the play that caused the reaction.
- Strong repeated crowd bursts extend the visual-event lookback from nearby shot/motion anchors.
- Candidate windows still carry `audioCueType`, `audioCueConfidence`, and `audioCueTime` for GPT and AI Work Receipt context.
- Audio-only reaction windows remain labeled as review-only `Crowd Reaction` clips unless visual context supports a basketball event.

## Tests

- Passed: `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_boundaries_detect_loud_local_crowd_pops ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_repeated_crowd_pops_boost_salience ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_candidate_windows_include_crowd_pop_recall_anchor_for_gpt_review ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_super_loud_crowd_pop_keeps_wider_pre_reaction_context ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_super_loud_crowd_pop_extends_visual_play_lookback_for_gpt_review ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_audio_pop_anchors_recall_window_with_lead_in ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_audio_pop_does_not_reward_steady_loud_background -v`
- Passed: `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v` (78 tests).
- Passed: `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py`
- Passed: focused iOS import-copy tests from Phase UX15.
- Passed: `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux15-dd CODE_SIGNING_ALLOWED=NO`
- Passed: `git diff --check`.

## Launch Notes

This improves recall for loud gyms without claiming audio is the highlight. GPT should use these candidates to review frames before and after the reaction, then reject boring, duplicate, or unclear clips.

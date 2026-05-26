# Phase Clip12 Outcome-Aware Visual Event Timing

## Goal

Improve native cloud candidate timing so HoopClips behaves less like a generic motion detector and more like a basketball editor. The visual event detector should prefer the rim/result moment in a shot sequence over an earlier release-only motion spike when follow-through evidence is present.

## Change

- Added a regression test where the current detector picked a high-motion release frame at `9.5s` instead of the rim/result frame at `10.0s`.
- Tuned `_outcome_aware_visual_event_score` to give stronger credit for visible setup before the candidate frame, plus smaller follow-through/result credit after it.
- Kept existing safeguards that prevent the detector from drifting into dead aftermath.

## Quality Rationale

The best highlight window should show the action before the shot and the visible result after it. A big motion spike can happen on release, but clipping exactly around release can still miss the actual basket. This scoring update makes the native candidate pool better before GPT sees keyframes, so GPT starts from higher-recall and higher-precision candidates.

## Validation Evidence

- Red test before implementation:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_rim_result_over_release_spike_with_follow_through -v`
  - Result before code change: failed because the detected boundary was `[9.5]`, expected `[10.0]`.
- Green focused tests after implementation:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_rim_result_over_release_spike_with_follow_through ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_prefers_rim_outcome_over_release_in_sequence ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_visual_event_detector_does_not_shift_to_dead_aftermath -v`
  - Result: 3 tests passed.
- Pipeline-quality suite:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Result: 18 tests passed.
- Full backend and editing service suites:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -v`
  - Result: 92 tests passed.
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 68 tests passed.
- Hygiene:
  - `python3 -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py`
  - `git diff --check`
  - Result: passed.

## Launch Notes

- No iOS code changed.
- No GPT payload, rendering, storage, or FFmpeg command behavior changed.
- This improves the cloud-native candidate pool that feeds GPT-led selection and deterministic fallback planning.

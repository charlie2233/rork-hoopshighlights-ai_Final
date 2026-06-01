# Phase Clip2: Audio Crowd Pop Cues

## Goal

Improve highlight recall by treating loud crowd/audio pops as a cloud-side clue that a highlight may be nearby, especially when the reaction is a short burst of repeated pops instead of one isolated spike.

## Change

- The native backend audio-pop scorer is now cluster-aware.
- Repeated elevated crowd pops around the same moment receive extra salience over an isolated pop with the same peak level.
- Steady loud gym noise still does not score as a crowd reaction because the boost requires local elevation above baseline.
- Existing crowd-pop behavior stays review-safe: audio is a recall signal only, and GPT/validators still need sampled visual evidence before claiming a make, block, steal, forced turnover, or defensive stop.

## Architecture

- Cloud backend owns audio profiling, candidate generation, GPT selection, edit planning, rendering, and storage.
- iOS behavior is unchanged.
- No full videos are sent to GPT; only existing candidate metadata and sampled keyframes reach the GPT-led editor.
- GPT still cannot emit FFmpeg commands or bypass deterministic plan validation.

## Validation

Commands:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_boundaries_detect_loud_local_crowd_pops ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_boundaries_detect_sustained_crowd_swell_onset ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_repeated_crowd_pops_boost_salience ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_audio_pop_does_not_reward_steady_loud_background -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
git diff --check
```

Results:

- Python compile: passed.
- Focused audio-pop regression tests: passed.
- Full backend pipeline-quality suite: passed, 66 tests.
- `git diff --check`: passed.

## Launch Recommendation

Keep this signal high-recall and reviewable. It should help HoopClips look around loud crowd moments, but final clip selection should continue to depend on visible basketball action and outcome evidence.

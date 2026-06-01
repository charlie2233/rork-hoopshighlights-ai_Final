# Phase Clip3: Audio Visual Anchor

## Goal

Improve highlight recall and label quality when a loud crowd pop happens shortly after a real basketball action.

## Change

- Cloud analysis now looks for a visual event shortly before each detected audio reaction.
- If a shot/action boundary is found before the crowd pop, the audio-reaction candidate is anchored on that visual play instead of the noise peak.
- The candidate window keeps setup context before the play and enough aftermath to include the crowd reaction.
- Audio remains a recall signal only. It does not prove a make, block, steal, forced turnover, or defensive stop by itself.

## Architecture

- Backend/cloud candidate generation changed.
- iOS behavior did not change.
- No local iOS analysis, rendering, composition, or FFmpeg generation was added.
- GPT still receives compact candidate metadata/keyframes only, and deterministic validators remain responsible for render safety.

## Validation

Commands:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_windows_keep_pre_pop_action_context ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_window_anchors_visual_play_before_crowd_pop ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_candidate_windows_include_crowd_pop_recall_anchor_for_gpt_review -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -v
git diff --check
```

Results:

- Python compile: passed.
- Focused audio-reaction tests: passed.
- Full pipeline-quality suite: passed, 67 tests.
- Backend unittest discovery: passed, 238 tests.
- `git diff --check`: passed.

## Launch Recommendation

Keep using crowd pops as high-recall hints, not truth. This should help HoopClips find the play before a loud reaction while still requiring visual/GPT review evidence before final selection and captions.

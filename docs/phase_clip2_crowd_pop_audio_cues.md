# Phase Clip2: Crowd Pop Audio Cues

## Goal

Improve highlight recall when a loud crowd reaction happens near a play. HoopClips now recognizes whether an audio cue looks like an isolated spike, repeated crowd-pop cluster, or crowd swell, then passes that cue to GPT as review/editing context.

## Architecture

- Cloud/backend owns audio profiling, cue recognition, candidate generation, GPT selection, edit planning, rendering, and storage.
- iOS only preserves and displays cloud-generated cue metadata, then passes it through to AI Edit.
- No iOS local audio analysis, video analysis, rendering, composition, or export logic was added.
- Audio cues remain recall hints only. GPT and validators still require visible basketball action and outcome evidence before final selection, captions, or outcomes.

## Changes

- Added optional `audioCueType`, `audioCueConfidence`, and `audioCueTime` to cloud analysis clips.
- Added audio cue pattern recognition:
  - `spike`: one loud local pop.
  - `cluster`: repeated elevated crowd pops around the same moment.
  - `swell`: a loud rise with short follow-through.
  - `steady_noise`: loud background noise, kept at zero confidence.
- Candidate windows carry audio cue type/confidence into classified `CloudClip` payloads.
- GPT compact candidate context and Agent Template Cookbook candidate quality now include audio cue metadata.
- Generic `Highlight` clips with recognized high-confidence crowd cues can be reserved for GPT/user review without requiring a `Crowd Reaction` label.
- Review UI can display recognized cue copy such as repeated crowd pop, crowd swell, or audio spike.

## Safety

- Full videos are not sent to GPT.
- GPT receives compact candidate metadata and sampled keyframes only.
- Audio cue metadata cannot create FFmpeg commands and cannot bypass EditPlan validation.
- Steady loud gym noise is classified as `steady_noise` with zero confidence.
- Audio-only moments remain review-required unless sampled frames show the basketball action and result.

## Validation

Completed local commands:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m py_compile ios/backend/app/models.py ios/backend/app/pipeline.py ios/backend/app/classifier.py ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py ios/backend/tests/test_pipeline_quality.py services/editing/tests/test_gpt_reranker.py
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_repeated_crowd_pops_boost_salience ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_audio_reaction_signal_classifies_swell_and_steady_noise ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_audio_pop_anchors_recall_window_with_lead_in ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_audio_pop_does_not_reward_steady_loud_background -v
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_sampling_reserves_unlabeled_loud_audio_pop_for_review services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_uses_recognized_audio_cue_metadata_for_generic_highlight services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_marks_crowd_reaction_candidates_as_audio_recall_hints -v
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build-for-testing
```

Results:

- Py compile passed.
- Focused pipeline and GPT regression tests passed.
- `ios.backend.tests.test_pipeline_quality`: 68 tests passed.
- `services.editing.tests.test_gpt_reranker`: 91 tests passed.
- `ios.backend.tests.test_edit_plan_agent`: 108 tests passed.
- `services.editing.tests.test_editing_service`: 57 tests passed, including local FFmpeg render paths and render-history privacy checks.
- `git diff --check` passed.
- iOS Debug simulator build passed.
- iOS Debug simulator `build-for-testing` passed after updating the Swift test fixtures for the new optional audio cue fields.

## Launch Recommendation

Keep this enabled as a high-recall signal for internal beta. It should help find blocks, steals, late buckets, and hype plays that produce loud reactions, while GPT/user review protects against boring crowd-only clips.

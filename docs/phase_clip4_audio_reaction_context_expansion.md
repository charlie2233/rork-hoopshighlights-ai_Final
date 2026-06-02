# Phase Clip4 Audio Reaction Context Expansion

## Goal

Improve GPT-led highlight quality for loud crowd-pop and audio-reaction candidates. Crowd noise is useful recall evidence, but GPT needs enough visual lead-in and follow-through to decide whether the pop belongs to a real basketball highlight.

## Architecture Guardrails

- Cloud editing service owns candidate expansion, keyframe sampling, GPT reranking, edit planning, validation, rendering, and storage.
- iOS remains the control surface for upload, review, Export, status, preview, download, and share.
- No iOS analysis, composition, rendering, FFmpeg command generation, or local GPT decision logic was added.
- Audio reactions remain recall hints only. GPT and validators must still require visible basketball event/outcome evidence.

## Changes

- Added cloud-side source-context expansion for strong audio-reaction candidates before GPT keyframe extraction.
- Uses `audioCueTime` as the preferred anchor when present, then clamps the expanded window to source duration.
- Pulls in more lead-in before the crowd/audio spike and short follow-through after it so GPT can inspect:
  - what happened before the sound
  - the cue/reaction moment
  - whether the play outcome is visible
- Leaves weak label-only crowd-reaction clips unchanged when there is no real loud-cue evidence.
- Preserves existing shot and defensive context expansion priority.

## Accuracy Behavior

- Strong crowd-pop clips can reach GPT with better visual context instead of late aftermath-only frames.
- GPT still receives `audioReactionGuidance`, `audioReactionVerificationRoles`, and strict rules that audio cues cannot prove makes, misses, blocks, steals, turnovers, or stops by themselves.
- Uncertain but promising clips remain reviewable when the visible evidence is not strong enough for automatic final rendering.

## Validation

- Targeted backend tests:
  - `uv run --no-project --with-requirements services/editing/requirements.txt python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_source_context_expansion_salvages_thin_shot_windows_before_gpt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_source_context_expansion_salvages_thin_defensive_windows_before_gpt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_source_context_expansion_salvages_loud_audio_reaction_windows_before_gpt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_source_context_expansion_leaves_weak_label_only_crowd_reaction_unchanged`
  - Result: passed, `Ran 4 tests`
- Full GPT reranker test module:
  - `uv run --no-project --with-requirements services/editing/requirements.txt python -m unittest services.editing.tests.test_gpt_reranker`
  - Result: passed, `Ran 93 tests`
- Editing service test module:
  - `uv run --no-project --with-requirements services/editing/requirements.txt python -m unittest services.editing.tests.test_editing_service`
  - Result: passed, `Ran 57 tests`
- Hygiene:
  - `git diff --check`
  - Result: passed

## Launch Notes

- This improves GPT evidence quality, but it does not prove the 85% real-footage target by itself.
- Internal TestFlight readiness still needs the installed-device smoke: import/upload -> cloud analysis -> Review -> Export -> AI Edit render -> preview -> revision -> share/open-in.
- No GitHub Actions run should be required for this phase unless a maintainer wants CI confirmation after local validation.

# Phase Clip3 Audio Cue GPT Context

## Goal

Improve GPT-led highlight editing quality by making loud crowd/audio cue candidates visible to the backend editor even when the candidate label is basketball-contextual, such as `Possible Layup`.

## Architecture

- Cloud backend owns candidate analysis, GPT selection, edit planning, validation, rendering, and storage.
- iOS remains the control/status surface and does not perform local production analysis or rendering.
- GPT receives compact candidate context only. Full videos and raw renderer commands are not sent to GPT.
- Audio cues are recall hints only. The validator still requires sampled visual evidence before GPT can claim a made shot, block, steal, or other outcome.

## Change

- Added `is_audio_reaction_context_label` in the backend editing layer.
- `audio_reaction_source_for_clip` now recognizes strong audio cues on uncertain basketball-action labels instead of only generic labels.
- New source labels include:
  - `recognized_basketball_audio_cue`
  - `basketball_context_loud_audio_pop`
  - `basketball_context_super_loud_audio_pop`
- Strong outcome labels such as made/missed/blocked/scored remain excluded from this helper to avoid turning normal scoring labels into audio-only claims.

## Safety

- Existing GPT validation still rejects audio-reaction clips when no sampled visual frame roles are available.
- The GPT editor receives guidance that crowd/audio pops are recall hints only and must be verified by visible basketball action and outcome.
- No FFmpeg commands, storage keys, presigned URLs, or secrets are added.

## Validation

- `git diff --check` passed.
- `PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_edit_plan_agent.py -k "audio_cue or audio_reaction or compact"` passed: 3 selected tests.
- `PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_edit_plan_agent.py` passed: 110 tests.
- `PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_render_jobs.py` passed: 7 tests.
- `PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_pipeline_quality.py` passed: 70 tests.
- `PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt python -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py` passed.
- iOS build was not rerun because this pass touched backend editing logic and docs only.

## Launch Notes

- This improves semantic clipping quality for moments where the crowd reacts before the visual classifier is fully confident.
- It should help GPT decide which candidates deserve keyframe review while keeping unclear audio-only clips out of renders.
- Real-device/TestFlight smoke is still required before internal launch signoff.

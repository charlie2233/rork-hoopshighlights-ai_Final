# Phase: Audio Pop Candidate Recall

## Goal

Use loud crowd/audio pops as a cloud-side recall signal for highlight candidates. A sudden crowd pop often lands near a dunk, big three, block, steal, or late-game bucket, so the native candidate pool should include those moments for GPT and user review.

## Architecture

- Cloud/backend extracts the normalized audio profile and builds candidate clips.
- iOS does not analyze or render video for this feature.
- Audio pops are only a recall and event-center signal. They do not replace visual shot/defensive detection, GPT review, EditPlan validation, or deterministic rendering.
- Audio-only candidates are labeled for review as `Crowd Reaction` and are not auto-kept unless later vision/GPT/user review confirms a real basketball event.

## Implementation

- Added `audio_pop_score` and `audio_pop_time` to backend `CandidateWindow`.
- Added `_audio_pop_signal_for_window`, which compares a loud bucket against the local baseline and window mean.
- Added context scoring so windows with lead-in before the pop rank above windows that start exactly on the noise spike.
- Candidate `peak_time` now anchors to the audio pop when no stronger visual shot event is available.
- Complete visual shot context still outranks later audio-only spikes.

## Quality Behavior

- Sharp isolated crowd pops boost candidate recall and provide a better `eventCenter` for GPT keyframe sampling.
- Steady loud background noise receives near-zero audio-pop score.
- Audio pop candidates remain review-safe, because a loud gym reaction alone does not prove the clip is a made shot, block, or steal.

## Tests

- `test_native_candidate_audio_pop_anchors_recall_window_with_lead_in`
- `test_native_candidate_audio_pop_does_not_reward_steady_loud_background`
- Existing guardrails still cover complete shot context outranking later audio-only spikes and audio-only windows not being labeled as made shots.

## Launch Notes

- This is safe for internal TestFlight because it expands/reorders candidate recall only on the backend.
- GPT-led editing should receive better keyframes around crowd reactions via the corrected `eventCenter`.
- Further accuracy work can combine this signal with GPT frame review, ball/rim/pose tracking, and team-defense attribution.

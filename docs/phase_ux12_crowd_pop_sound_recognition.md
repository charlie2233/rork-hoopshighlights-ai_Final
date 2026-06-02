# Phase UX12 Crowd Pop Sound Recognition

## Goal

Make loud crowd/audio pops a stronger cloud-side recall signal because a big reaction often lands near a dunk, block, steal, finish, or made shot.

## Changes

- Cloud native analysis now keeps more long-game audio reaction boundaries:
  - boundary cap increased from 48 to 96.
- Audio-reaction candidate windows now hold more context around the sound:
  - lead-in increased to 3.4 seconds.
  - follow-through increased to 1.7 seconds.
  - visual-event lookback increased to 4.25 seconds so a play before a delayed crowd pop can still anchor the candidate.
  - post-pop context increased to 0.9 seconds.
- Review trimming now reserves more crowd/audio-pop candidates when the pool is large:
  - 160+ review slots can reserve up to 16 audio-reaction candidates.
  - 80+ review slots can reserve up to 10.
  - 40+ review slots can reserve up to 6.
  - 20+ review slots can reserve up to 4.
- GPT review is slightly more permissive for audio-reaction salience, while still requiring sampled visual evidence before keeping or claiming an outcome.

## Safety Rules

- Audio pops are recall hints only.
- They do not prove a made shot, block, steal, or defensive stop.
- GPT must inspect sampled keyframes around the reaction before keeping the clip.
- FFmpeg/CV/timestamp logic still owns exact extraction and rendering.
- No iOS local analysis, rendering, or export behavior was added.

## Validation

- Passed: backend audio-reaction focused tests:
  - `test_audio_reaction_boundaries_keep_long_game_crowd_pop_candidates`
  - `test_audio_reaction_window_anchors_earlier_visual_play_before_late_crowd_pop`
  - `test_review_trim_reserves_more_audio_reactions_for_internal_candidate_pool`
  - `test_native_candidate_audio_pop_anchors_recall_window_with_lead_in`
  - steady-noise guardrail coverage
- Passed: full backend pipeline quality suite, 75 tests.
- Passed: full GPT reranker suite, 95 tests.
- Passed: `git diff --check`.

## Launch Notes

- This should improve recall for loud gyms and games where the best signal is a sudden crowd pop after the play.
- Real-footage validation should include blocks, steals, late finishes, and noisy gym clips where applause or crowd bursts happen slightly after the visible event.

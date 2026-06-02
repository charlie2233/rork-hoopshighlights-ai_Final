# Phase Clip: Crowd Pop Context Boost

## Goal

Improve highlight recall when a very loud crowd, bench, or court-audio pop happens a few seconds after the actual play.

## Changes

- Cloud native analysis now treats high-salience audio reactions as a wider search hint:
  - pre-pop context increased to 5.2 seconds;
  - post-pop context increased to 2.4 seconds;
  - visual-event lookback increased to 6.75 seconds.
- Super-loud isolated spikes can qualify as high-salience audio reactions when confidence is strong enough.
- GPT-led editing now expands audio-reaction candidates with a longer pre-pop context window before sampling keyframes:
  - lead-in increased to 4.2 seconds;
  - follow-through increased to 1.6 seconds;
  - target context increased to 7 seconds;
  - maximum context increased to 9 seconds.

## Safety

- Audio is still only a recall clue.
- GPT must verify sampled frames show visible basketball action and outcome before keeping a clip.
- GPT still cannot generate FFmpeg commands, replace CV/timestamp logic, or invent clip IDs.
- iOS still does not analyze, render, compose, or export production edits locally.

## Validation

- Added backend tests for delayed crowd-pop anchoring and super-loud spike salience.
- Added GPT reranker test for longer pre-crowd-pop keyframe context.
- Run locally before launch review:
  - `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_high_salience_crowd_pop_anchors_delayed_visual_play_for_gpt_review ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_super_loud_isolated_spike_counts_as_high_salience_audio_reaction -v`
  - `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_source_context_expansion_keeps_longer_pre_crowd_pop_context_for_gpt -v`

## Launch Notes

Use this in internal beta footage with noisy gyms, late crowd reactions, blocks, steals, big threes, and fast-break finishes. The expected behavior is more reviewable candidates around loud reactions, with GPT rejecting boring, duplicate, or audio-only moments.

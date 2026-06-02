# Phase UX18 - Crowd Pop Recall Reserve

## Goal

Make loud or repeated crowd pops survive the backend candidate cap more reliably, because a sudden gym reaction often happens right after a dunk, block, steal, tough finish, or important make.

## Architecture

- Cloud analysis owns audio recognition and candidate generation.
- iOS does not run audio analysis, rendering, composition, or export.
- Audio reactions are recall hints for GPT/editor review, not proof that a shot was made or that a specific basketball event happened.
- Renderer execution stays deterministic through validated `EditPlan` JSON.

## Changes

- Added a candidate-window reserve pass for strong audio reactions.
- When the visual candidate list is already full, the backend now protects a configurable slice of high-salience `spike`, `cluster`, or `swell` crowd-pop windows.
- Overlapping visual candidates are kept unless the audio-reaction window carries stronger audio salience.
- Audio-only windows remain review candidates and can still be rejected by GPT/user review if frames are unclear or boring.

## Safety

- Full videos are not sent to GPT by this change.
- GPT does not generate FFmpeg commands.
- Audio signals do not override CV/timestamp extraction.
- Loud steady background noise is still filtered by cue classification and confidence gates.

## Validation Plan

- Focused backend test for full candidate-cap audio reserves.
- Existing audio reaction tests for local pops, swells, repeated clusters, pre-pop context, visual anchor lookback, steady-noise guardrails, and long-game repeated pops.
- `git diff --check`.

## Launch Notes

This should improve recall in loud gyms without making false claims. The candidate pool should include more moments near crowd bursts, then GPT and the Review UI can reject uncertain clips or keep them when frames show a clear play.

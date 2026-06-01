# Phase Audio Reaction Highlight Recall

## Goal

Use real cloud-side audio analysis to catch loud crowd pops as high-recall highlight candidates.

This keeps the HoopClips architecture cloud-first. iOS does not analyze audio or render video; the backend extracts an audio profile, creates reviewable candidate windows, and GPT/visual validators decide whether the crowd reaction is attached to a real basketball highlight.

## Changes

- Added explicit audio reaction boundary detection for loud local audio spikes.
- Added audio-reaction candidate windows around crowd-pop peaks with lead-in and follow-through context.
- Crowd-pop candidates are recall hints only. They are labeled `Crowd Reaction` when no shot context is visible and are not auto-kept without visual evidence.
- Existing visual/shot boundaries still win when they are available, so crowd noise does not replace CV, timestamp logic, keyframes, GPT review, or deterministic rendering.
- GPT context already receives `audioReactionCandidate` guidance and must verify sampled keyframes before claiming made shots, blocks, steals, or other outcomes.

## Validation

Run after this change:

```bash
git diff --check
cd ios/backend && python -m pytest tests/test_pipeline_quality.py
```

## Launch Notes

- This improves recall for gyms where parents/crowds react loudly right after a big play.
- It intentionally favors reviewability over silent rejection. If the audio pop is real but the visuals are unclear, GPT should keep it as uncertain/review-only instead of confidently rendering it.
- Cost is unchanged for native analysis; extra GPT cost only happens downstream when these candidates are sampled for GPT-led editing.

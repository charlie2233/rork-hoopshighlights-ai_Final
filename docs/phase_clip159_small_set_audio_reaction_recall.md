# Phase Clip159: Small-Set Audio Reaction Recall

## Goal

Keep loud crowd/audio reaction moments available for GPT and user review even when the visible review set is small.

## Change

- Lowered the audio-reaction review reserve threshold from 8 clips to 4 clips.
- Small review sets now reserve one strong crowd/audio reaction candidate when scoring clips would otherwise fill the cap.
- Larger review sets keep the existing higher audio-reaction reserve counts.

## Architecture

- Cloud backend still owns audio profiling, candidate generation, GPT review, edit planning, and rendering.
- iOS behavior is unchanged.
- Audio reactions are recall hints only. GPT and the reviewer still need visible basketball action/outcome before a moment becomes a final highlight.
- No full videos are sent to GPT and GPT does not generate FFmpeg commands.

## Validation

Command:

```bash
PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_pipeline_quality.py -k "review_trim or audio_reaction or defensive"
PYTHONPATH=ios/backend uv run --with-requirements ios/backend/requirements.txt --with pytest python -m pytest ios/backend/tests/test_pipeline_quality.py
```

Result:

- 24 passed, 45 deselected.
- Full pipeline quality suite: 69 passed.

## Launch Recommendation

Use this to improve recall for noisy gyms and crowd-pop moments. Keep the Review surface and GPT reranker strict about boring, duplicate, unclear, or audio-only clips.

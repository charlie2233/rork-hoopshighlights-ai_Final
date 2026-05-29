# Phase Clip99 - Defensive GPT Timing Floor

## Goal

Improve selected-team recall for blocks, steals, and defensive stops without reopening the bad shot-window problem.

## Change

- GPT candidate quality hints now use the production shot-context floor for true shot clips: `1.2s` setup, `0.8s` outcome, and at least `3.0s` duration.
- Defensive candidates now use a separate defensive event-context floor: at least `2.0s` duration, `0.6s` before the defensive event, and `0.5s` after it.
- Generic non-shot clips stay on the stricter context floor; only defensive labels get the defensive event-context floor so they do not get silently dropped just because they do not look like a shot-tracker sequence.

## Why

The user-facing goal is selected-team highlights, not only makes. Blocks, steals, forced turnovers, and defensive stops should reach GPT when they show the challenge and possession/result context. Applying shot-style lead-in rules to every candidate was too strict for valid defensive events, especially when source expansion is unavailable.

## Guardrails

- This does not allow tiny `0.1s` clips: `MIN_PLAN_CLIP_SECONDS` and defensive quality thresholds still apply.
- Shot clips still use the stricter shot context floor and remain rejected when they begin right before the basket/result.
- GPT still receives compact candidate metadata/keyframes only, not full videos, and it cannot output renderer commands.

## Validation

Run after this phase:

```bash
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_quality_filter_keeps_defensive_window_with_event_context_before_gpt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_quality_filter_excludes_barely_contextual_shot_windows_before_gpt -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

## Remaining Launch Proof

This improves recall for defensive candidates before GPT review, but it is still not the real 85% launch proof. Internal launch still needs labeled real-footage evaluation covering selected-team makes, misses, blocks, steals, forced turnovers, uncertain review clips, opponent highlights, and bad-window negatives.

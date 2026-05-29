# Phase Clip122: Selected-Team GPT Sampling Balance

## Goal

Keep uncertain selected-team clips visible for Review without letting them consume the full GPT editor budget ahead of confident selected-team highlights.

## What Changed

- GPT candidate sampling now separates selected-team render-eligible clips from unreviewed uncertain review-only clips.
- Unreviewed uncertain clips still get a bounded review reserve.
- Confident selected-team clips and user-kept uncertain clips fill the remaining GPT slots before extra review-only uncertain clips are added.

## Why This Matters

The product goal is not to hide uncertain clips. The user should still see plausible blocks, steals, and borderline team-attribution plays in Review. But the final GPT editor also needs enough confident selected-team clips to build a good reel. Before this phase, a high-scoring uncertain pile could take every sampled GPT slot and starve lower-scored but render-ready selected-team clips.

## Validation

- Red check before implementation:
  - `test_selected_team_sampling_bounds_unreviewed_uncertain_clip_reserve` failed with 8 uncertain clips in an 8-clip GPT sample.
- Green focused checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_selected_team_sampling_bounds_unreviewed_uncertain_clip_reserve services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_includes_team_targeting_and_excludes_confident_opponent_clips services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_disabled_gpt_fallback_preserves_uncertain_team_review_ids -v`

## Launch Notes

This improves selected-team GPT sampling behavior only. It does not prove the requested 85% real-footage target. Internal launch still needs the launch-grade labeled accuracy report, live staging proof, installed TestFlight smoke, and unblocked CI.

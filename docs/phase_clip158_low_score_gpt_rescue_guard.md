# Phase Clip158 Low-Score GPT Rescue Guard

## Goal

Improve final highlight quality by making GPT low-score rejections stick.

## Change

- Removed `low_highlight_score` and `low_watchability_score` from the all-rejected GPT rescue allowlist.
- The rescue path still preserves softer reviewable reasons such as `not_confident`, `needs_review`, and `low_hype`.
- Clips that fail backend GPT highlight/watchability thresholds now stay rejected instead of being revived only because GPT rejected every sampled candidate.
- Central team/all-team filtering now excludes clips where `userReviewDecision` is `discarded`.
- GPT rerank summaries report discarded clips as `user_discarded` when they arrive in an edit request.
- Disabled/fallback GPT receipts also classify discarded clips as `user_discarded`.

## Why

GPT is acting as the final semantic highlight editor in this phase. If it returns keep=true but scores a clip below the backend highlight/watchability thresholds, that is stronger evidence than a vague editorial rejection. Reviving those clips can put boring or hard-to-watch moments back into the final EditPlan.

## Architecture

- Cloud backend still owns GPT selection, edit planning, validation, and render decisions.
- iOS behavior is unchanged.
- This does not alter FFmpeg, CV, timestamp logic, keyframe extraction, or GPT prompts.

## Validation

- Added `test_gpt_highlight_rerank_low_scores_do_not_rescue_boring_clips`.
- Added `test_team_filter_excludes_user_discarded_clips`.
- Added `test_gpt_highlight_rerank_does_not_render_user_discarded_matched_clip`.
- Focused backend test quartet: passed.
- `python -m py_compile` for edited backend/reranker/test modules: passed.
- `python -m unittest ios.backend.tests.test_edit_plan_agent -v`: passed, 100 tests.
- `python -m unittest services.editing.tests.test_gpt_reranker -v`: passed, 61 tests.
- `git diff --check`: passed.

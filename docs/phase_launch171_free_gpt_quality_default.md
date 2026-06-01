# Phase Launch171 Free GPT Quality Default

## Goal

Keep acquisition-friendly Free availability while improving highlight judgment quality. Free users still get `3` AI editing chances/day, but GPT-led highlight editing now uses the same 10-keyframe clip evidence package by default unless an operator explicitly lowers it.

## Change

- `HOOPS_AI_CLIP_GPT_FREE_KEYFRAMES_PER_CLIP` default moved to `10`, clamped to `3...10`.
- Free GPT review still samples up to `320` existing candidate clips.
- GPT still receives only sampled candidate keyframes and compact clip metadata, never full videos.
- FFmpeg/CV/timestamp logic remains deterministic backend code; GPT only selects, rejects, captions, orders, and suggests bounded edits through validated JSON.
- Daily Free edit availability remains `3`; this change spends more vision evidence per edit, not more free edit chances.

## Why

The 10-frame package gives GPT release, shot arc, rim approach, rim entry, below-rim follow-through, start, event center, and finish evidence. That directly targets the observed bad clips where a late basket aftermath, unclear ball path, or duplicate/boring moment can look plausible with too few frames.

## Validation

Run locally before merge:

```bash
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_default_keyframes_include_setup_and_outcome_context services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default -v
PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
git diff --check
```

## Launch Notes

Use this with the existing staging deploy defaults:

- `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED=true`
- `HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED=true`
- `HOOPS_AI_CLIP_GPT_REVISION_ENABLED=true`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE=320`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO=320`
- `HOOPS_AI_CLIP_GPT_FREE_KEYFRAMES_PER_CLIP=10`
- `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP=10`

Do not claim the 85% accuracy target until the labeled internal footage bundle measures it.

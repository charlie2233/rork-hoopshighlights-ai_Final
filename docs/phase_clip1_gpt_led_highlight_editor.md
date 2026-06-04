# Phase Clip 1: GPT-Led Highlight Editor

Date: 2026-06-04
Branch: codex/phase-clip1-gpt-led-highlight-editor

## Goal

Make GPT the final semantic editor/director for HoopClips highlight selection while preserving the cloud-first architecture:

```text
CV/runtime = high-recall candidate finder
GPT = semantic editor/director over sampled keyframes and compact metadata
backend validator = safety and correctness gate
FFmpeg = deterministic renderer
```

## Architecture status

The backend already contains the core GPT-led editor path:

- `services/editing/editing_app/gpt_reranker.py` builds strict OpenAI Responses API payloads with sampled keyframes and compact clip metadata.
- `app.editing.apply_gpt_highlight_rerank` applies GPT keep/reject, ranking, captions, story order, slow-motion suggestions, crop focus, and outcome evidence only after backend validation.
- `build_agent_editing_context` supplies template-aware Agent Template Cookbook rules.
- `derive_user_prompt_intent` maps Export user text into structured intent instead of renderer commands.
- GPT outputs are strict JSON schema responses and are not stored by OpenAI requests from this path.
- GPT failure, disabled state, missing source, missing key, invalid JSON, duplicate decisions, incomplete decisions, and keyframe extraction failures all fall back to existing backend ranking.
- The backend rejects forbidden GPT-generated renderer commands, storage keys, URLs, local-render instructions, and policy-bypass content.

## What changed in this branch

This branch tightens the launch defaults so GPT reviews a stable candidate set instead of flooding the model with every plausible clip by default.

Default candidate/keyframe limits now match the product strategy:

- Free: top 8 GPT candidates, 3 keyframes per clip.
- Pro/Internal: top 30 GPT candidates, 6 keyframes per clip.
- Quality-beta/internal overrides can still raise the limits up to the existing hard backend caps.

The public GPT reranker status now exposes both legacy camelCase fields and launch-plan snake_case fields:

- `ai_clip_gpt_editor_enabled`
- `ai_clip_gpt_max_candidates_free`
- `ai_clip_gpt_max_candidates_pro`
- `ai_clip_gpt_max_candidates_internal`
- `ai_clip_gpt_keyframes_per_clip`

## Why this matters

The failed Troy/El Dorado review showed the raw candidate pool had too many false positives. Sending too many low-quality candidates to GPT makes final selection noisier and harder to debug. These defaults force the product path into the intended shape:

```text
input video -> raw candidates -> quality/duplicate/team filter -> compact GPT candidate set -> validated final EditPlan
```

## Backend safety rules preserved

- No full source video is sent to GPT.
- GPT never generates FFmpeg commands.
- GPT cannot bypass template, team, duration, policy, storage, or render validation.
- iOS remains a control surface only.
- Existing deterministic ranking remains the fallback when GPT is disabled or fails.

## Eval metrics to track next

For every real labeled test video, track:

- candidate recall
- candidate precision
- GPT keep precision
- wrong-team leakage
- miss-to-made drift
- defensive highlight retention
- duplicate rejection rate
- boring rejection rate
- final selected useful clip rate

Launch target remains:

- 85%+ useful final selected clips
- 0 obvious opponent-team leakage
- miss/made uncertainty rather than confident drift
- defensive events retained
- uncertain clips preserved for review

## Validation

Run after code changes:

```bash
git diff --check
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python \
  -m unittest discover services/editing/tests -p 'test_gpt_reranker.py' -v
```

Result:

- git diff --check: pass
- GPT reranker tests: 105 passed

## Next work

The next backend quality improvement should be an eval-backed GPT editor run over the Troy/white labels plus at least one more real case:

- verify selected-team scan reliability before GPT
- keep possession-level duplicate suppression before GPT
- compare GPT keep precision versus pre-GPT candidate precision
- report useful selected clip rate, wrong-team leakage, and miss/made uncertainty behavior

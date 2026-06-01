# Phase Launch154 GPT Free Keyframe Quality

## Goal

Improve internal TestFlight highlight accuracy for Free testers without reducing Free availability. Free users still get 3 AI edits per day, but staging can now give GPT the richer 10-keyframe evidence package for each candidate clip.

## Changes

- `HOOPS_AI_CLIP_GPT_FREE_KEYFRAMES_PER_CLIP` now defaults to `3` and clamps to `3...10` instead of being hard-fixed at `3`.
- Staging Cloud Build sets `HOOPS_AI_CLIP_GPT_FREE_KEYFRAMES_PER_CLIP=10`.
- The GitHub staging deploy path also sets `HOOPS_AI_CLIP_GPT_FREE_KEYFRAMES_PER_CLIP=10`.
- Launch config preflight now requires the Free staging keyframe setting and Cloud Run env mapping.
- Free daily AI edit availability remains `3`.

## Architecture

- Cloud still owns keyframe extraction, GPT clip selection, EditPlan generation, rendering, and storage.
- iOS behavior is unchanged.
- GPT still receives only existing candidate clip metadata plus sampled JPEG keyframes.
- Full videos, raw FFmpeg commands, storage keys, R2 credentials, and presigned URLs are not sent to GPT.

## Why This Helps

For Free internal testers, GPT previously saw only `start`, `eventCenter`, and `finish`. With the staging quality override, GPT can inspect release, shot arc, rim approach, rim entry, below-rim follow-through, and defensive outcome frames when available. That should reduce guessed-made clips and improve blocks, steals, and selected-team review decisions.

## Validation

Passed on June 1, 2026:

```sh
git diff --check
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_env_overrides_are_launch_bounded services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_keyframe_env_override_allows_quality_beta_depth -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
python3 -m unittest scripts.test_launch_backend_config_preflight -v
python3 -m py_compile services/editing/editing_app/gpt_reranker.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py
python3 scripts/launch_backend_config_preflight.py --json
```

- Focused GPT sampling tests passed: 3 passed, 0 failed.
- Full GPT reranker tests passed: 62 passed, 0 failed.
- Launch backend config preflight tests passed: 7 passed, 0 failed.
- Static launch backend config preflight passed: 82 pass findings, 0 failures, 12 warnings.

## Launch Notes

- This is an internal staging quality setting, not a client-side analysis change.
- Monitor OpenAI request size and latency during real TestFlight smoke before production cutover.

# Phase Clip13 High Resolution GPT Keyframes

## Goal

Improve GPT-led highlight selection quality by giving the vision editor sharper sampled keyframes. Since internal beta quality matters more than cost right now, GPT should receive enough visual detail to judge ball path, rim/result, player control, and camera clarity from existing candidate windows.

## Change

- Increased GPT keyframe extraction default width from `768` to `1024`.
- Increased allowed frame-width override cap from `768` to `1280`.
- Increased per-frame payload default from `300000` bytes to `750000` bytes.
- Increased allowed per-frame payload cap from `500000` bytes to `1000000` bytes.
- Kept all existing hard rules:
  - GPT receives sampled keyframes from existing candidate clips only.
  - GPT never receives full videos, source URLs, storage keys, presigned URLs, or FFmpeg commands.
  - Backend validators still own exact timestamps, EditPlan safety, rendering, and storage.

## Quality Rationale

The earlier pipeline already spends more semantic budget with `gpt-4.1`, 8 free candidate clips, 30 Pro/internal candidate clips, and up to 8 frames per clip. The remaining weakness was image detail: small or compressed frames make ball/rim judgment harder, especially for youth basketball footage from phone cameras. Raising the default image width and byte budget should make GPT’s semantic editor more reliable when judging setup, release, ball path, outcome, and watchability.

## Validation Evidence

- Red tests before implementation:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_default_visual_sampling_prioritizes_ball_and_rim_detail services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_visual_sampling_env_allows_quality_beta_high_resolution_cap -v`
  - Result before code change: failed because the default and cap were still `768`.
- Green focused tests after implementation:
  - Same command.
  - Result: 2 tests passed.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 30 tests passed.
- Editing service suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 70 tests passed.
- Full backend suite:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -v`
  - Result: 92 tests passed.
- Hygiene:
  - `python3 -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py`
  - `git diff --check`
  - Result: passed.

## Launch Notes

- No iOS code changed.
- No renderer behavior changed.
- Watch OpenAI usage in staging because frames can be larger, by design, for better highlight quality.

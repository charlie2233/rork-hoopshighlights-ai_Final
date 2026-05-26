# Phase Clip31: Free Quality GPT Candidate Budget

## Goal

Improve clip quality for Free users without increasing the number of free video-editing chances. The backend analysis pool now returns up to 30 candidates, but the GPT editor still capped Free reranking at 8 candidates. That meant good blocks, steals, complete shot-context plays, or selected-team uncertain clips could be cut before GPT reviewed them.

## Change

- Free GPT reranking now defaults to the full `30` candidate analysis pool.
- The Free candidate cap is clamped to `1...30`.
- Free keyframes remain at the high-quality default of `10` frames per clip, so GPT can inspect setup, release/action, shot arc, rim approach, rim entry, follow-through, and finish context.
- Pro/internal remains capped at `30` candidate clips.
- GPT timeout/output defaults are raised to `45s` and `6000` output tokens so full-pool review has enough room to return strict JSON decisions and plan edits.
- Sampling now reserves GPT review slots for defensive and selected-team uncertain candidates when the eligible pool is larger than the cap.
- The Free daily edit chance count remains `3`; this change spends more semantic review per edit, not more free edits.
- Existing kill switches still control whether GPT editing is live:
  - `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED`
  - `HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED`
  - `HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED`
  - `HOOPS_AI_CLIP_GPT_REVISION_ENABLED`

## Why This Matters

The product direction is quality-first during internal beta. A larger Free GPT candidate window makes it less likely that the first deterministic cutoff drops the best selected-team plays. The validators still reject tiny clips, pre-basket-only windows, unsafe GPT output, unsupported clip IDs, bad shot evidence, and confident opponent-team clips.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_candidate_cap_is_generous_but_bounded -v`
- `python3 -m unittest scripts.test_launch_backend_config_preflight.LaunchBackendConfigPreflightTests.test_quality_beta_uses_full_shot_tracker_keyframe_default -v`
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 78 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 112 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 39 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py` -> passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use this setting for internal TestFlight once GitHub Actions billing is unblocked and staging has a real OpenAI secret configured. Keep the public kill switches available so the team can disable GPT editing without changing iOS.

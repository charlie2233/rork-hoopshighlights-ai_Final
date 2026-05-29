# Phase Clip36: Full-Pool Free GPT Review

## Goal

Improve HoopClips highlight quality during internal beta by letting Free users get the same full 30-candidate GPT semantic review as Pro/internal. This keeps Free video-editing chances at `3`; it spends more cloud intelligence on each edit instead of increasing edit count.

## Change

- Free GPT clip review now defaults to `30` candidate clips, matching the backend analysis pool and Pro/internal candidate cap.
- The Free candidate cap is configurable with `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE` and legacy `HOOPS_GPT_HIGHLIGHT_RERANK_FREE_MAX_CLIPS`, clamped to `1..30`.
- GPT calls now default to `45s` timeout and `6000` output tokens so the full candidate pool can return strict JSON decisions, captions, story order, slow-motion suggestions, and plan edit hints.
- GPT sampling is now recall-balanced when the eligible pool is larger than the GPT cap:
  - selected-team uncertain clips reserve review slots instead of being crowded out by high-scoring makes
  - blocks, steals, forced turnovers, defensive stops, pressure/lockdown moments, and other defensive labels reserve review slots
  - defense-focused prompts and team/coach templates reserve a larger defensive slice
- Defensive non-shot clips, including standalone `Block` labels, now sample defensive keyframe roles (`defenseSetup`, `challenge`, `possessionChange`, `recovery`, `defenseOutcome`) instead of shot-arc/rim roles.
- Backend validation rejects defensive GPT keeps that cite unsampled defensive roles or omit sampled `possessionChange`/outcome evidence.
- Backend validation also rejects blocked-shot keeps that omit sampled `challenge`/blocked-outcome evidence.
- Staging Cloud Build explicitly sets:
  - `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE=30`
  - `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO=30`
  - `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP=10`
  - `HOOPS_AI_CLIP_GPT_TIMEOUT_SECONDS=45`
  - `HOOPS_AI_CLIP_GPT_MAX_OUTPUT_TOKENS=6000`

## Safety

- GPT still receives only compact candidate metadata and sampled JPEG keyframes from existing candidate windows.
- GPT still cannot see full videos, presigned URLs, R2 credentials, storage keys, source object keys, or FFmpeg commands.
- Backend validators still reject tiny clips, pre-basket-only windows, guessed outcomes, unsupported clip IDs, confident opponent-team clips, weak defensive clips, unsafe GPT content, and invalid plan patches.
- Selected-team uncertain clips remain reviewable instead of being treated as selected-team proof.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_reserves_buried_defensive_candidates_for_gpt_review services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_defensive_candidates_use_possession_change_keyframes services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_block_candidates_use_defensive_challenge_keyframes services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_defensive_keep_requires_sampled_possession_change_roles services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_blocked_keep_requires_sampled_challenge_and_outcome_roles services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_candidate_cap_is_generous_but_bounded -v`
- `python3 -m unittest scripts.test_launch_backend_config_preflight.LaunchBackendConfigPreflightTests.test_quality_beta_uses_full_shot_tracker_keyframe_default -v`
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py`
- `git diff --check`
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 84 passed
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 118 passed
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 39 passed

## Launch Recommendation

Use this for internal TestFlight once staging has `HOOPS_OPENAI_API_KEY` mounted and CI can execute jobs. Do not claim the 85% real-footage target until the labeled team/highlight accuracy harness passes on internal footage with makes, misses, blocks, steals, forced turnovers, confident opponent clips, and uncertain jersey-color clips.

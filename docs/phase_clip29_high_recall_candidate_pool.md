# Phase Clip29: High-Recall Candidate Pool

## Goal

Give the cloud/GPT editing path enough candidates to make better semantic choices. GPT was already configured to judge up to 30 Pro/internal clips, but cloud analysis still defaulted to returning only 8 clips. That made the final editor too dependent on an early narrow cutoff.

## Change

- `HOOPS_MAX_RETURNED_CLIPS` now defaults to `30`.
- The setting is clamped to `8...40` so staging can increase recall without accidentally flooding Review with hundreds of clips.
- iOS still reviews and sends candidate clips to cloud AI Edit; no local analysis/rendering/export behavior was added.
- The Free editing chance count remains `3`; this change broadens clip availability, not free usage count.

## Why This Matters

The requested direction is high recall first, then GPT as the semantic final editor. Returning 30 cloud candidates makes it more likely that good possessions, blocks, steals, and complete shot-context clips survive long enough for GPT/template selection and user Review. The existing quality filters still reject tiny clips, late pre-basket windows, and weak generic filler before GPT.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_thirty ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_backend_candidate_pool_env_is_clamped_for_review_safety ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_recall_fallback_returns_configured_candidate_pool -v` -> 3 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/config.py ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 112 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 77 tests passed, including local FFmpeg render coverage.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 35 tests passed.
- `git diff --check` -> passed.

No iOS source files changed in this phase. The current PR's preceding iOS team-scan work was already validated with the HoopsClips focused simulator test suite, simulator Debug build, and `xcodebuild build-for-testing` before this backend-only candidate-pool update.

## Launch Recommendation

Use the default 30-candidate pool for internal TestFlight. Keep `includeUncertain=true` for team targeting so uncertain but plausible plays remain reviewable. Do not claim real-world 85% team or highlight accuracy until a labeled internal footage eval set measures it.

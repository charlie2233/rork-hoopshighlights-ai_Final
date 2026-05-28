# Phase Clip96 Quality Defaults Preflight

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Keep the internal beta biased toward highlight quality and customer acquisition without quietly drifting away from launch policy. Free users should get broad GPT review per edit, but Free editing chances stay at `3`.

## Change

- Extended `scripts/launch_backend_config_preflight.py` so Cloud Run env mappings must include the GPT quality limits, not only the kill switches.
- Added static preflight checks that Free daily quota/render policy stays at `3` across:
  - control-plane fallback quota metadata
  - local analysis backend quota default
  - editing backend Free render policy
  - iOS Free policy copy
  - iOS Free/Pro UI smoke copy
- Added regression tests that make the required GPT and selected-team scan flag sets explicit, so launch defaults are harder to weaken by omission.

## Guardrails

- This does not add local iOS analysis, rendering, composition, or export.
- This does not send full videos to GPT.
- This does not expose secret values, R2 credentials, or presigned URLs.
- Existing kill switches still control whether GPT editor, GPT plan edit, GPT revisions, selected-team scan, and live rendering are enabled in staging.

## Validation Evidence

- `python3 -m py_compile scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py` passed.
- `python3 scripts/launch_backend_config_preflight.py --json` passed with `79 pass`, `12 warn`, `0 fail`.
- `python3 -m unittest scripts.test_launch_backend_config_preflight -v` passed: 7 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 70 tests.
- `npm --prefix services/control-plane test` passed: 28 tests.
- `npm --prefix services/control-plane run typecheck` passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_default_model_prioritizes_full_quality_vision_editor services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_default_visual_sampling_prioritizes_ball_and_rim_detail -v` passed: 4 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_plan_tier_policy_defaults_are_safe_without_statsig services.editing.tests.test_editing_service.EditingServiceTests.test_render_job_writes_output_log_and_download_url services.editing.tests.test_editing_service.EditingServiceTests.test_daily_render_limit_uses_feature_flag_default_override -v` passed: 3 tests.
- XcodeBuildMCP `build_sim` for `HoopsClips` Debug on iPhone 17 Pro simulator passed.
- XcodeBuildMCP `test_sim -only-testing:HoopsClipsTests/HoopsClipsTests` passed: 45 tests.
- `git diff --check` passed.
- `python3 scripts/submission_readiness_preflight.py --skip-live` exited `1` with `22 pass`, `2 warn`, `8 fail` after the code commit. Repo hygiene passed; remaining failures were missing launch-grade team accuracy report, unavailable physical iPhone, stale main-branch workflow evidence, unproven installed TestFlight smoke, unproven live Worker version route, missing Cloudflare deploy credential proof, and unproven live iOS kill-switch status through the Worker.
- PR #32 CI re-ran for this branch, but GitHub Actions failed before steps started because account payments failed or the Actions spending limit needs to be increased.

## Remaining Proof

The static launch preflight now guards quality defaults and Free=3 policy, but internal launch still requires the live TestFlight smoke and labeled team-highlight accuracy report before App Store submission.

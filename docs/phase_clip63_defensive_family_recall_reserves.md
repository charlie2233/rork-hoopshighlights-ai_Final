# Phase Clip63: Defensive Family Recall Reserves

## Goal

Improve real clip-selection quality for selected-team highlights by making blocks and steals survive the cloud analysis and GPT-review handoff. This phase does not claim the 85% target by itself; it makes the candidate pool better aligned with the eval gates from Phase Clip62.

## Change

- Selected-team analysis now expands the prefilter pool to `4x` the visible Review cap, bounded at `160` candidate clips.
- Team quick scan now defaults to `160` candidate clips, `60` rich candidates, and `720` total candidate frames.
- Analysis Review trimming reserves defensive variety by family, so a strong block cannot crowd out every steal when both are available.
- GPT rerank sampling also reserves defensive families before filling the remaining sample budget, so the final semantic editor sees both block and steal candidates when possible.
- The iOS app remains a control surface only; all scan, selection, GPT review, and render decisions stay cloud-owned.

## Defensive Families

The reserve pass recognizes:

- `block`
- `steal`
- `forced_turnover`
- `defensive_stop`
- general `defensive`

When the defensive reserve has room for multiple plays, the backend takes the best available candidate from distinct families first, then fills any remaining defensive reserve by normal quality rank.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_forty ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_selected_team_candidate_pool_limit_is_expanded_but_bounded ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_review_trim_reserves_block_and_steal_families_when_available -v`
  - Passed: 3 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_total_clip_frame_budget_allows_configured_beta_ceiling -v`
  - Passed: 1 test.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_reserves_block_and_steal_families_for_gpt_review -v`
  - Passed: 1 test.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Passed: 150 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Passed: 93 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Passed: 46 tests.
- `git diff --check`
  - Passed.

## CI Evidence

After commit `de3d9c641915fc44ef9600e6def24482de74f505`, GitHub Actions created these PR runs:

- `iOS Internal TestFlight Upload` run `26503068187`
  - Failed before any runner step started.
  - Failed job: `No-secret internal staging codecheck`.
  - GitHub annotation: `The job was not started because recent account payments have failed or your spending limit needs to be increased.`
  - `Build internal staging TestFlight archive` was skipped because this was a pull request codecheck run, not a manual archive/upload operation.
- `Cloud Edit Deploy Preflight` run `26503068195`
  - Failed before any runner step started.
  - Failed jobs: `Worker typecheck and dry run`, `Editing backend Python tests`.
  - GitHub annotation on both failed jobs: `The job was not started because recent account payments have failed or your spending limit needs to be increased.`
  - `Verify cloud edit deploy secrets` was skipped because the codecheck jobs did not start and the run was not a manual deploy/preflight operation.

No failed-step logs were available for these jobs because GitHub did not allocate runners.

## Launch Recommendation

Use the larger scan budget for internal beta. If latency becomes painful, lower the environment caps temporarily, but do not claim the selected-team 85% target until labeled footage proves makes, misses, blocks, steals, uncertain team clips, and bad timing/outcome negatives all pass.

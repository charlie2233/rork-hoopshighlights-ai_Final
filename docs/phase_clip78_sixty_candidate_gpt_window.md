# Phase Clip78: Sixty-Candidate GPT Window

## Goal

Improve selected-team and defensive-highlight recall by removing the remaining 40-candidate bottleneck between cloud analysis, iOS Review, AI Edit, and GPT-led highlight editing.

## Changes

- `HOOPS_MAX_RETURNED_CLIPS` now defaults to `60` and clamps to `8...60`, so iOS Review and AI Edit can receive more cloud-ranked candidates before the user or GPT makes final choices.
- `GPT_CANDIDATE_REVIEW_LIMIT` is now `60`, which expands structured request validation, GPT plan edit arrays, story-order arrays, and AI Work Receipt summary IDs without changing renderer authority.
- GPT candidate caps now default to `60` for Free and Pro/internal while keeping per-clip keyframes at `10`.
- GPT structured-output budget defaults to `12000` tokens so 60 clip decisions plus optional plan edit JSON have room to return complete strict JSON.
- Cloud Build deploy defaults and launch preflight expectations now require the 60-candidate settings.

## Architecture Guardrails

- Cloud analysis still owns candidate generation, team attribution, GPT selection, edit planning, and render handoff.
- iOS only displays Review candidates, sends export controls/user intent, previews completed renders, downloads, and shares.
- GPT only receives compact clip metadata and sampled keyframes from existing candidate clip windows.
- GPT still cannot generate FFmpeg commands, invent clip IDs, replace CV/timestamp logic, or bypass EditPlan validators.
- Free availability stays broad for acquisition; the daily Free editing chance default remains `3`.

## Quality Rationale

The team quick scan can now inspect up to 160 action-anchored candidates with a richer frame budget. Returning and reranking only 40 clips after that scan can drop useful selected-team, uncertain, block, steal, or defensive-stop moments before GPT/user review. A 60-candidate window gives GPT more recall to reject boring/duplicate/unclear moments while still keeping the payload bounded and structured.

## Validation Evidence

Local validation run on branch `codex/phase-clip28-cloud-team-quick-scan`:

```bash
python3 -m py_compile ios/backend/app/config.py ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py -> passed
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_sixty ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_backend_candidate_pool_env_is_clamped_for_review_safety -v -> 2 tests passed
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_candidate_cap_is_generous_but_bounded -v -> 3 tests passed
python3 -m unittest scripts.test_launch_backend_config_preflight -v -> 4 tests passed
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover ios/backend/tests -v -> 165 tests passed
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover services/editing/tests -v -> 93 tests passed
python3 -m unittest discover -s scripts -p 'test_*.py' -v -> 55 tests passed
git diff --check -> passed
```

## Launch Notes

- Deploy analysis and editing backends together so Review, AI Edit, and GPT limits stay aligned.
- Keep existing kill switches available: `ai_edit_enabled`, `ai_edit_live_render_enabled`, `ai_edit_revisions_enabled`, `ai_edit_templates_enabled`, `ai_clip_gpt_editor_enabled`, `ai_clip_gpt_plan_edit_enabled`, and `ai_clip_gpt_revision_enabled`.
- Real labeled-footage evaluation is still required before claiming the target 85% selected-team highlight accuracy.

# Phase Clip156: Full-Pool GPT Review On Launch70

## Goal

Align GPT-led highlight editing with the current high-recall cloud analysis pool. HoopClips should bias internal beta quality and Free availability toward more semantic review per edit, while keeping Free video-editing chances capped at `3`.

## Change

- Free GPT clip review now defaults to `160` candidate clips with `3` keyframes per clip.
- Pro/internal GPT clip review now defaults to `160` candidate clips with `5...8` keyframes per clip.
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE` and legacy `HOOPS_GPT_HIGHLIGHT_RERANK_FREE_MAX_CLIPS` now clamp to `1...160`.
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO` and legacy `HOOPS_GPT_HIGHLIGHT_RERANK_PAID_MAX_CLIPS` now clamp to `20...160`.
- Staging deploy defaults in `services/editing/cloudbuild.yaml` and the secret-gated deploy workflow now set both Free and Pro/internal GPT candidate caps to `160`.
- Static backend config preflight now requires those `160`-candidate GPT quality defaults.

## Guardrails

- Cloud still owns candidate generation, GPT clip selection, EditPlan planning, rendering, storage, and retention.
- iOS still only uploads, shows Review/Export/status/timeline, previews, downloads, shares, and sends user commands.
- GPT still receives existing candidate clip metadata and sampled keyframes only.
- Full videos, R2 credentials, source object keys, full presigned URLs, and raw FFmpeg commands are not sent to GPT.
- Free daily AI edit chances remain guarded at `3` by the quota/policy layer and static preflight tests.

## Why

The analysis backend now returns up to `160` candidates and `GPT_CANDIDATE_REVIEW_LIMIT` is `160`. Keeping the GPT semantic editor at `8`, `30`, or `60` candidates could drop clear blocks, steals, defensive stops, selected-team uncertain clips, or late high-quality moments before GPT could judge them. The wider cap lets GPT reject boring, duplicate, unclear, and opponent-team clips from the same high-recall pool the user can review.

## Validation

```bash
python3 -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_env_overrides_are_launch_bounded services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_caps_are_applied_before_openai_call -v
python3 -m unittest scripts.test_launch_backend_config_preflight -v
ruby -e 'require "yaml"; YAML.load_file("services/editing/cloudbuild.yaml"); YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "yaml parses"'
python3 -m unittest discover -s scripts -p 'test_*.py'
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py'
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py'
python3 scripts/launch_backend_config_preflight.py --json
Build iOS Apps plugin: test_sim HoopsClips Debug iPhone 17 Pro -only-testing:HoopsClipsTests/CloudEditServiceTests
```

Results:

- Python compile: passed.
- Focused GPT reranker tests: 4 passed.
- Static backend config preflight tests: 7 passed.
- YAML parse check: passed.
- `scripts` unittest discovery: 126 passed.
- `services/editing/tests` discovery: 117 passed, including local render, revision, history, and GPT reranker coverage.
- `ios/backend/tests` discovery: 207 passed.
- Backend config preflight: 81 passed, 12 warned, 0 failed.
- Targeted `CloudEditServiceTests`: 11 passed via the Build iOS Apps plugin.

## Launch Notes

- Deploy analysis and editing together so Review, AI Edit, and GPT limits stay aligned around the 160-candidate pool.
- Keep all GPT/editing kill switches available for staging rollback.
- Do not claim internal submission readiness until the launch-grade labeled footage report and installed TestFlight smoke are proven.

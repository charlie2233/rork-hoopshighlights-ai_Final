# Phase Clip2: GPT Decision Integrity

Date: 2026-05-24
Branch: `codex/phase-clip2-gpt-decision-integrity`

## Scope

- Tightened GPT highlight reranker validation so duplicate clip decisions fall back instead of silently letting one response overwrite another.
- Tightened GPT `planEdit` accounting so invalid plan references do not appear as applied in the AI Work Receipt.
- Added tests for duplicate GPT decisions and invalid GPT plan references.

## Architecture

HoopClips remains cloud-first. The backend owns GPT selection, edit planning, validation, rendering, storage, and receipts. iOS remains the control surface for upload, review, status, preview, download, share, and user commands.

GPT still receives only sampled keyframes and compact candidate metadata. It does not receive full videos, source video URLs, R2 credentials, presigned URLs, or permission to generate FFmpeg commands. The renderer continues to execute only deterministic, validated `EditPlan` JSON.

## Integrity Rules

The GPT reranker now requires exactly one valid decision for every sampled candidate clip before applying model output:

- Missing sampled clip decisions fall back with `incomplete_gpt_decisions`.
- Duplicate sampled clip decisions fall back with `duplicate_gpt_decisions`.
- Decisions for clips outside the sampled pool do not satisfy completeness.

The backend also now reports `planEditApplied=true` only when the validated `planEdit` actually changes at least one kept clip:

- valid story ordering for kept clips
- valid caption override for kept clips
- valid slow-motion moment for kept clips

If GPT returns `planEdit` entries that reference only unknown clips, the plan edit is ignored and the AI Work Receipt records `planEditApplied=false`.

## Validation

Commands run:

```sh
python3 -m py_compile services/editing/editing_app/gpt_reranker.py ios/backend/app/editing.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_duplicate_gpt_decisions_fall_back ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_plan_edit_ignores_invalid_clip_references -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
python3 scripts/staging_version_probe.py
python3 scripts/submission_readiness_preflight.py
```

Results:

- Python compile: passed.
- Focused integrity tests: 2 passed.
- Affected GPT reranker/edit-plan suites: 46 tests passed.
- `ios/backend/tests` discovery: 44 tests passed.
- `services/editing/tests` discovery: 52 tests passed, including local FFmpeg render/revision/download-history coverage.
- `scripts` discovery: 27 tests passed.
- `git diff --check`: passed.
- `scripts/staging_version_probe.py`: failed with `diagnosis=worker_route_missing_and_editing_version_stale`.
- `scripts/submission_readiness_preflight.py` before commit: `pass=18 warn=1 fail=13` because this branch still had tracked changes and one untracked doc. The live/provider blockers remain valid.
- `scripts/submission_readiness_preflight.py` after commit: `pass=20 warn=0 fail=12`. Repo hygiene passed; live/provider blockers remain.

## Launch Notes

This branch improves GPT-led clipping quality and receipt truthfulness, but it does not make the app ready for Apple/TestFlight submission by itself. Known launch blockers from the current preflight still include stale/unproxied staging editing version state, missing deploy credentials, missing signed iOS archive/upload artifact, missing local signing inputs, and unproven installed-device TestFlight smoke.

Current live readiness blockers:

- Staging Worker `/v1/editing/version` returns HTTP 404.
- Direct staging editing `/version` is reachable but missing `aiEditLiveRenderEnabled`.
- Direct staging editing `gitSha` is stale and does not match the current checkout.
- Required deploy inputs are not present in this environment: `CLOUDFLARE_API_TOKEN`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, `GCP_REGION`.
- Required iOS upload inputs are not present in this environment.
- No `.xcarchive` or `.ipa` upload artifact is present under expected build output locations.
- No available physical iPhone was detected for installed TestFlight smoke.

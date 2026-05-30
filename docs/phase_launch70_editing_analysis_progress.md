# Phase Launch70 Editing Analysis Progress

## Goal

Keep selected-team cloud analysis alive with real backend progress while the editing service performs long-running team-aware analysis. This phase does not move analysis/rendering into iOS.

## Live Failure That Triggered This Patch

- Branch before this phase: `codex/phase-launch69-selected-team-editing-provider`
- Commit before this phase: `537e07518a1a13ed0de68ee39e5dfac35dbba2cd`
- Command:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch69_downloads_326_team \
  --video-id downloads_326_1770329282 \
  --team-mode team \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch69 \
  --manifest artifacts/team_highlight_accuracy_launch69_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 1800
```

- Result: failed.
- Job ID: `8d0781a768cf45fd87c95dffe9d2e5ae`
- Failure: `failed_timeout`, `Inference callback timed out after 3 accepted attempts.`
- Cloud Run request log proof: `hoopclips-editing-staging` accepted `POST /v1/analyze` at `2026-05-30T20:27:33Z`.

This proved the selected-team request reached the editing provider. The remaining issue was that the Worker had no observable progress before its stale-processing timeout.

## Changes

- Editing `/v1/analyze` now sends real `processing` callbacks through the existing Worker callback endpoint before and during analysis.
- Editing still sends the existing heartbeat endpoint, but progress callbacks use the same route as final success/failure callbacks for better liveness coverage.
- Editing emits safe structured analysis events:
  - `analysis.dispatch.started`
  - `analysis.heartbeat.sent` / `analysis.heartbeat.failed`
  - `analysis.progress_callback.sent` / `analysis.progress_callback.failed`
  - `analysis.source.materialized`
  - `analysis.run.started`
  - `analysis.run.completed`
  - `analysis.callback.sent` / `analysis.callback.failed`
- Worker recovery now has a configurable selected-team timeout:
  - `SELECTED_TEAM_PROCESSING_TIMEOUT_SECONDS`
  - default/staging value: `1800`
- Normal all-team/legacy processing keeps the existing `PROCESSING_TIMEOUT_SECONDS` behavior.

## Safety

- No source URLs, object keys, presigned URLs, R2 credentials, or secrets are emitted in the new logs.
- GPT/analysis remains cloud-owned.
- iOS receives only real job status/progress from the Worker.
- No fake thinking, fake ETA, or artificial waits were added.

## Validation

Local verification before deploy:

```bash
python3 -m py_compile services/editing/editing_app/main.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_analyze_endpoint_accepts_worker_dispatch_and_posts_callback -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover services/editing/tests -v
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test -- --test-name-pattern 'processing callbacks|selected-team editing jobs|heartbeat|timeout|selected team'
npm --prefix services/control-plane test
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
npm --prefix services/control-plane run deploy:staging:dry-run
cd services/control-plane && npx prettier --check src/env.ts src/recovery.ts test/control-plane-timeout-recovery.test.ts ../../scripts/control-plane-harness.ts
cd services/control-plane && npx prettier --check --trailing-comma none wrangler.jsonc
git diff --check
```

- `py_compile`: passed.
- Focused editing `/v1/analyze` progress callback test: passed.
- Full editing-service suite: 116 tests passed.
- Control-plane typecheck: passed.
- Focused control-plane timeout/selected-team suite: 33 tests passed.
- Full control-plane suite: 33 tests passed.
- Launch script suite: 115 tests passed after keeping `wrangler.jsonc` parseable without trailing commas.
- Worker staging dry run: passed and showed `SELECTED_TEAM_PROCESSING_TIMEOUT_SECONDS=1800`.
- Prettier check: passed for TypeScript and `wrangler.jsonc` with no trailing commas.
- `git diff --check`: passed.

## CI Attempt

- GitHub Actions run: `26694624663`
- Result: failed before deploy.
- Passed: Worker typecheck/dry run and editing backend Python tests.
- Failed: launch script tests rejected the first `wrangler.jsonc` formatting because trailing commas made the repo's JSONC preflight parser fail.
- Local fix: removed trailing commas, reran the exact failing test plus the full launch script suite and staging dry run successfully.

- GitHub Actions run: `26694736663`
- Result: passed.
- Deployed staging editing service and staging Worker for commit `5fb981dfcbd75492adea2270ed9ed99298602317`.
- Staging version probe passed for direct editing `/version` and Worker `/v1/editing/version`.

## Live Launch70 Finding

Real selected-team collection was rerun after deploy:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch70_downloads_326_team \
  --video-id downloads_326_1770329282 \
  --team-mode team \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch70 \
  --manifest artifacts/team_highlight_accuracy_launch70_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 2400
```

- Job ID: `7ab4ef8e55ca46fb9e9a5318d4cc8e3f`
- Editing service accepted and completed analysis.
- Editing logs showed `analysis.run.completed`.
- Editing callbacks and heartbeats failed before reaching the Worker.
- Route probe without a service User-Agent returned Cloudflare `error code: 1010`.
- Route probe with `User-Agent: HoopClipsEditingService/1.0` reached the Worker and returned the expected invalid-secret JSON.

This means the selected-team backend was no longer stuck in analysis; Cloudflare Browser Integrity rejected default Python `urllib` callback requests before the Worker route could authenticate them.

## Follow-Up Patch

- Editing callback and heartbeat requests now send `User-Agent: HoopClipsEditingService/1.0`.
- Safe callback failure logging now includes failure codes such as `callback_http_403` and `heartbeat_http_403`, without logging secrets, credentials, object keys, source URLs, or full presigned URLs.
- Added a regression test that verifies both callback and heartbeat requests include the service User-Agent and inference callback secret header.

Additional local validation:

```bash
python3 -m py_compile services/editing/editing_app/main.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_worker_callbacks_use_service_user_agent services.editing.tests.test_editing_service.EditingServiceTests.test_analyze_endpoint_accepts_worker_dispatch_and_posts_callback -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover services/editing/tests -v
```

- `py_compile`: passed.
- Focused callback/User-Agent tests: passed.
- Full editing-service suite: 117 tests passed.

## Callback Fix Deploy

To avoid another full GitHub Actions deploy run, only the editing Cloud Run service was redeployed with the existing Cloud Build config:

```bash
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG="$(git rev-parse HEAD)"
```

- Commit: `bdbd3f2c408f67b484896f5f5a025e55bf990b90`
- Cloud Build ID: `5fc61324-aca8-45f1-9f90-b7ff165f511f`
- Result: `SUCCESS`
- Cloud Run revision: `hoopclips-editing-staging-00034-xj4`
- Traffic: 100% to `hoopclips-editing-staging-00034-xj4`
- Note: deploy printed an IAM policy warning, but the existing service URL remained reachable.

Version proof:

```bash
python3 scripts/staging_version_probe.py --expected-git-sha "$(git rev-parse HEAD)" --json
```

- Direct editing `/version`: passed for `bdbd3f2c408f67b484896f5f5a025e55bf990b90`.
- Worker `/v1/editing/version`: passed for `bdbd3f2c408f67b484896f5f5a025e55bf990b90`.

## Live Launch70 Success

The same real selected-team collection was rerun after the callback fix deploy:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch70_downloads_326_team \
  --video-id downloads_326_1770329282 \
  --team-mode team \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch70 \
  --manifest artifacts/team_highlight_accuracy_launch70_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 2400
```

- Result: passed.
- Job ID: `36d008a66e454da899a8037721a53d78`
- Final job status: `completed`
- Detected teams: 2
- Selected team: `team_black` / `black`
- Clip count: 3
- Local artifact paths:
  - `artifacts/team_highlight_accuracy_launch70/launch70_downloads_326_team/analysis_result.json`
  - `artifacts/team_highlight_accuracy_launch70/launch70_downloads_326_team/manual_labels_template.json`
  - `artifacts/team_highlight_accuracy_launch70_manifest.json`

Safe Cloud Run event proof for job `36d008a66e454da899a8037721a53d78`:

- `analysis.dispatch.started`
- `analysis.heartbeat.sent` at `Preparing cloud analysis input`
- `analysis.progress_callback.sent` at `Preparing cloud analysis input`, progress `0.64`
- `analysis.source.materialized`
- `analysis.heartbeat.sent` at `Analyzing in cloud`
- `analysis.progress_callback.sent` at `Analyzing in cloud`, progress `0.72`
- `analysis.run.started`
- `analysis.run.completed`, `clipCount=3`
- `analysis.callback.sent`, `status=succeeded`

Selected-team analysis now has proven real backend progress callbacks and a final completion callback through the Worker. Manual labels are still needed to score the clips for the target 85%+ team/highlight accuracy gate.

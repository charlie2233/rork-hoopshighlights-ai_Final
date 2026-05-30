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

After deploy, rerun the real selected-team accuracy collection and capture the job ID plus generated artifacts or sanitized failure state.

# Phase Launch68 Analysis Heartbeats

Date: 2026-05-30
Branch: `codex/phase-launch68-analysis-heartbeats`
Base: `main` at `8c67898`

## Scope

Unblock launch accuracy collection after the real staging selected-team analysis path moved past the missing `/v1/analyze` endpoint and then timed out while the editing service was still working.

Real staging evidence before this phase:

- Previous missing endpoint job: `22757c17e22a4c37bb1f9f8b52017e57`
- Fixed deploy SHA: `8c67898e435a2481d09ba8c9917fe59d94a86b73`
- Next real collection job: `f2ec690889ce4a51a9ca3075431fb254`
- Last live processing state before client timeout: `Running external inference service`, progress `0.6`, attempt `3`
- Final state after Worker timeout: `failed_timeout`
- Failure reason: `Inference callback timed out after 3 accepted attempts.`

## Root Cause

The Worker already exposes an internal inference heartbeat endpoint, but stale-processing recovery used the original `processingStartedAt` time as the timeout anchor. A long cloud analysis could therefore be retried and eventually failed even if the editing backend was alive.

The editing `/v1/analyze` compatibility endpoint also did not send liveness heartbeats while it materialized the cloud source and ran the analysis pipeline.

## Changes

- Editing service sends real inference heartbeats to `/internal/inference/heartbeat/{jobId}` while `/v1/analyze` work is running.
- Heartbeats start before source materialization and continue during cloud analysis.
- Heartbeat payloads include only safe job/timeline metadata and a real processing stage.
- Heartbeats do not include `sourceUrl`, `sourceObjectKey`, raw storage keys, or full presigned URLs.
- Worker heartbeat updates `updatedAt` to the heartbeat receive time.
- Stale-processing recovery uses the latest valid timestamp from `processingStartedAt` and `updatedAt`, so fresh heartbeats keep long-running analysis attempts alive.
- Periodic heartbeats do not advance invented progress; they preserve the current Worker progress unless a caller supplies a validated numeric progress.

## Architecture

- Cloud backend still owns analysis, GPT-assisted candidate quality improvements, team filtering, edit planning, rendering, and storage.
- iOS behavior is unchanged.
- The UI can show real backend stages such as `Preparing cloud analysis input` and `Analyzing in cloud`; this is not artificial thinking or fake ETA copy.
- GPT remains an editing aid only and does not replace CV/timestamp/FFmpeg validators.

## Validation

Commands run:

```bash
python3 -m py_compile services/editing/editing_app/main.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_analyze_endpoint_accepts_worker_dispatch_and_posts_callback -v
npm --prefix services/control-plane test -- --test-name-pattern 'fresh inference heartbeats|stale processing jobs|exhausted stale processing'
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test -- --test-name-pattern 'heartbeat|timeout|selected team|falls back to editing analysis'
cd services/control-plane && npx prettier --check src/recovery.ts src/routes/internal.ts test/control-plane-timeout-recovery.test.ts
git diff --check
```

Results:

- Python compile passed.
- Focused editing heartbeat/callback test passed.
- Full editing-service tests passed: 116 tests.
- Control-plane typecheck passed.
- Focused control-plane heartbeat/timeout/selected-team tests passed: 31 tests.
- Prettier check passed for touched control-plane files.
- Diff whitespace check passed.

## Launch Notes

After local validation, deploy this branch once through the Cloud Edit Deploy Preflight workflow to conserve GitHub Actions budget. Then probe staging versions and rerun the real selected-team accuracy collection:

```bash
python3 scripts/staging_version_probe.py --expected-git-sha <deployed-sha> --json
python3 scripts/collect_team_highlight_accuracy_case.py --video-path /Users/hanfei/Downloads/326_1770329282.mp4 --case-id launch68_downloads_326_team --video-id downloads_326_1770329282 --team-mode team --duration-seconds 30 --output-dir artifacts/team_highlight_accuracy_launch68 --manifest artifacts/team_highlight_accuracy_launch68_manifest.json --poll-interval-seconds 5 --timeout-seconds 1800
```

If the collection completes, create/fill the manual label template and rebuild the launch-grade team/highlight accuracy report. If it still fails, inspect the sanitized Worker job state and editing service logs for callback delivery or pipeline exceptions before changing timeout policy.

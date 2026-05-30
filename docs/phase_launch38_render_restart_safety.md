# Phase Launch38 Render Restart Safety

## Goal

Make cloud AI Edit renders safe across backend restarts so iOS can keep showing real render status and retrying the same job without creating fake progress, local rendering, or duplicate outputs.

## Architecture

- Cloud editing backend owns render state, request reconstruction, FFmpeg rendering, storage, and AI Work Timeline/Receipt generation.
- iOS remains a control surface for status, preview, download, share, and retry commands.
- No render work moves into iOS.
- Recovery never sends full videos to GPT and never asks GPT for FFmpeg commands.
- Logs do not include secrets, R2 credentials, or full presigned URLs.

## Implementation

- Added durable render request payload storage under `render_state/render_requests/{renderJobId}.json`.
- `request_for_render_job` now restores requests in this order:
  1. in-memory request map
  2. durable render request payload
  3. stored edit job payload plus stored revision plan, when applicable
- `run_render_job` no longer indexes the volatile request map before entering error handling. It reacquires a durable lease first, reconstructs the request, and marks the job failed with `missing_render_request` if recovery is impossible.
- Existing active jobs returned by idempotent render retry, latest render lookup, render history, or render status are now rescheduled when:
  - status is `queued`, `created`, or `render_requested`, or
  - status is `rendering` but there is no unexpired lease.
- Jobs with an active unexpired lease are returned as active and not double-run.
- Recovery emits `render.recovery_scheduled` with job IDs and status only.

## Validation

Commands run locally:

```bash
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest \
  services.editing.tests.test_editing_service.EditingServiceTests.test_queued_render_after_reload_restarts_from_stored_edit_job_payload \
  services.editing.tests.test_editing_service.EditingServiceTests.test_queued_revision_render_after_reload_restarts_from_persisted_revision_plan

PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests
```

Result:

- Focused recovery tests passed.
- Full editing backend suite passed: 111 tests.
- Evidence logs showed `render.recovery_scheduled`, `render.lease_acquired`, `render.started`, and `render.completed` for both base render and revision render recovery.
- Existing stale unrecoverable render behavior still returns `failed_timeout`.

GitHub launch state checked:

- Main push iOS internal staging codecheck run `26668956688`: success.
- Manual cloud deploy preflight run `26668982164`: failed only on Cloudflare Wrangler auth.
- The same run confirmed GCP project, Artifact Registry, Cloud Run service, R2 endpoint, and all required Secret Manager entries including `HOOPS_OPENAI_API_KEY` exist with enabled latest versions.

## Current Blocker

`CLOUDFLARE_API_TOKEN` still fails Wrangler authentication in GitHub Actions. GCP secret metadata and Secret Manager access are no longer the active blocker based on run `26668982164`.

## Launch Recommendation

Before internal TestFlight smoke, replace or rescope the GitHub staging `CLOUDFLARE_API_TOKEN`, rerun `cloud-edit-deploy-preflight.yml` with `operation=preflight`, then deploy staging and verify `/v1/editing/version` through the Worker before triggering a TestFlight upload.

# Phase Edit7b Render Concurrency And Revision Persistence

## Goal

Phase Edit7b hardens the HoopClips AI Edit Agent cloud renderer for beta-scale operation. The work keeps the architecture cloud-first:

```text
iOS Export UI -> Cloudflare Worker -> Cloud Run editing service -> FFmpeg -> R2/local render storage
```

iOS still does not analyze, patch plans, compose video, or render final exports locally.

## Render Lease Design

Render jobs now persist execution lease fields in durable state:

- `leaseOwner`
- `leaseToken`
- `leaseAcquiredAt`
- `leaseExpiresAt`
- `heartbeatAt`

The editing service acquires a durable lease before moving a job into `rendering`. Only the active lease holder can persist completion or failure state. The lease is written through conditional storage operations:

- local storage uses a process lock plus content hash checks
- R2 storage uses conditional `If-Match` / `If-None-Match` writes where supported

This is a safety layer around the existing durable render record. It prevents obvious duplicate execution and stale-worker overwrites in tests, while Cloud Run remains pinned at `max-instances=1` until a live multi-instance smoke proves the production storage semantics.

## Lease Rules

- duplicate render requests return the existing active/rendered job through idempotency
- an active non-expired lease blocks a second executor
- an expired lease can be reclaimed by another executor
- a completion/failure write with the wrong lease token is rejected
- a stale worker cannot overwrite a reclaimed or completed render
- stale active jobs transition to `failed_timeout`

Safe observability events include:

- `render.lease_acquired`
- `render.lease_conflict`
- `render.failed`
- `render.completed`

No secret values or full presigned URLs are emitted.

## Revision Persistence

Revision definitions and revised plans now persist independently from process memory.

Stored edit job state:

```text
render_state/edit_jobs/{editJobId}/edit_job.json
```

Stored revised plans:

```text
edits/{editJobId}/plans/{planId}.json
```

Stored revision definitions:

```text
edits/{editJobId}/revisions/{revisionId}.json
```

Revision index:

```text
render_state/edit_jobs/{editJobId}/revisions.json
```

This means a revision can be listed, fetched, and rendered after an app/service reload. Revision render metadata continues to include `revisionId` in render status and render logs.

## R2 Cleanup Dry-Run

The cleanup path is intentionally safe-first.

Command:

```bash
python services/editing/scripts/render_retention_cleanup.py
```

Useful local dry-run:

```bash
python services/editing/scripts/render_retention_cleanup.py \
  --render-storage-provider local \
  --upload-root /tmp/hoops-render-storage
```

The dry-run scans durable render metadata for:

```text
deleteEligible=true
expiresAt < now
retentionClass allowed by optional filter
```

It reports candidate object keys for `final.mp4`, `render_log.json`, and the durable render-state record. It deletes nothing unless `--execute` is explicitly passed.

## CI Deploy Readiness

Added a manual preflight workflow:

```text
.github/workflows/cloud-edit-deploy-preflight.yml
```

Required CI inputs:

- `CLOUDFLARE_API_TOKEN`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`
- `GCP_PROJECT_ID`
- `GCP_REGION`

Cloudflare token permissions:

- Workers Scripts Edit
- Workers Tail Read, optional
- R2 Read/Write if CI verifies render artifacts

GCP deploy identity requirements:

- Cloud Build submit permission
- Artifact Registry write access
- Cloud Run deploy permission for the editing service
- Secret Manager accessor for deploy-time secret wiring
- Service Account User on the Cloud Run runtime service account if applicable

## Scaling Plan

Keep staging at:

```text
Cloud Run max-instances=1
```

Do not raise to `2+` until:

- lease tests pass
- duplicate live render smoke returns one render job
- revision render after reload passes live
- cleanup dry-run is verified on staging metadata
- observability confirms no double render

## Validation

Run locally with the repo Python environment:

```bash
ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service
ios/backend/.venv/bin/python services/editing/scripts/render_retention_cleanup.py --render-storage-provider local --upload-root /tmp/hoops-cleanup-empty
```

Focused evidence from this branch:

- render lease rejects second active executor
- expired lease can be reclaimed
- wrong lease token cannot complete render
- stale worker cannot overwrite reclaimed render
- revision list/get survive app reload
- revised plan persists under `edits/{editJobId}/plans/{planId}.json`
- revision render after reload completes with `revisionId`
- cleanup dry-run reports expired delete-eligible artifacts without deleting them

Live Worker -> Cloud Run -> R2 smoke was not rerun in this branch. Run one before raising Cloud Run concurrency.

## Remaining Beta Blockers

- install CI secret values in the staging/prod environments
- run a live multi-instance duplicate render smoke before changing Cloud Run max instances
- run cleanup dry-run against staging R2 metadata
- decide whether render dispatch should move to Cloud Tasks, Pub/Sub, or Durable Objects before broader beta load

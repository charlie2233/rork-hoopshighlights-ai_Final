# Phase Edit7a Durable Render State And CI Deploy

## Goal

Phase Edit7a prepares the HoopClips AI Edit Agent for beta operation by making render job status durable and by documenting repeatable deploy requirements.

The architecture remains cloud-first:

```text
iOS Export UI -> Cloudflare control plane -> Cloud Run editing service -> FFmpeg -> R2 final.mp4/render_log.json
```

iOS still does not analyze, plan, patch, or render video locally.

## Durable Render State Design

The editing service now persists render job state through the existing render storage abstraction. In staging this uses the R2 results bucket; in local tests it uses the configured local upload root.

Durable state is intentionally small JSON, not video payloads. Final videos and render logs still use the existing output keys.

### State Keys

Canonical render job state:

```text
render_state/render_jobs/{renderJobId}.json
```

Latest render for an edit job:

```text
render_state/edit_jobs/{editJobId}/latest.json
```

Idempotency lookup:

```text
render_state/idempotency/{sha256(idempotencyKey)}.json
```

Install quota lookup:

```text
render_state/installs/{sha256(installId)}.json
```

Hashing install IDs and idempotency keys keeps those raw identifiers out of object names while still allowing deterministic lookup.

## Persisted Fields

Each render state record persists:

- `renderJobId`
- `editJobId`
- `revisionId`
- `idempotencyKey`
- `status`
- `planVersion`
- `templateId`
- `planTier`
- `sourceObjectKey`
- `outputObjectKey`
- `renderLogObjectKey`
- `createdAt`
- `updatedAt`
- `startedAt`
- `completedAt`
- `expiresAt`
- `failureReason`
- `retryCount`
- `rendererVersion`
- `outputBytes`
- `durationSeconds`
- `aspectRatio`
- `retentionMetadata`
- `validationErrors`

The API response also includes `planVersion` so clients and proxy types can inspect the plan version without reading the full plan.

## Status Transitions

Supported render statuses are:

```text
created
queued
rendering
rendered
failed
failed_timeout
cancelled
```

Current flow:

```text
queued -> rendering -> rendered
queued -> failed
rendering -> failed
rendering -> failed_timeout
```

`failed_timeout` is now an explicit API status rather than only a `failureReason` under generic `failed`.

## Idempotency Rules

Render creation checks durable state before creating a new job:

1. Look up the idempotency key in memory.
2. If missing, look up the durable idempotency index.
3. Return the existing active or rendered job when present.
4. Only create a new render when no active/rendered durable match exists and policy allows it.

This means a repeated render request after process reload can still return the existing render job.

For edit-level render requests, the service also checks the durable latest-render index for the edit job. For revision render requests, the revision idempotency key is the primary guard so a new revision render can replace the edit's latest render while duplicate revision taps still collapse to one render.

## Status And Download Reads

Render status reads now load durable state when in-memory state is missing:

- `GET /v1/render-jobs/{renderJobId}`
- `GET /v1/edit-jobs/{editJobId}/render-status`

Download URL reads only return a URL for `rendered` jobs with an `outputObjectKey`:

- `GET /v1/render-jobs/{renderJobId}/download-url`
- `GET /v1/edit-jobs/{editJobId}/download-url`

Non-rendered jobs return `render_not_ready`; failed jobs expose the failure reason through render status.

## Stale Render Handling

When status endpoints or render creation touch a durable active job, the editing service checks:

```text
now - updatedAt > policy.staleRenderTimeoutSeconds
```

If true, the job transitions to:

```text
status = failed_timeout
failureReason = failed_timeout
retentionClass = {planTier}_failed_render
```

The service writes updated durable state and a failed render log with retention metadata.

## R2 Metadata Consistency

Durable state stores the output and log object keys after render completion:

```text
edits/{editJobId}/render_jobs/{renderJobId}/final.mp4
edits/{editJobId}/render_jobs/{renderJobId}/render_log.json
```

The `render_log.json` continues to include:

- policy summary
- retention metadata
- template signature
- render cost estimate
- `revisionId` when rendering a revision
- FFmpeg summary metadata

The service does not silently invent download URLs from missing output state. Download requires a rendered durable job with an output key.

## Cloud Run Scaling Plan

Staging remains pinned conservatively:

```text
--max-instances 1
--no-cpu-throttling
```

This is still appropriate while render execution uses FastAPI background tasks. Durable state now lets status/idempotency survive process reloads, but it is not a distributed queue or lock.

Before raising `max-instances` above `1`, HoopClips should add one of:

- Cloud Tasks or Pub/Sub-backed render dispatch
- a database-backed render lease with atomic compare-and-set
- a single-worker queue consumer model

Required proof before scaling:

- duplicate render requests cannot acquire two leases
- status polling works across instances
- completed jobs are durable after redeploy
- stale jobs are reconciled by a periodic or on-read sweeper
- active-render limits are enforced against durable state

## CI And Deploy Readiness

Manual deploy currently works through local authenticated CLIs. CI needs these secrets and identities before beta release automation is reliable.

### Required CI Secrets

- `CLOUDFLARE_API_TOKEN`
- GCP workload identity or deploy service account credentials

Do not commit secret values or put them in `wrangler.jsonc` plaintext vars.

### Cloudflare Token Use

`CLOUDFLARE_API_TOKEN` is required for:

- `npx wrangler deploy --env staging`
- `npx wrangler secret put ... --env staging` during controlled rotations
- optional `npx wrangler tail` or Worker deployment inspection
- optional R2 smoke checks that fetch `render_log.json`

Recommended token permissions:

- Account: Workers Scripts Edit
- Account: Workers Tail Read, optional
- Account: R2 Read/Write, if CI verifies R2 smoke artifacts
- Account: D1 Edit or Queues Edit only if future control-plane deploys manage those bindings

### GCP Deploy Identity

The GCP deploy identity needs:

- Cloud Build submit permission
- Artifact Registry writer for `us-central1/hoopsclips`
- Cloud Run developer/admin permission for `hoopclips-editing-staging`
- Secret Manager secret accessor for deploy-time secret wiring
- Service Account User on the Cloud Run runtime service account if a custom runtime account is used

### Deploy Commands

Editing service:

```bash
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG="$GIT_SHA"
```

Control-plane Worker:

```bash
cd services/control-plane
npx wrangler deploy --env staging
```

### Rollback Commands

Cloud Run rollback:

```bash
gcloud run services update-traffic hoopclips-editing-staging \
  --project=hoopsclips-9d38f \
  --region=us-central1 \
  --to-revisions <previous-revision>=100
```

Worker rollback should use the Cloudflare dashboard deployment rollback or the matching Wrangler deployment/version workflow for the configured account.

## Tests

Backend tests added:

- durable render status survives app reload
- duplicate render idempotency survives app reload
- edit-level render status reads durable latest render state
- stale durable render transitions to `failed_timeout`
- stale failed render writes failed retention metadata

Validation commands for this branch:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service
npm --prefix services/control-plane run typecheck
cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts
```

## Live Smoke Plan

Run after deploying this branch:

```bash
PYTHONPATH=services/editing/scripts \
ios/backend/.venv/bin/python services/editing/scripts/policy_observability_smoke.py \
  --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --editing-url https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
```

Additional durable-state smoke:

1. Start a render.
2. Confirm `render_state/render_jobs/{renderJobId}.json` exists.
3. Deploy/restart the editing service.
4. Confirm `GET /v1/render-jobs/{renderJobId}` still returns status from durable state.
5. Re-send the same idempotency key and confirm the same render job is returned.

## Remaining Beta Blockers

- CI still needs `CLOUDFLARE_API_TOKEN`.
- Cloud Run render execution still uses background tasks, so keep `max-instances=1` until a queue/lease model lands.
- R2 cleanup should start with a non-destructive dry run before deleting artifacts.
- Production/staging config separation still needs a beta release audit.

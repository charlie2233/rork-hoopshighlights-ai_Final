# Phase Edit2c Canonical Cloud Editing Service

## Verdict

`ios/backend` proved the FFmpeg renderer locally, but it is not the active deployed cloud lineage. The canonical cloud path is:

```text
iOS app -> services/control-plane Worker -> services/editing Cloud Run -> R2
                           |
                           +-> services/inference Cloud Run for analysis
```

The renderer now has a canonical service home under `services/editing`. The Worker has a minimal proxy contract for the iOS-facing render endpoints while render execution stays inside the Python editing service.

## What This Branch Adds

- `services/editing`: internal Python Cloud Run service for FFmpeg render jobs.
- `services/editing/Dockerfile`: installs FFmpeg/FFprobe and copies the shared iOS backend planning/render core.
- `services/editing/cloudbuild.yaml`: deploy scaffold for `hoopclips-editing-staging`.
- `services/editing/scripts/live_render_smoke.py`: local/R2 smoke that creates a source, posts a valid `EditPlan`, renders, downloads, and probes the final MP4.
- `services/control-plane/src/editing/client.ts`: Worker-side editing-service proxy client.
- Worker env/secret declarations:
  - `EDITING_BASE_URL`
  - `EDITING_SHARED_SECRET`
- Worker routes:
  - `POST /v1/edit-jobs/{editJobId}/render`
  - `GET /v1/edit-jobs/{editJobId}/render-status`
  - `GET /v1/edit-jobs/{editJobId}/download-url`

## Current Service Boundary

The editing service accepts an already-built `EditPlan`. It does not run analysis and does not expose R2 credentials to iOS.

Supported internal endpoints:

```text
GET  /healthz
GET  /readyz
GET  /version
POST /v1/render-jobs
GET  /v1/render-jobs/{renderJobId}
GET  /v1/render-jobs/{renderJobId}/download-url
POST /v1/edit-jobs/{editJobId}/render
GET  /v1/edit-jobs/{editJobId}/render-status
GET  /v1/edit-jobs/{editJobId}/download-url
```

The `/v1/edit-jobs/...` endpoints are compatibility endpoints for the active Worker-facing contract.

## Storage Contract

Render artifacts use the stable keys:

```text
edits/{editJobId}/plan.json
edits/{editJobId}/render_jobs/{renderJobId}/final.mp4
edits/{editJobId}/render_jobs/{renderJobId}/render_log.json
```

`download-url` returns a short-lived presigned GET URL in R2 mode. Treat it as a bearer token and do not log the full URL.

## Cloud Smoke Gate

Before claiming cloud editing readiness:

1. Deploy `services/editing` with FFmpeg available.
2. Configure Cloud Run secrets:
   - `HOOPS_EDITING_SERVICE_SECRET`
   - `HOOPS_R2_ACCESS_KEY_ID`
   - `HOOPS_R2_SECRET_ACCESS_KEY`
3. Configure Cloud Run env:
   - `HOOPS_RENDER_STORAGE_PROVIDER=r2`
   - `HOOPS_R2_BUCKET`
   - `HOOPS_R2_ENDPOINT_URL`
   - `HOOPS_PUBLIC_BASE_URL`
4. Configure Worker secrets:
   - `EDITING_BASE_URL`
   - `EDITING_SHARED_SECRET`
5. Run `services/editing/scripts/live_render_smoke.py` against the deployed editing URL.
6. Run a Worker-path smoke through `/v1/edit-jobs/{editJobId}/render`.

## Known Limits

- Render jobs are still in-memory inside `services/editing`. The next reliability pass should move render state to durable storage or a callback-owned Worker state.
- `services/editing` imports the proven `ios/backend/app` planning/render modules to avoid duplicate renderer logic in this branch. A later cleanup can extract a shared Python package.
- The branch does not deploy live cloud resources from this environment because Cloudflare auth is missing and the exact editing Cloud Run service does not exist yet.
- No iOS UI should be built until the deployed Worker -> editing service -> R2 smoke is green.

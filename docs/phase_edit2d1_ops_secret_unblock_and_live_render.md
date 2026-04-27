# Phase Edit2d1 Ops Secret Unblock And Live Render

## Verdict

The canonical Cloud Run editing service is now deployed and direct Cloud Run -> R2 rendering is proven.

The remaining blocker is the active Cloudflare Worker path:

```text
active Worker -> hoopclips-editing-staging -> R2 final.mp4 -> presigned download URL
```

That path is still blocked because this machine does not have a usable Cloudflare token for Wrangler.

## GCP Ops Completed

Created or verified the required Google Secret Manager entries without printing secret values:

```text
HOOPS_EDITING_SERVICE_SECRET
HOOPS_R2_ACCESS_KEY_ID
HOOPS_R2_SECRET_ACCESS_KEY
```

`HOOPS_EDITING_SERVICE_SECRET` was generated fresh. The editing R2 secret names were populated from the existing inference R2 Secret Manager values so the editing service can access the same staging R2 account.

Granted the default Cloud Run runtime service account access to those three secrets:

```text
568888872909-compute@developer.gserviceaccount.com
roles/secretmanager.secretAccessor
```

## Cloud Run Deploy

Deployed the canonical service:

```text
service: hoopclips-editing-staging
region: us-central1
project: hoopsclips-9d38f
url: https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
revision: hoopclips-editing-staging-00001-knw
image: us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:924e02c
buildId: a649b950-7bbb-4276-af99-b35555c1fc8e
```

The Cloud Build deploy step warned that unauthenticated invoker binding failed. The binding was then applied manually:

```text
member: allUsers
role: roles/run.invoker
service: hoopclips-editing-staging
```

This is intentional for the current Worker -> Cloud Run shared-secret model. The render routes still require `x-hoops-editing-secret`.

## Health Evidence

`/readyz` passes:

```json
{
  "status": "ok",
  "service": "hoopclips-editing",
  "environment": "staging",
  "auth": "configured",
  "ffmpegAvailable": true,
  "ffprobeAvailable": true,
  "drawtextAvailable": true,
  "renderStorageProvider": "r2",
  "renderStorageReady": true,
  "sourceBucket": true,
  "outputBucket": true
}
```

`/version` passes:

```json
{
  "service": "hoopclips-editing",
  "backendModelVersion": "editing-cloud-v1",
  "gitSha": "924e02c",
  "rendererVersion": "ffmpeg-renderer-v1"
}
```

Note: `/healthz` is present in the generated OpenAPI schema, but direct Cloud Run requests to `/healthz` return a Google frontend 404. `/readyz` and `/version` reach the FastAPI app and are the reliable deploy checks for this revision.

## Direct Render Smoke Evidence

Direct Cloud Run smoke passed through:

```text
source upload to R2 source bucket
POST /v1/render-jobs
poll /v1/render-jobs/{renderJobId}
GET /v1/render-jobs/{renderJobId}/download-url
download final.mp4
ffmpeg decode
ffprobe validation
```

Smoke IDs:

```text
editJobId: edit_smoke_1777331685
renderJobId: render_cb6944d1b98a405c86ccc196777a97f9
sourceObjectKey: sources/editing-smoke-1777331684.mp4
outputObjectKey: edits/edit_smoke_1777331685/render_jobs/render_cb6944d1b98a405c86ccc196777a97f9/final.mp4
renderLogObjectKey: edits/edit_smoke_1777331685/render_jobs/render_cb6944d1b98a405c86ccc196777a97f9/render_log.json
```

Downloaded MP4 proof:

```json
{
  "duration": "14.422005",
  "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
  "size": "348089",
  "video": {
    "codec_name": "h264",
    "width": 720,
    "height": 1280,
    "pix_fmt": "yuv420p",
    "r_frame_rate": "30/1"
  },
  "audio": {
    "codec_name": "aac"
  }
}
```

R2 object HEAD proof:

```json
{
  "bucket": "hoopsclips-results-staging",
  "objects": [
    {
      "key": "edits/edit_smoke_1777331685/render_jobs/render_cb6944d1b98a405c86ccc196777a97f9/final.mp4",
      "contentLength": 348089,
      "contentType": "video/mp4"
    },
    {
      "key": "edits/edit_smoke_1777331685/render_jobs/render_cb6944d1b98a405c86ccc196777a97f9/render_log.json",
      "contentLength": 6871,
      "contentType": "application/json"
    }
  ]
}
```

## Existing Non-Canonical Service

There is another Cloud Run service:

```text
hoops-ai-editing-staging
https://hoops-ai-editing-staging-npya43jiia-uc.a.run.app
```

It appears to be the older `ios/backend` runtime or an older deploy shape. It reports FFmpeg and R2 readiness but uses a different API/env contract, has public API disabled for create-job routes, and is not the canonical `services/editing` path for this phase.

Do not point the Worker at `hoops-ai-editing-staging` for the canonical AI Edit Agent renderer.

## Remaining Blocker

Worker deploy is still blocked:

```text
CLOUDFLARE_API_TOKEN is not set
wrangler whoami -> Failed to fetch auth token / Not logged in
```

The active staging Worker also returns Cloudflare `error code: 1010` for direct unauthenticated curl probes from this environment, so a successful Worker-path render smoke must run from an allowed environment after Worker secrets are set.

## Next Commands

On a machine/session with Cloudflare auth:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane
export CLOUDFLARE_API_TOKEN="<operator-held-token>"
npx wrangler whoami

EDITING_BASE_URL="https://hoopclips-editing-staging-npya43jiia-uc.a.run.app"
printf '%s' "$EDITING_BASE_URL" | npx wrangler secret put EDITING_BASE_URL --env staging
gcloud secrets versions access latest --secret=HOOPS_EDITING_SERVICE_SECRET --project=hoopsclips-9d38f | \
  npx wrangler secret put EDITING_SHARED_SECRET --env staging

npx wrangler deploy --env staging
```

Then run Worker-path smoke using a real uploaded source key:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
PYTHONPATH=services/editing:ios/backend \
WORKER_BASE_URL="https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev" \
HOOPS_SMOKE_SOURCE_OBJECT_KEY="<existing uploads/... source object>" \
uv run --with pydantic==2.10.4 --with fastapi==0.115.6 \
  python services/editing/scripts/worker_render_smoke.py
```

## Next Gate

Do not start `phase-edit3-ai-edit-client-ui` until Worker-path smoke passes.

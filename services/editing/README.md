# HoopClips Editing Service

Canonical cloud service for HoopClips FFmpeg rendering.

The service receives a validated `EditPlan`, downloads the source video from render storage, renders a final MP4 through backend-owned FFmpeg templates, stores `final.mp4` and `render_log.json`, and returns a temporary download URL.

## Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /version`
- `POST /v1/render-jobs`
- `GET /v1/render-jobs/{renderJobId}`
- `GET /v1/render-jobs/{renderJobId}/download-url`

## Environment

- `HOOPS_ENVIRONMENT`: `local`, `staging`, or `production`
- `HOOPS_EDITING_SERVICE_SECRET`: shared secret required outside local mode
- `HOOPS_PUBLIC_BASE_URL`: base URL used for local render downloads
- `HOOPS_UPLOAD_ROOT`: local temp/source/output root
- `HOOPS_RENDER_STORAGE_PROVIDER`: `local` or `r2`
- `HOOPS_RENDER_DOWNLOAD_TTL_SECONDS`: default `900`
- `HOOPS_R2_BUCKET`
- `HOOPS_R2_ENDPOINT_URL`
- `HOOPS_R2_ACCESS_KEY_ID`
- `HOOPS_R2_SECRET_ACCESS_KEY`
- `HOOPS_R2_REGION`: default `auto`
- `HOOPS_GIT_SHA`
- `HOOPS_BACKEND_MODEL_VERSION`

## Local Smoke

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
PYTHONPATH=services/editing:ios/backend \
HOOPS_ENVIRONMENT=local \
HOOPS_RENDER_STORAGE_PROVIDER=local \
HOOPS_UPLOAD_ROOT=/tmp/hoopclips-editing-smoke \
ios/backend/.venv/bin/python -m uvicorn editing_app.main:app --host 127.0.0.1 --port 8090
```

In another terminal:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
PYTHONPATH=services/editing:ios/backend \
HOOPS_RENDER_STORAGE_PROVIDER=local \
HOOPS_UPLOAD_ROOT=/tmp/hoopclips-editing-smoke \
ios/backend/.venv/bin/python services/editing/scripts/live_render_smoke.py \
  --base-url http://127.0.0.1:8090 \
  --render-storage-provider local \
  --upload-root /tmp/hoopclips-editing-smoke
```

## Cloud Smoke

Configure the deployed Cloud Run service with R2 and `HOOPS_EDITING_SERVICE_SECRET`, then run:

```bash
PYTHONPATH=services/editing:ios/backend \
HOOPS_RENDER_STORAGE_PROVIDER=r2 \
HOOPS_EDITING_SERVICE_SECRET=... \
HOOPS_R2_BUCKET=... \
HOOPS_R2_ENDPOINT_URL=... \
HOOPS_R2_ACCESS_KEY_ID=... \
HOOPS_R2_SECRET_ACCESS_KEY=... \
ios/backend/.venv/bin/python services/editing/scripts/live_render_smoke.py \
  --base-url https://YOUR-EDITING-SERVICE \
  --render-storage-provider r2
```

Do not expose `HOOPS_EDITING_SERVICE_SECRET` or R2 credentials to iOS.

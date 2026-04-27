# Phase Edit2b Live Render Smoke

## Verdict

This branch adds the proof tooling for the cloud FFmpeg renderer path, but the live cloud render is not yet verified from this checkout.

The tracked backend in this branch is `ios/backend`, including its Cloud Run scaffold for `hoops-ai-api`. Prior staging evidence on the Phase 4h branch points to `services/control-plane` plus `services/inference` as the deployed Worker/GPU-inference lineage. Do not claim public cloud render readiness until the renderer is wired into the active deployed backend path and the live smoke below passes.

## Added proof surfaces

- `GET /readyz` reports FFmpeg, FFprobe, drawtext, upload-root, and render-storage readiness without printing secrets.
- `GET /version` reports backend and renderer version information.
- `ios/backend/scripts/live_render_smoke.py` creates or reuses a small source MP4, creates an edit job, requests render, polls render status, downloads the returned MP4, and verifies the file with FFmpeg/FFprobe.

## Local/internal smoke

Use this against a local or private internal backend with public edit APIs enabled.

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend
export HOOPS_ENVIRONMENT=local
export HOOPS_PUBLIC_API_ENABLED=true
export HOOPS_RENDER_STORAGE_PROVIDER=local
export HOOPS_UPLOAD_ROOT=/tmp/hoopclips-render-smoke
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

In another terminal:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend
python scripts/live_render_smoke.py \
  --base-url http://127.0.0.1:8080 \
  --render-storage-provider local \
  --upload-root /tmp/hoopclips-render-smoke
```

Expected proof chain:

```text
GET /readyz = ok
POST /v1/edit-jobs = editJobId
POST /v1/edit-jobs/:id/render = renderJobId
GET /v1/edit-jobs/:id/render-status = rendered
GET /v1/edit-jobs/:id/download-url = temporary URL
downloaded final.mp4 passes ffmpeg decode and ffprobe stream checks
```

## R2/deployed smoke

The deployed service must be configured with:

```text
HOOPS_PUBLIC_API_ENABLED=true
HOOPS_RENDER_STORAGE_PROVIDER=r2
HOOPS_R2_BUCKET
HOOPS_R2_ENDPOINT_URL
HOOPS_R2_ACCESS_KEY_ID
HOOPS_R2_SECRET_ACCESS_KEY
HOOPS_RENDER_DOWNLOAD_TTL_SECONDS=900
```

Then run:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend
export HOOPS_RENDER_STORAGE_PROVIDER=r2
export HOOPS_R2_BUCKET=...
export HOOPS_R2_ENDPOINT_URL=...
export HOOPS_R2_ACCESS_KEY_ID=...
export HOOPS_R2_SECRET_ACCESS_KEY=...
python scripts/live_render_smoke.py \
  --base-url https://YOUR-INTERNAL-BACKEND.example.com \
  --render-storage-provider r2
```

The script uploads a synthetic source MP4 to R2 when no `--source-object-key` is provided. If the source is pre-seeded, pass:

```bash
python scripts/live_render_smoke.py \
  --base-url https://YOUR-INTERNAL-BACKEND.example.com \
  --render-storage-provider r2 \
  --source-object-key sources/render-smoke-preseeded.mp4
```

## Pass criteria

- `readyz.status` is `ok`.
- Render status reaches `rendered`.
- Final MP4 exists at `edits/{editJobId}/render_jobs/{renderJobId}/final.mp4`.
- Render log exists at `edits/{editJobId}/render_jobs/{renderJobId}/render_log.json`.
- Download URL fetches a non-empty MP4.
- FFmpeg can decode the MP4 with no errors.
- FFprobe reports one video stream and one audio stream.

## Current blocker

This environment could query Google Cloud, but `hoops-ai-api` is not currently found in `us-central1`, Docker is not available locally, and the currently visible Cloud Run service is `hoopsclips-inference-staging`, which belongs to the separate Phase 4h inference/control-plane lineage. The live R2 cloud smoke therefore remains pending until the active deployed backend path is selected and configured.

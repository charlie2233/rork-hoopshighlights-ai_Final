# Hoops AI Cloud Analysis Backend

This is a Cloud Run-ready FastAPI service that implements the app-side cloud analysis contract used by the iOS client.

## What is implemented
- `POST /v1/analysis/jobs`
- `POST /v1/analysis/jobs/{jobId}/start`
- `GET /v1/analysis/jobs/{jobId}`
- `DELETE /v1/analysis/jobs/{jobId}`
- `PUT /v1/internal/uploads/{jobId}` for local/dev signed-upload emulation
- `POST /v1/internal/process/{jobId}` for internal task execution

## Local behavior
- The service runs on `http://127.0.0.1:8080` by default.
- The iOS app debug build now points to that same base URL by default.
- Uploads are written to `/tmp/hoops-ai` and deleted after processing completes.
- Job state and quota tracking are in-memory for now.

This means the app can talk to the backend immediately in simulator/debug mode, but job state is not durable across backend restarts. The API contract is stable, so Firestore, Cloud Storage, and Cloud Tasks can replace the in-memory/local adapters without changing the iOS client surface.

## Run locally
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

## Environment
- `HOOPS_PUBLIC_BASE_URL`: public base URL returned in upload URLs (default `http://127.0.0.1:8080`)
- `HOOPS_UPLOAD_ROOT`: temp storage root (default `/tmp/hoops-ai`)
- `HOOPS_INTERNAL_PROCESS_SECRET`: optional shared secret for `/v1/internal/process/{jobId}`
- `HOOPS_DAILY_QUOTA`: per-install rolling quota (default `3`)
- `HOOPS_MAX_DURATION_SECONDS`: max backend video duration (default `1800`)
- `HOOPS_MAX_FILE_SIZE_BYTES`: max video size for v1 (default `524288000`)
- `HOOPS_BACKEND_MODEL_VERSION`: version string exposed in diagnostics (default `cloud-v1`)
- `HOOPS_USE_GEMINI_RELABELING`: reserved flag; current scaffold keeps deterministic labels

## Processing pipeline in this scaffold
- Validates duration and file size limits.
- Uses `ffprobe` when available to verify duration.
- Uses `ffmpeg` when available to extract a mono WAV and derive an audio-energy profile.
- Builds overlapping candidate windows.
- Applies hysteresis-style segmentation.
- Produces normalized clips and deterministic action labels.
- Deletes uploaded source files after success/failure.

## Cloud migration path
To move this from local-dev scaffolding to the target Google Cloud architecture, keep the API unchanged and swap these adapters:
- `backend/app/job_store.py`: replace in-memory store with Firestore-backed state + usage counters.
- `backend/app/storage.py`: replace local filesystem writes with GCS signed URLs and object lifecycle cleanup.
- `backend/app/api.py`: replace `BackgroundTasks` dispatch with Cloud Tasks calling `/v1/internal/process/{jobId}`.
- `backend/app/pipeline.py`: replace local fallback segmentation with Video Intelligence + richer CV feature extraction.

The current code is intentionally structured so those swaps do not require changing the iOS client contract.

## Current tier behavior
- Free tier is enforced in the iOS client: videos longer than 15 minutes require Pro before analysis starts.
- The backend scaffold allows up to 30 minutes so Pro users are not blocked by the previous 10-minute limit.
- Because backend subscription validation is not wired yet, the 15-minute free-tier gate is currently a client-side product rule, not a hardened server-side entitlement check.

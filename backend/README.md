# Hoops AI Cloud Analysis Backend

This service keeps the existing iOS cloud-analysis API contract stable while swapping the backend internals by environment.

## What is implemented
- `POST /v1/analysis/jobs`
- `POST /v1/analysis/jobs/{jobId}/start`
- `GET /v1/analysis/jobs/{jobId}`
- `DELETE /v1/analysis/jobs/{jobId}`
- `POST /v1/internal/process/{jobId}` for internal task execution
- `PUT /v1/internal/uploads/{jobId}` only when local upload emulation is enabled

## Runtime modes
### Local
- Uses `InMemoryJobStore`
- Uses `LocalStorageProvider`
- Uses `InlineTaskDispatcher`
- Keeps the signed-upload emulator enabled so the iOS simulator can upload directly to `http://127.0.0.1:8080`

### Staging / Production
- Uses `FirestoreJobStore` for durable job state and rolling quota tracking
- Uses `GCSStorageProvider` for V4 signed uploads and source-object cleanup
- Uses `CloudTasksDispatcher` to enqueue `POST /v1/internal/process/{jobId}`
- Disables local upload emulation by default

The public request and response payloads stay unchanged across all modes.

## Run locally
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

## Environment
- `HOOPS_ENVIRONMENT`: `local`, `staging`, or `production` (default `local`)
- `HOOPS_PUBLIC_BASE_URL`: base URL returned in local signed-upload URLs (default `http://127.0.0.1:8080`)
- `HOOPS_CLOUD_RUN_BASE_URL`: base URL Cloud Tasks calls in managed mode
- `HOOPS_UPLOAD_ROOT`: temp storage root for local uploads and transient downloads (default `/tmp/hoops-ai`)
- `HOOPS_INTERNAL_PROCESS_SECRET`: optional shared secret for `/v1/internal/process/{jobId}`
- `HOOPS_GCP_PROJECT_ID`: Google Cloud project ID for Firestore, GCS, and Cloud Tasks
- `HOOPS_GCP_REGION`: task queue / Cloud Run region (default `us-central1`)
- `HOOPS_GCS_BUCKET`: upload bucket (default `charlie-hoops-ai-analysis-temp`)
- `HOOPS_FIRESTORE_JOBS_COLLECTION`: Firestore collection for analysis jobs (default `analysisJobs`)
- `HOOPS_FIRESTORE_USAGE_COLLECTION`: Firestore collection for usage counters (default `usageCounters`)
- `HOOPS_CLOUD_TASKS_QUEUE`: Cloud Tasks queue name (default `analysis-jobs`)
- `HOOPS_ENABLE_LOCAL_UPLOAD_EMULATION`: force-enable or disable the local upload emulator
- `HOOPS_DAILY_QUOTA`: per-install rolling quota (default `3`)
- `HOOPS_MAX_DURATION_SECONDS`: max backend video duration (default `1800`)
- `HOOPS_MAX_FILE_SIZE_BYTES`: max video size for v1 (default `524288000`)
- `HOOPS_BACKEND_MODEL_VERSION`: version string exposed in diagnostics (default `cloud-v1`)
- `HOOPS_USE_GEMINI_RELABELING`: reserved flag; current scaffold keeps deterministic labels

## Processing semantics
- The pipeline still normalizes clips the same way and preserves the current client schema.
- Managed mode downloads the source object from GCS into ephemeral local disk before analysis.
- Temporary local analysis files are deleted after each run.
- Source objects are deleted after terminal job states (`succeeded`, `failed`, `expired`).

## Deployment
`cloudbuild.yaml` deploys the service to Cloud Run and wires:
- service account
- managed environment variables
- `HOOPS_INTERNAL_PROCESS_SECRET` from Secret Manager
- local upload emulation disabled in managed mode

Before production cutover, verify:
- Firestore Native mode is enabled
- the `analysis-jobs` queue exists in `us-central1`
- the Cloud Run service account can access Firestore, Cloud Storage, and Cloud Tasks
- the GCS bucket `charlie-hoops-ai-analysis-temp` exists

## Current tier behavior
- Free tier is enforced in the iOS client: videos longer than 15 minutes require Pro before analysis starts.
- The backend allows up to 30 minutes so Pro users are not blocked by the old cap.
- Backend subscription validation is still not implemented in this pass, so the 15-minute free-tier rule remains a client-side product rule.

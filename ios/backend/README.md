# Hoops AI Cloud Analysis Backend

This service keeps the existing iOS cloud-analysis API contract stable while swapping the backend internals by environment. It is also the natural home for the next HoopClips AI Edit Agent backend work: EditContext creation, EditPlan generation, deterministic plan validation, cloud rendering jobs, and final MP4 storage.

## What is implemented
- `POST /v1/analysis/jobs`
- `POST /v1/analysis/jobs/{jobId}/start`
- `GET /v1/analysis/jobs/{jobId}`
- `DELETE /v1/analysis/jobs/{jobId}`
- `POST /v1/internal/process/{jobId}` for internal task execution
- `PUT /v1/internal/uploads/{jobId}` only when local upload emulation is enabled
- `POST /v1/edit-jobs` for local/internal EditPlan creation from analyzed clip metadata
- `GET /v1/edit-jobs/{editJobId}`
- `GET /v1/edit-jobs/{editJobId}/plan`
- `POST /v1/edit-jobs/{editJobId}/revise`

The edit-job routes are planning-only in this phase. They create and revise validated `EditPlan` JSON but do not render video yet.

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
- Keeps the public `/v1/analysis/*` routes internal-only by default until authenticated rollout is ready

The public request and response payloads stay unchanged in local mode. Managed launch mode keeps the internal processing surface available while the public analysis surface stays off.

## Run locally
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

## Optional external model integrations
The backend can now call two repo-backed adapters without changing the iOS API contract:

- `HoopCut_FH` for basketball shot detection / preprocessing
- `autohighlight` for optional post-ranking of detected clips

Those repos are not vendored into this repository. Keep them in ignored local directories and wire them in through environment variables:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend
./scripts/setup_external_backends.sh --with-venvs
```

That script clones:

- `/Users/hanfei/rork-hoopshighlights-ai_Final/backend/.external/HoopCut_FH`
- `/Users/hanfei/rork-hoopshighlights-ai_Final/backend/.external/autohighlight`

Then you can selectively install dependencies into isolated virtualenvs:

```bash
./scripts/setup_external_backends.sh --install-hoopcut
```

`autohighlight` is optional and intentionally not auto-installed by default because its TensorFlow 1.x stack is legacy and may require a dedicated Python environment.

## Environment
- `HOOPS_ENVIRONMENT`: `local`, `staging`, or `production` (default `local`)
- `HOOPS_PUBLIC_BASE_URL`: base URL returned in local signed-upload URLs (default `http://127.0.0.1:8080`)
- `HOOPS_CLOUD_RUN_BASE_URL`: base URL Cloud Tasks calls in managed mode
- `HOOPS_UPLOAD_ROOT`: temp storage root for local uploads and transient downloads (default `/tmp/hoops-ai`)
- `HOOPS_INTERNAL_PROCESS_SECRET`: required shared secret for `/v1/internal/process/{jobId}` outside local mode
- `HOOPS_PUBLIC_API_ENABLED`: enables public `/v1/analysis/*` routes (default `true` in local, `false` elsewhere)
- `HOOPS_GCP_PROJECT_ID`: Google Cloud project ID for Firestore, GCS, and Cloud Tasks
- `HOOPS_GCP_REGION`: task queue / Cloud Run region (default `us-central1`)
- `HOOPS_GCS_BUCKET`: upload bucket (default `charlie-hoops-ai-analysis-temp`)
- `HOOPS_FIRESTORE_JOBS_COLLECTION`: Firestore collection for analysis jobs (default `analysisJobs`)
- `HOOPS_FIRESTORE_USAGE_COLLECTION`: Firestore collection for usage counters (default `usageCounters`)
- `HOOPS_CLOUD_TASKS_QUEUE`: Cloud Tasks queue name (default `analysis-jobs`)
- `HOOPS_ENABLE_LOCAL_UPLOAD_EMULATION`: force-enable or disable the local upload emulator
- `HOOPS_EXTERNAL_REPO_ROOT`: default root for ignored external repo clones (default `ios/backend/.external`)
- `HOOPS_DETECTION_PROVIDER`: `heuristic`, `hybrid`, or `hoopcut` (default `hybrid`)
- `HOOPS_POST_RANKING_PROVIDER`: `native` or `autohighlight` (default `native`)
- `HOOPS_HOOPCUT_REPO_PATH`: explicit HoopCut checkout path
- `HOOPS_HOOPCUT_PYTHON`: Python executable for the HoopCut virtualenv
- `HOOPS_AUTOHIGHLIGHT_REPO_PATH`: explicit autohighlight checkout path
- `HOOPS_AUTOHIGHLIGHT_PYTHON`: Python executable for the autohighlight virtualenv
- `HOOPS_DAILY_QUOTA`: per-install rolling quota (default `5`)
- `HOOPS_MAX_DURATION_SECONDS`: max backend video duration (default `1800`)
- `HOOPS_MAX_FILE_SIZE_BYTES`: max video size for v1 (default `524288000`)
- `HOOPS_BACKEND_MODEL_VERSION`: version string exposed in diagnostics (default `cloud-v1`)
- `HOOPS_USE_GEMINI_RELABELING`: reserved flag; current scaffold keeps deterministic labels

## Processing semantics
- The pipeline still normalizes clips the same way and preserves the current client schema.
- `hybrid` detection will try the external HoopCut adapter first and fall back to the built-in heuristic pipeline if the repo or its dependencies are unavailable.
- `autohighlight` post-ranking is optional and only runs when the repo path and dedicated Python runtime are configured.
- Managed mode downloads the source object from GCS into ephemeral local disk before analysis.
- Temporary local analysis files are deleted after each run.
- Source objects are deleted after terminal job states (`succeeded`, `failed`, `expired`).

## Deployment
`cloudbuild.yaml` deploys the service to Cloud Run and wires:
- service account
- managed environment variables
- `HOOPS_INTERNAL_PROCESS_SECRET` from Secret Manager
- public API disabled in managed mode by default
- local upload emulation disabled in managed mode

Before production cutover, verify:
- Firestore Native mode is enabled
- the `analysis-jobs` queue exists in `us-central1`
- the Cloud Run service account can access Firestore, Cloud Storage, and Cloud Tasks
- the GCS bucket `charlie-hoops-ai-analysis-temp` exists

## Launch posture
- Public App Store launch should treat this backend as internal-only until cloud cutover gates clear.
- Hoopclips target architecture is cloud analysis, cloud edit planning, and cloud rendering with iOS as the control surface.
- The current iOS on-device path is a temporary launch-safe fallback, not the production editing architecture.
- `installId` is not a sufficient public auth boundary. Do not re-enable `/v1/analysis/*` in managed mode until there is a real identity and authorization model.
- Do not add public `/v1/edit-jobs/*` or render-job access until authn/authz, storage, observability, render reliability, and Phase 4h gates are ready.

## AI Edit Agent planning layer

Implemented planning routes:

- `POST /v1/edit-jobs`
- `GET /v1/edit-jobs/{editJobId}`
- `GET /v1/edit-jobs/{editJobId}/plan`
- `POST /v1/edit-jobs/{editJobId}/revise`

Planned render routes:

- `POST /v1/edit-jobs/{editJobId}/render`
- `GET /v1/edit-jobs/{editJobId}/render-status`
- `GET /v1/edit-jobs/{editJobId}/download-url`

The planning layer outputs strict `EditPlan` JSON from compact analyzed clip metadata and validates the plan deterministically before render. FFmpeg should be the first production renderer; Remotion, Canva, Cloudinary, and Revideo are template/asset/preview tools, not iOS render engines.

## Current tier behavior
- Free tier is enforced in the iOS client: videos longer than 15 minutes require Pro before analysis starts.
- The backend allows up to 30 minutes so Pro users are not blocked by the old cap.
- Backend subscription validation is still not implemented in this pass, so the 15-minute free-tier rule remains a client-side product rule.

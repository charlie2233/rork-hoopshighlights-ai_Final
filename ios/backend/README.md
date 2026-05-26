# Hoops AI Cloud Analysis Backend

This service keeps the existing iOS cloud-analysis API contract stable while swapping the backend internals by environment. It is also the natural home for the next HoopClips AI Edit Agent backend work: EditContext creation, EditPlan generation, deterministic plan validation, cloud rendering jobs, and final MP4 storage.

## What is implemented
- `POST /v1/analysis/jobs`
- `POST /v1/analysis/jobs/{jobId}/start`
- `GET /v1/analysis/jobs/{jobId}`
- `DELETE /v1/analysis/jobs/{jobId}`
- `POST /v1/internal/process/{jobId}` for internal task execution
- `GET /readyz` for FFmpeg/render-storage readiness
- `GET /version` for backend and renderer version diagnostics
- `PUT /v1/internal/uploads/{jobId}` only when local upload emulation is enabled
- `POST /v1/edit-jobs` for local/internal EditPlan creation from analyzed clip metadata
- `GET /v1/edit-jobs/{editJobId}`
- `GET /v1/edit-jobs/{editJobId}/plan`
- `POST /v1/edit-jobs/{editJobId}/revise`
- `POST /v1/edit-jobs/{editJobId}/render`
- `GET /v1/edit-jobs/{editJobId}/render-status`
- `GET /v1/edit-jobs/{editJobId}/download-url`

The edit-job routes create and revise validated `EditPlan` JSON, then render a validated plan into an MP4 with backend-owned FFmpeg templates. The current render state is local/in-process and internal-only; durable production queue/state work is still required before public cloud cutover.

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
- `HOOPS_DAILY_QUOTA`: per-install rolling quota (default `3`)
- `HOOPS_MAX_DURATION_SECONDS`: max backend video duration (default `1800`)
- `HOOPS_MAX_FILE_SIZE_BYTES`: max video size for v1 (default `524288000`)
- `HOOPS_BACKEND_MODEL_VERSION`: version string exposed in diagnostics (default `cloud-v1`)
- `HOOPS_USE_GEMINI_RELABELING`: reserved flag; current scaffold keeps deterministic labels
- `HOOPS_TEAM_QUICK_SCAN_ENABLED`: enables the cloud GPT frame quick scan for jersey-color team detection and per-clip team attribution. If unset, it follows `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED` / `HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED`.
- `HOOPS_OPENAI_API_KEY`: required only when GPT team quick scan is enabled. Do not print or log this value.
- `HOOPS_TEAM_QUICK_SCAN_MODEL`: vision-capable model for team quick scan (default follows `HOOPS_AI_CLIP_GPT_MODEL`, then `gpt-4.1`)
- `HOOPS_TEAM_QUICK_SCAN_VIDEO_FRAME_COUNT`: whole-video frame samples for team color detection, clamped to `2...16` (default `8`)
- `HOOPS_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP`: per-candidate clip frames for team ownership, clamped to `1...4` (default `3`)
- `HOOPS_TEAM_QUICK_SCAN_MIN_TEAM_CONFIDENCE`: minimum confidence to expose a detected team option (default `0.55`). Clip filtering still treats attribution below `0.85` as uncertain.
- `HOOPS_RENDER_STORAGE_PROVIDER`: `local` or `r2` (default `local`)
- `HOOPS_RENDER_DOWNLOAD_TTL_SECONDS`: signed/local render download URL TTL (default `900`)
- `HOOPS_MAX_RENDER_COMPLEXITY_UNITS`: max estimated render complexity before rejecting render (default `600`)
- `HOOPS_FFMPEG_BINARY`: FFmpeg executable path (default `ffmpeg`)
- `HOOPS_FFPROBE_BINARY`: ffprobe executable path (default `ffprobe`)
- `HOOPS_R2_BUCKET`: R2 bucket for render outputs when render storage provider is `r2`
- `HOOPS_R2_ENDPOINT_URL`: R2 S3-compatible endpoint URL
- `HOOPS_R2_ACCESS_KEY_ID`: R2 access key ID
- `HOOPS_R2_SECRET_ACCESS_KEY`: R2 secret access key
- `HOOPS_R2_REGION`: R2 region (default `auto`)

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

## Live render smoke

`scripts/live_render_smoke.py` is the canonical Phase Edit2b smoke helper. It checks `/readyz`, creates or reuses a small source MP4, creates an edit job, starts render, polls render status, downloads the final MP4, and verifies playback with FFmpeg/FFprobe.

Local/internal smoke:

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

For R2/deployed smoke, configure `HOOPS_RENDER_STORAGE_PROVIDER=r2` and the `HOOPS_R2_*` variables locally before running the same script against the internal backend URL. The script can upload a synthetic source MP4 to R2 when no `--source-object-key` is provided. Keep returned presigned URLs out of logs and tickets; treat them as temporary bearer tokens.

## Launch posture
- Public App Store launch should treat this backend as internal-only until cloud cutover gates clear.
- Hoopclips target architecture is cloud analysis, cloud edit planning, and cloud rendering with iOS as the control surface.
- The current iOS on-device path is a temporary launch-safe fallback, not the production editing architecture.
- `installId` is not a sufficient public auth boundary. Do not re-enable `/v1/analysis/*` in managed mode until there is a real identity and authorization model.
- Do not add public `/v1/edit-jobs/*` or render-job access until authn/authz, storage, observability, render reliability, and Phase 4h gates are ready.

## AI Edit Agent planning and render layer

Implemented planning routes:

- `POST /v1/edit-jobs`
- `GET /v1/edit-jobs/{editJobId}`
- `GET /v1/edit-jobs/{editJobId}/plan`
- `POST /v1/edit-jobs/{editJobId}/revise`

Implemented render routes:

- `POST /v1/edit-jobs/{editJobId}/render`
- `GET /v1/edit-jobs/{editJobId}/render-status`
- `GET /v1/edit-jobs/{editJobId}/download-url`

The planning layer outputs strict `EditPlan` JSON from compact analyzed clip metadata and validates the plan deterministically before render. The render layer converts the structured plan into backend-owned FFmpeg command templates; the plan and LLM never carry raw FFmpeg commands.

Current renderer support:

- trim selected source ranges
- split slow-motion ranges
- concatenate normalized clips
- crop to `9:16` or `16:9`
- add caption/watermark overlays when FFmpeg supports `drawtext`, with safe box overlays as a fallback
- add the free-user Hoopclips outro
- mix bundled CC0 music with game audio when a mapped music asset exists
- encode final MP4
- write `plan.json`, `render_log.json`, and `final.mp4`
- return a local or R2 presigned-style download URL

Current render output keys:

- `edits/{editJobId}/plan.json`
- `edits/{editJobId}/render_jobs/{renderJobId}/render_log.json`
- `edits/{editJobId}/render_jobs/{renderJobId}/final.mp4`

Remaining before public cloud cutover:

- durable render job store
- real queue-backed render worker
- production authz beyond `installId`
- production observability and trace propagation
- production R2 credentials/environment validation
- renderer retry/timeout policy

## Current tier behavior
- Free tier is enforced in the iOS client: videos longer than 15 minutes require Pro before analysis starts.
- The backend allows up to 30 minutes so Pro users are not blocked by the old cap.
- Backend subscription validation is still not implemented in this pass, so the 15-minute free-tier rule remains a client-side product rule.

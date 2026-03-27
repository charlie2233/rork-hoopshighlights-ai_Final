# Cloudflare Environment Setup

## Control Plane

- `HOOPS_API_BASE_URL`
- `HOOPS_R2_BUCKET_UPLOADS`
- `HOOPS_R2_BUCKET_RESULTS`
- `HOOPS_QUEUE_ANALYSIS`
- `HOOPS_DO_NAMESPACE_JOBS`
- `HOOPS_D1_DATABASE`
- `HOOPS_SIGNED_UPLOAD_TTL_SECONDS`
- `HOOPS_JOB_TTL_SECONDS`
- `HOOPS_DEFAULT_POLL_AFTER_SECONDS`
- `HOOPS_MAX_FILE_SIZE_BYTES`
- `HOOPS_MAX_DURATION_SECONDS`
- `HOOPS_INFERENCE_BASE_URL`
- `HOOPS_INFERENCE_SHARED_SECRET`

## Local Dev

- Use a local Worker/dev emulator for the API contract.
- Keep queue dispatch inline in local mode.
- Keep source/result storage on local disk only for dev convenience.
- Do not require localhost assumptions in the production path.

## Inference Service

- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT`
- `CALLBACK_URL`
- `CALLBACK_SHARED_SECRET`
- `FFMPEG_PATH`
- `MODEL_VERSION`
- `PIPELINE_VERSION`

## Notes

- Durable Objects own per-job state.
- D1 is only the secondary index.
- R2 is the blob store for uploads, manifests, and artifacts.


# HoopsClips Inference Service

Standalone Python inference service for the production cloud path.

## Role
- Accepts inference jobs from the control plane.
- Downloads source videos from R2 by object key, or from a direct signed URL for local compatibility.
- Runs FFmpeg-backed source preparation before feature extraction.
- Proposes candidate segments.
- Runs action recognition with a VideoMAE baseline and an X-CLIP comparison path.
- Emits canonical basketball labels with per-clip top-k scores, while preserving the current app-facing clip labels for compatibility.
- Infers event metadata and reranks clips.
- Writes a normalized result manifest and calls back to the Cloudflare control plane.

## API
- `POST /v1/analyze`
- `POST /v1/inference/run` - compatibility alias for older callers
- `GET /healthz`
- `GET /readyz`
- `GET /version`

### Analyze request
The preferred production request body is:

```json
{
  "jobId": "job_123",
  "requestId": "req_123",
  "sourceObjectKey": "uploads/job_123/source.mp4",
  "callbackUrl": "https://control-plane.example.com/internal/inference/callback",
  "modelVersion": "videomae:MCG-NJU/videomae-base-finetuned-kinetics"
}
```

Optional compatibility fields:
- `sourceUrl`
- `callbackSecret`
- `resultObjectKey`
- `installId`
- `appVersion`
- `analysisVersion`
- `requestedModel`
- `uploadTraceId`
- `inferenceAttemptId`
- `traceId`

## Local run
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

## Docker
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference
docker build -t hoops-inference .
docker run --rm -p 8080:8080 \
  --env-file .env \
  hoops-inference
```

## Endpoints
- `GET /healthz`
- `GET /readyz`
- `GET /version`
- `POST /v1/analyze`
- `POST /v1/inference/run`

## Environment
All settings use the `HOOPS_INFERENCE_` prefix.

Required for the R2 happy path:
- `HOOPS_INFERENCE_R2_BUCKET_NAME`
- `HOOPS_INFERENCE_R2_ENDPOINT_URL`
- `HOOPS_INFERENCE_R2_ACCESS_KEY_ID`
- `HOOPS_INFERENCE_R2_SECRET_ACCESS_KEY`

Callback authentication:
- `HOOPS_INFERENCE_CALLBACK_SECRET`

Service and model config:
- `HOOPS_INFERENCE_SERVICE_NAME`
- `HOOPS_INFERENCE_ENVIRONMENT`
- `HOOPS_INFERENCE_VERSION`
- `HOOPS_INFERENCE_DEFAULT_MODEL`
- `HOOPS_INFERENCE_MODEL_NAME_VIDEOMAE`
- `HOOPS_INFERENCE_MODEL_NAME_XCLIP`
- `HOOPS_INFERENCE_TEMP_DIR`
- `HOOPS_INFERENCE_CALLBACK_TIMEOUT_SECONDS`
- `HOOPS_INFERENCE_HTTP_TIMEOUT_SECONDS`
- `HOOPS_INFERENCE_MAX_CANDIDATES`
- `HOOPS_INFERENCE_RESULT_SCHEMA_VERSION`
- `HOOPS_INFERENCE_HEURISTIC_WINDOW_SECONDS`
- `HOOPS_INFERENCE_HEURISTIC_STRIDE_SECONDS`
- `HOOPS_INFERENCE_FFMPEG_ENABLE_TRANSCODE`
- `HOOPS_INFERENCE_FFMPEG_VIDEO_PRESET`
- `HOOPS_INFERENCE_FFMPEG_VIDEO_CRF`
- `HOOPS_INFERENCE_FFMPEG_MAX_WIDTH`

## Implementation notes
- The service accepts `sourceObjectKey` as the primary production input and falls back to `sourceUrl` for compatibility.
- If R2 is configured, the service downloads the source video using the bucket-scoped R2 credentials.
- The pipeline attempts a small FFmpeg normalization pass before feature extraction; if that fails, it falls back to the downloaded source file.
- The callback payload mirrors the current control-plane schema, including `requestId`, `modelVersion`, `schemaVersion`, `confidence`, `resultConfidence`, `failureReason`, and `results`.
- The callback/result payload also carries `uploadTraceId` and `inferenceAttemptId` so staging traces can be correlated end to end.
- The result manifest remains the canonical artifact written by the service.

## Portable deployment
The Docker image is portable enough to run on a VM, container service, or Hugging Face-hosted container runtime as long as the following are present:
- `ffmpeg`
- `ffprobe`
- Python 3.11+
- the `HOOPS_INFERENCE_*` environment variables above

## Runtime constraints
- VideoMAE and X-CLIP weights are loaded lazily from Hugging Face on first request; cold starts will be slower than steady-state requests.
- The service defaults to CPU if no CUDA device is available, but the first production deployment should use a GPU-backed container for acceptable latency.
- The current baseline keeps candidate proposal heuristic-driven; the learned models only classify and relabel candidate windows.
- The canonical label vocabulary is intentionally small: `dunk`, `layup`, `jumper`, `block`, `steal`, `fast break`, and `miss`.

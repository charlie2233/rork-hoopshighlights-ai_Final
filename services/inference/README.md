# HoopsClips Inference Service

Standalone Python inference service for the production cloud path.

## Role
- Downloads source videos from R2-signed URLs or scoped object URLs.
- Runs FFmpeg-backed feature extraction.
- Proposes candidate segments.
- Runs action recognition with a VideoMAE baseline and an X-CLIP comparison path.
- Infers event metadata and reranks clips.
- Writes a normalized result manifest and calls back to the Cloudflare control plane.

## Local run
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference
uv venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

## Docker
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference
docker build -t hoops-inference .
docker run --rm -p 8080:8080 \
  -e HOOPS_INFERENCE_ENVIRONMENT=local \
  -e HOOPS_INFERENCE_DEFAULT_MODEL=videomae \
  hoops-inference
```

## Endpoints
- `GET /healthz`
- `GET /readyz`
- `POST /v1/inference/run`

## Request shape
The inference service accepts a job request with:
- `jobId`
- `sourceUrl`
- `callbackUrl`
- `callbackSecret`
- optional request metadata such as `installId`, `appVersion`, `analysisVersion`, and `requestedModel`

## Environment
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

## Implementation notes
- The recognizers are lazy-loaded so the package stays importable even when weights are missing locally.
- If VideoMAE or X-CLIP cannot be loaded, the pipeline falls back to heuristic outputs and marks the manifest with a failure reason.
- The result manifest is the canonical artifact written by the service; the callback payload mirrors the manifest fields that the control plane needs.

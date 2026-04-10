# HoopsClips Inference Service

Standalone Python inference service for the production cloud path.

## Role
- Accepts inference jobs from the control plane.
- Downloads source videos from R2 by object key, or from a direct signed URL for local compatibility.
- Runs FFmpeg-backed source preparation before feature extraction.
- Proposes candidate segments.
- Runs action recognition with a VideoMAE baseline and an X-CLIP comparison path.
- Derives structured basketball signals from ball / rim / player perception before final label mapping.
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

## Structured basketball signals
- The live path keeps the public callback contract stable.
- Internally, each candidate window now generates lightweight perception outputs for `basketball`, `rim`, and `player` tracks.
- The live decision stack resolves `eventFamily -> outcome -> shotSubtype` before deriving the flat display label.
- VideoMAE and X-CLIP stay in the loop as auxiliary signals; they are no longer the only source of basketball semantics.
- A Qwen-based teacher labeler exists for offline audits and pseudo-label generation, but it is disabled in the live path by default.

## Runtime calibration
- The runtime labeler now loads a held-out gold calibration artifact from `services/inference/evals/runtime_calibration.json` when present.
- Calibration is applied separately to `eventFamily`, `outcome`, and `shotSubtype` probabilities before uncertainty gating and flat-label derivation.
- Teacher outputs remain training-only; the runtime calibration artifact is built from human-verified gold rows and runtime predictions only.

To regenerate the checked-in calibration artifact:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
python3 services/inference/scripts/build_runtime_calibration.py \
  --output services/inference/evals/runtime_calibration.json
```

The script also writes `services/inference/evals/runtime_calibration_report.md` for a quick holdout summary.

## Local run
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

## Runtime training export
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
python3 services/inference/scripts/build_runtime_training_data.py \
  --output-dir services/inference/datasets/runtime_training
```

The export writes a split manifest, per-split record dumps, and JSON feature matrices for the lightweight runtime labeler.

## Runtime fusion model
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
python3 services/inference/scripts/train_runtime_model.py \
  --dataset-dir services/inference/datasets/runtime_training \
  --output services/inference/models/runtime_fusion_v1.json \
  --report-output services/inference/evals/runtime_fusion_v1_report.md
```

## VideoMAE LoRA / rsLoRA
The lightweight encoder-adaptation path lives in [`docs/videomae_lora.md`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/docs/videomae_lora.md).
It trains a frozen baseline and an rsLoRA-adapted VideoMAE backbone side by side, then exports adapted logits for downstream fusion.
The LoRA-ready split export is generated alongside `runtime_training/` as `runtime_training/videomae_lora_v1/`.
The staging/runtime bundle lives at `services/inference/models/videomae_lora_v1/runtime_bundle.json`.

Runtime model rollout is controlled with:

- `HOOPS_INFERENCE_RUNTIME_MODEL_MODE=off|shadow|primary`
- `HOOPS_INFERENCE_RUNTIME_MODEL_BUNDLE_PATH=/absolute/path/to/runtime_fusion_v1.json`
- `HOOPS_INFERENCE_VIDEOMAE_LORA_MODE=off|shadow|primary`
- `HOOPS_INFERENCE_VIDEOMAE_LORA_BUNDLE_PATH=/absolute/path/to/videomae_lora_v1/runtime_bundle.json`

Use `shadow` on staging first to keep the current live labels while capturing runtime-fusion metadata in the result manifest. Promote to `primary` only after the mixed-batch shadow report shows better flat-label spread and lower miss-vs-made confusion. For LoRA/encoder adaptation, compare the candidate batch against the phase3d baseline with `--baseline-results` in [`docs/shadow_eval_reporting.md`](/Users/hanfei/rork-hoopshighlights-ai_Final/docs/shadow_eval_reporting.md).

## Docker
```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference
docker build -t hoops-inference .
docker run --rm -p 8080:8080 \
  --env-file .env \
  hoops-inference
```

## Staging deploy
The repository now includes a Cloud Build recipe for a Cloud Run staging deploy. It keeps the service portable while making the staging cutover reproducible.

Required secret names:
- `HOOPS_INFERENCE_CALLBACK_SECRET`
- `HOOPS_INFERENCE_INGRESS_SECRET`
- `HOOPS_INFERENCE_R2_ACCESS_KEY_ID`
- `HOOPS_INFERENCE_R2_SECRET_ACCESS_KEY`

Required non-secret staging values:
- `HOOPS_INFERENCE_SERVICE_NAME=hoopsclips-inference-staging`
- `HOOPS_INFERENCE_ENVIRONMENT=staging`
- `HOOPS_INFERENCE_VERSION=phase2b-live-inference-cutover`
- `HOOPS_INFERENCE_R2_BUCKET_NAME=hoopsclips-uploads-staging`
- `HOOPS_INFERENCE_R2_ENDPOINT_URL=https://78fb4442e6e37b2c46d7e539c6e79172.r2.cloudflarestorage.com`
- `HOOPS_INFERENCE_R2_REGION_NAME=auto`

Example deploy command:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/inference
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=_SERVICE_NAME=hoopsclips-inference-staging,_REGION=us-central1,_ARTIFACT_REPO=hoopsclips,_ENVIRONMENT=staging,_VERSION=phase2b-live-inference-cutover,_R2_BUCKET_NAME=hoopsclips-uploads-staging,_R2_ENDPOINT_URL=https://78fb4442e6e37b2c46d7e539c6e79172.r2.cloudflarestorage.com,_R2_REGION_NAME=auto \
  .
```

The Cloud Build recipe now tags the pushed image with `$BUILD_ID`, so the same command works for manual `gcloud builds submit` runs as well as trigger-driven deploys.
The checked-in [`services/inference/.gcloudignore`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/.gcloudignore) intentionally excludes `.venv/`, local tests, and docs from the upload context so manual staging deploys do not waste time archiving local development artifacts.
The deploy step intentionally does not override the Cloud Run service account; staging keeps the service account already attached to `hoopsclips-inference-staging` unless you choose to rotate it explicitly.

After deploy, capture the Cloud Run URL and hand it to the control plane as `INFERENCE_BASE_URL` in the staging environment.
For the phase3e basketball-specific shadow rollout, configure:

```bash
HOOPS_INFERENCE_RUNTIME_MODEL_MODE=off
HOOPS_INFERENCE_TEMPORAL_ENCODER_MODE=shadow
HOOPS_INFERENCE_TEMPORAL_ENCODER_BUNDLE_PATH=/app/services/inference/models/temporal_encoder_v1.json
HOOPS_INFERENCE_DISTILLED_CLIP_ENCODER_MODE=off
HOOPS_INFERENCE_DISTILLED_CLIP_ENCODER_BUNDLE_PATH=/app/services/inference/models/distilled_clip_encoder_v1.json
HOOPS_INFERENCE_VIDEOMAE_LORA_MODE=off
HOOPS_INFERENCE_VIDEOMAE_LORA_BUNDLE_PATH=/app/services/inference/models/videomae_lora_v1/runtime_bundle.json
```

The branch also includes an offline candidate trainer for the two basketball-specific runtime heads:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final \
services/inference/.venv/bin/python \
  services/inference/scripts/train_basketball_runtime_candidates.py \
  --output-dir /tmp/phase3e-candidates \
  --write-models \
  --temporal-epochs 60
```

That command exports:

- `services/inference/models/temporal_encoder_v1.json`
- `services/inference/models/distilled_clip_encoder_v1.json`
- `/tmp/phase3e-candidates/comparison_report.md`

The current offline winner is `temporalEncoder`, so staging shadow should use `runtimeFusionTemporalShadow` as the primary comparison namespace and leave the distilled encoder disabled unless you explicitly want a side-by-side shadow pass.

## Local tunnel path
If you need to validate the callback path before a cloud deploy is available, use a named Cloudflare Tunnel or another durable staging hostname. Do not use `cloudflared tunnel --url`; that quick tunnel is ephemeral and should only appear in historical rollout reports.

Use the helper doc and config template in [`docs/cloudflare_tunnel_staging.md`](/Users/hanfei/rork-hoopshighlights-ai_Final/docs/cloudflare_tunnel_staging.md). The companion script in [`services/inference/scripts/run_named_tunnel.sh`](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/scripts/run_named_tunnel.sh) starts the local origin and the named tunnel together.

Then set `INFERENCE_BASE_URL` to the durable staging hostname in the staging control-plane environment and confirm `/readyz` reports `callback`, `ingress`, and `r2` as `configured` before starting a live job.

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
- `HOOPS_INFERENCE_INGRESS_SECRET`

Service and model config:
- `HOOPS_INFERENCE_SERVICE_NAME`
- `HOOPS_INFERENCE_ENVIRONMENT`
- `HOOPS_INFERENCE_VERSION`
- `HOOPS_INFERENCE_DEFAULT_MODEL`
- `HOOPS_INFERENCE_MODEL_NAME_VIDEOMAE`
- `HOOPS_INFERENCE_MODEL_NAME_XCLIP`
- `HOOPS_INFERENCE_TEACHER_MODEL_NAME`
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
- `HOOPS_INFERENCE_PERCEPTION_SAMPLE_FRAMES`
- `HOOPS_INFERENCE_PERCEPTION_OVERLAY_FRAME_LIMIT`
- `HOOPS_INFERENCE_TEACHER_LABELING_ENABLED`
- `HOOPS_INFERENCE_TEACHER_FRAME_COUNT`
- `HOOPS_INFERENCE_RUNTIME_MODEL_MODE`
- `HOOPS_INFERENCE_RUNTIME_MODEL_BUNDLE_PATH`
- `HOOPS_INFERENCE_TEMPORAL_ENCODER_MODE`
- `HOOPS_INFERENCE_TEMPORAL_ENCODER_BUNDLE_PATH`
- `HOOPS_INFERENCE_DISTILLED_CLIP_ENCODER_MODE`
- `HOOPS_INFERENCE_DISTILLED_CLIP_ENCODER_BUNDLE_PATH`
- `HOOPS_INFERENCE_VIDEOMAE_LORA_MODE`
- `HOOPS_INFERENCE_VIDEOMAE_LORA_BUNDLE_PATH`

## Implementation notes
- The service accepts `sourceObjectKey` as the primary production input and falls back to `sourceUrl` for compatibility.
- If R2 is configured, the service downloads the source video using the bucket-scoped R2 credentials.
- The pipeline attempts a small FFmpeg normalization pass before feature extraction; if that fails, it falls back to the downloaded source file.
- The callback payload mirrors the current control-plane schema, including `requestId`, `modelVersion`, `schemaVersion`, `confidence`, `resultConfidence`, `failureReason`, and `results`.
- The callback/result payload also carries `uploadTraceId` and `inferenceAttemptId` so staging traces can be correlated end to end.
- The result manifest remains the canonical artifact written by the service.
- Perception overlays are exported as image artifacts for a few sampled frames when OpenCV is available.

## Shadow eval
Use [`docs/shadow_eval_reporting.md`](/Users/hanfei/rork-hoopshighlights-ai_Final/docs/shadow_eval_reporting.md) when you need to summarize a live staging batch or local mixed batch without touching the runtime contract. The shadow report records flat labels, hierarchical labels, uncertainty, miss-vs-made confusion, mixed-batch spread, and optional baseline-vs-candidate deltas for phase3d comparison.

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

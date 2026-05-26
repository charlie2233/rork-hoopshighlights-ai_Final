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
- `HOOPS_R2_BUCKET`: legacy single-bucket fallback
- `HOOPS_R2_SOURCE_BUCKET`: source-video bucket, usually `hoopsclips-uploads-staging`
- `HOOPS_R2_OUTPUT_BUCKET`: render-output bucket, usually `hoopsclips-results-staging`
- `HOOPS_R2_ENDPOINT_URL`
- `HOOPS_R2_ACCESS_KEY_ID`
- `HOOPS_R2_SECRET_ACCESS_KEY`
- `HOOPS_R2_REGION`: default `auto`
- `HOOPS_GIT_SHA`
- `HOOPS_BACKEND_MODEL_VERSION`
- `HOOPS_AI_EDIT_ENABLED`: kill switch for AI Edit planning, default `true`
- `HOOPS_AI_EDIT_LIVE_RENDER_ENABLED`: kill switch for live render enqueue, default `true`
- `HOOPS_AI_EDIT_REVISION_ENABLED`: kill switch for AI Edit revisions, default `true`
- `HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED`: kill switch for template-backed planning, default `true`
- `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED`: kill switch for GPT-led highlight editing, default `false`
- `HOOPS_AI_CLIP_GPT_PLAN_EDIT_ENABLED`: allows GPT `planEdit` ordering/caption/slow-motion directives to affect EditPlan inputs, default `false`
- `HOOPS_AI_CLIP_GPT_REVISION_ENABLED`: launch switch for GPT-produced `EditPlanPatch` revision flows, default `false`
- `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP`: shared keyframe cap per clip, clamped to `3...10`; quality-beta default is `10` for stronger shot-arc and rim-entry path context
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE`: Free candidate cap, clamped to `1...8`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO`: Pro/internal candidate cap, clamped to `20...30`; quality-beta default is `30`
- `HOOPS_GPT_HIGHLIGHT_RERANKER_ENABLED`: kill switch for GPT highlight reranking, default `false`
- `HOOPS_OPENAI_API_KEY`: OpenAI key required only when GPT highlight reranking is enabled
- `HOOPS_GPT_HIGHLIGHT_RERANK_MODEL`: vision-capable reranker model, default `gpt-4.1` for quality-beta editing; set `HOOPS_AI_CLIP_GPT_MODEL` to override
- `HOOPS_GPT_HIGHLIGHT_RERANK_FREE_MAX_CLIPS`: Free cap, clamped to `1...8`
- `HOOPS_GPT_HIGHLIGHT_RERANK_FREE_FRAMES_PER_CLIP`: Free frames per clip, clamped to `3...10`; quality-beta default is `10`
- `HOOPS_GPT_HIGHLIGHT_RERANK_PAID_MAX_CLIPS`: Pro/internal cap, clamped to `20...30`; quality-beta default is `30`
- `HOOPS_GPT_HIGHLIGHT_RERANK_PAID_FRAMES_PER_CLIP`: Pro/internal frames per clip, clamped to `5...10`; quality-beta default is `10`
- `HOOPS_GPT_HIGHLIGHT_RERANK_TIMEOUT_SECONDS`: OpenAI request timeout, clamped to `1...60`
- `HOOPS_GPT_HIGHLIGHT_RERANK_MAX_OUTPUT_TOKENS`: Structured-output budget, clamped to `256...6000`; quality-beta default is `3500`
- `HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH`: sampled keyframe width, clamped to `256...1280`; quality-beta default is `1024`
- `HOOPS_GPT_HIGHLIGHT_RERANK_JPEG_QUALITY`: FFmpeg JPEG quality, clamped to `2...12`; quality-beta default is `4`
- `HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES`: per-frame payload cap, clamped to `40000...1000000`; quality-beta default is `750000`
- `HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL`: OpenAI image detail, one of `low`, `high`, `original`, or `auto`; defaults to `high`

The `/version` endpoint reports the resolved non-secret feature-flag snapshot and GPT reranker sampling caps. It intentionally does not expose all cost knobs. Use it to verify staging rollout state without exposing R2 credentials, service secrets, OpenAI keys, sampled frames, or presigned URLs. GPT reranker OpenAI requests are built with `store=false`.

GPT highlight reranking only receives existing candidate clips and sampled JPEG keyframes. The quality-beta path filters out candidates shorter than the backend minimum or candidates whose event center is too close to the start/end of the window, then asks GPT to verify visible setup, release/event, shot arc, ball path, rim/outcome, camera quality, full play context, explicit `shotResultEvidence`, and frame-role `shotTrackingEvidence` through strict JSON. At the 10-frame budget, shot candidates include release, early arc, late arc, rim approach, rim entry, and below-rim follow-through evidence so GPT can judge ball flight instead of trusting a label or late basket aftermath. Made-shot decisions must also provide rim-entry sequence evidence showing approach, entry, and below-rim/net follow-through. Backend validation rejects kept GPT decisions that still describe tiny, pre-basket-only, unclear, low-score, guessed-made, untracked-entry, missing-outcome, missing rim-entry sequence evidence, unsampled frame-role evidence, or generic frame-role proof when richer sampled shot roles were available before the deterministic EditPlan is built.

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

## Deploy Preflight

Run this before a live staging deploy. It checks GCP auth, Artifact Registry, required Secret Manager entries, the R2 endpoint, and Wrangler auth without printing secret values.

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
ios/backend/.venv/bin/python services/editing/scripts/deploy_preflight.py
```

Expected first-time blockers are missing Secret Manager values and missing Cloudflare auth. Create the missing secrets from an operator-held source; do not paste secret values into logs.

## Cloud Deploy

Once preflight is green:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
IMAGE_TAG="$(git rev-parse --short HEAD)"
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG="$IMAGE_TAG"
```

The staging deploy uses:

- Artifact Registry repo: `hoopsclips`
- Cloud Run service: `hoopclips-editing-staging`
- Source bucket: `hoopsclips-uploads-staging`
- Output bucket: `hoopsclips-results-staging`
- R2 endpoint: `https://78fb4442e6e37b2c46d7e539c6e79172.r2.cloudflarestorage.com`

After deploy, set the Worker secrets so the active control plane can call Cloud Run:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane
printf '%s' "$EDITING_BASE_URL" | npx wrangler secret put EDITING_BASE_URL --env staging
printf '%s' "$EDITING_SHARED_SECRET" | npx wrangler secret put EDITING_SHARED_SECRET --env staging
npx wrangler deploy --env staging --keep-vars
```

Load secret values from an operator-held environment before running these commands. Do not paste secret values directly into shell history, docs, tickets, or chat.

`EDITING_SHARED_SECRET` must match `HOOPS_EDITING_SERVICE_SECRET` on Cloud Run.

## Cloud Smoke

Configure the deployed Cloud Run service with R2 and `HOOPS_EDITING_SERVICE_SECRET`, then load required smoke credentials from an operator-held environment before running:

```bash
# Required pre-exported secret env vars:
# HOOPS_EDITING_SERVICE_SECRET
# HOOPS_R2_ENDPOINT_URL
# HOOPS_R2_ACCESS_KEY_ID
# HOOPS_R2_SECRET_ACCESS_KEY
PYTHONPATH=services/editing:ios/backend \
HOOPS_RENDER_STORAGE_PROVIDER=r2 \
HOOPS_R2_SOURCE_BUCKET=hoopsclips-uploads-staging \
HOOPS_R2_OUTPUT_BUCKET=hoopsclips-results-staging \
ios/backend/.venv/bin/python services/editing/scripts/live_render_smoke.py \
  --base-url https://YOUR-EDITING-SERVICE \
  --render-storage-provider r2
```

Do not place secret values inline in this smoke command; inline assignments can be retained in shell history.

After the Worker is deployed with editing secrets, run the Worker-path smoke:

```bash
PYTHONPATH=services/editing:ios/backend \
WORKER_BASE_URL=https://YOUR-WORKER \
HOOPS_SMOKE_SOURCE_OBJECT_KEY=uploads/YOUR_JOB/source.mp4 \
ios/backend/.venv/bin/python services/editing/scripts/worker_render_smoke.py
```

Do not expose `HOOPS_EDITING_SERVICE_SECRET` or R2 credentials to iOS.

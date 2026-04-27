# Phase Edit2d Live Cloud Render Deploy

## Verdict

Live cloud render is still blocked by provider configuration, not by repo code.

The local and canonical service path exists, but this phase cannot honestly claim:

```text
active Worker -> deployed services/editing Cloud Run -> R2 final.mp4 -> presigned download URL
```

because the staging editing Cloud Run service is not deployed yet and required secrets are missing or unavailable in this environment.

## Verified From This Machine

- Active gcloud account is present.
- Active GCP project is `hoopsclips-9d38f`.
- Artifact Registry has the real Docker repo `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips`.
- Existing Cloud Run services in `us-central1` include `hoopsclips-inference-staging`.
- `hoopclips-editing-staging` does not exist yet.
- Worker config declares required staging secrets:
  - `EDITING_BASE_URL`
  - `EDITING_SHARED_SECRET`
- Worker editing proxy typecheck/dry-run paths are code-valid, but live Worker deploy is blocked by Cloudflare auth.

## Blockers

1. Missing GCP Secret Manager entries for the editing service:

```text
HOOPS_EDITING_SERVICE_SECRET
HOOPS_R2_ACCESS_KEY_ID
HOOPS_R2_SECRET_ACCESS_KEY
```

2. Cloudflare Worker auth is unavailable locally:

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

`wrangler whoami` cannot verify the account and `wrangler deploy --env staging` cannot run safely until auth is present.

3. Worker secrets cannot be written or verified yet:

```text
EDITING_BASE_URL
EDITING_SHARED_SECRET
```

`EDITING_BASE_URL` should be the deployed `hoopclips-editing-staging` Cloud Run URL. `EDITING_SHARED_SECRET` must match `HOOPS_EDITING_SERVICE_SECRET`.

4. No live Worker-path render can run until a real source object exists in the staging upload bucket:

```text
hoopsclips-uploads-staging
```

Use an existing uploaded source key or upload a small smoke video through the normal app/control-plane upload path.

## Config Fixes In This Branch

- `services/editing/cloudbuild.yaml` now points at the existing Artifact Registry repo `hoopsclips`.
- Cloud Run deploy defaults now use separate R2 buckets:
  - source bucket: `hoopsclips-uploads-staging`
  - output bucket: `hoopsclips-results-staging`
- `services/editing` now supports:
  - `HOOPS_R2_SOURCE_BUCKET`
  - `HOOPS_R2_OUTPUT_BUCKET`
  - `HOOPS_R2_BUCKET` as a legacy fallback
- `services/editing/scripts/deploy_preflight.py` checks deploy readiness without printing secrets.
- `services/editing/scripts/worker_render_smoke.py` tests the active Worker render path once Cloud Run and Worker secrets are live.
- `services/editing/scripts/live_render_smoke.py` now fails if the downloaded MP4 is not h264/aac MP4, has the wrong 9:16 or 16:9 resolution, or has a duration mismatch against render status.

## Required Deploy Sequence

Run the preflight first:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
ios/backend/.venv/bin/python services/editing/scripts/deploy_preflight.py
```

Create or verify the three GCP secrets without printing their values:

```bash
printf '%s' "$HOOPS_EDITING_SERVICE_SECRET" | gcloud secrets create HOOPS_EDITING_SERVICE_SECRET --project=hoopsclips-9d38f --data-file=-
printf '%s' "$HOOPS_R2_ACCESS_KEY_ID" | gcloud secrets create HOOPS_R2_ACCESS_KEY_ID --project=hoopsclips-9d38f --data-file=-
printf '%s' "$HOOPS_R2_SECRET_ACCESS_KEY" | gcloud secrets create HOOPS_R2_SECRET_ACCESS_KEY --project=hoopsclips-9d38f --data-file=-
```

If the secrets already exist, add a new version instead of creating them:

```bash
printf '%s' "$HOOPS_EDITING_SERVICE_SECRET" | gcloud secrets versions add HOOPS_EDITING_SERVICE_SECRET --project=hoopsclips-9d38f --data-file=-
printf '%s' "$HOOPS_R2_ACCESS_KEY_ID" | gcloud secrets versions add HOOPS_R2_ACCESS_KEY_ID --project=hoopsclips-9d38f --data-file=-
printf '%s' "$HOOPS_R2_SECRET_ACCESS_KEY" | gcloud secrets versions add HOOPS_R2_SECRET_ACCESS_KEY --project=hoopsclips-9d38f --data-file=-
```

Deploy the editing service:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml
```

Verify Cloud Run health:

```bash
EDITING_BASE_URL="$(gcloud run services describe hoopclips-editing-staging --region us-central1 --project hoopsclips-9d38f --format='value(status.url)')"
curl -fsS "$EDITING_BASE_URL/healthz"
curl -fsS "$EDITING_BASE_URL/readyz"
curl -fsS "$EDITING_BASE_URL/version"
```

Configure and deploy the Worker:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final/services/control-plane
export CLOUDFLARE_API_TOKEN="<operator-held-token>"
npx wrangler whoami
printf '%s' "$EDITING_BASE_URL" | npx wrangler secret put EDITING_BASE_URL --env staging
printf '%s' "$HOOPS_EDITING_SERVICE_SECRET" | npx wrangler secret put EDITING_SHARED_SECRET --env staging
npx wrangler deploy --env staging
```

## Smoke Gates

Direct Cloud Run smoke:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
PYTHONPATH=services/editing:ios/backend \
HOOPS_RENDER_STORAGE_PROVIDER=r2 \
HOOPS_EDITING_BASE_URL="$EDITING_BASE_URL" \
HOOPS_EDITING_SERVICE_SECRET="$HOOPS_EDITING_SERVICE_SECRET" \
HOOPS_R2_SOURCE_BUCKET=hoopsclips-uploads-staging \
HOOPS_R2_OUTPUT_BUCKET=hoopsclips-results-staging \
HOOPS_R2_ENDPOINT_URL=https://78fb4442e6e37b2c46d7e539c6e79172.r2.cloudflarestorage.com \
HOOPS_R2_ACCESS_KEY_ID="$HOOPS_R2_ACCESS_KEY_ID" \
HOOPS_R2_SECRET_ACCESS_KEY="$HOOPS_R2_SECRET_ACCESS_KEY" \
ios/backend/.venv/bin/python services/editing/scripts/live_render_smoke.py \
  --base-url "$EDITING_BASE_URL" \
  --render-storage-provider r2 \
  --editing-secret "$HOOPS_EDITING_SERVICE_SECRET" \
  --timeout-seconds 300
```

Active Worker smoke:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
PYTHONPATH=services/editing:ios/backend \
WORKER_BASE_URL="$WORKER_BASE_URL" \
HOOPS_SMOKE_SOURCE_OBJECT_KEY="$HOOPS_SMOKE_SOURCE_OBJECT_KEY" \
ios/backend/.venv/bin/python services/editing/scripts/worker_render_smoke.py
```

Pass criteria:

- `readyz.status = ok`
- render status reaches `rendered`
- `final.mp4` exists in R2
- `render_log.json` exists in R2
- download URL works
- downloaded MP4 passes FFmpeg decode and FFprobe
- MP4 is h264/aac
- 9:16 output is `720x1280`
- duration matches render status within tolerance

Do not log full presigned download URLs; treat them as bearer tokens.

## Next Gate

Only after the Worker-path smoke passes should the project move to:

```text
codex/phase-edit3-ai-edit-client-ui
```

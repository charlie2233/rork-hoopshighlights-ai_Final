# Phase Edit7c Beta Release Hardening

Date: 2026-05-05

Branch:

```text
codex/phase-edit7c-beta-release-hardening
```

Base commit:

```text
e7c688e
```

Goal:

```text
Prepare the HoopClips AI Edit Agent for beta/TestFlight by tightening deploy readiness,
configuration separation, retention cleanup, observability, feature flags, and user-facing
failure states without adding product features.
```

This phase keeps the existing cloud-first architecture intact. iOS remains the control surface for review, export configuration, status, preview, download, share, and Open In. Analysis, edit planning, revision planning, template application, policy enforcement, durable render state, and FFmpeg rendering remain backend-owned.

## Beta Readiness Checklist

- Export-page AI Edit flow has live proof through Worker, Cloud Run, durable state, R2 output/logs, download URL, iOS preview/share, revision render, and duplicate render idempotency from Phase Edit7b1.
- Cloud Run staging remains intentionally guarded at `max-instances=1` until an approved scaling smoke raises it temporarily.
- Render leases, durable render state, revision persistence, and cleanup dry-run exist before beta traffic.
- Free-tier policy limits, watermark/outro requirements, duplicate render behavior, and stale timeout handling are enforced by backend policy.
- iOS now decodes `failed_timeout`, maps durable render failures to friendly copy, and shows friendly share-failure copy.
- R2 cleanup stays dry-run by default and reports candidate count, object key count, and estimated output bytes before any execute path is used.
- CI deploy automation remains blocked until `CLOUDFLARE_API_TOKEN` and GCP deploy identity secrets are installed.

## Config Matrix

| Surface | Staging | Production / Beta Placeholder | Source |
| --- | --- | --- | --- |
| iOS cloud launch mode | `HOOPS_CLOUD_LAUNCH_MODE=enabled` in Debug | `disabled` in Release until explicit cloud cutover | `ios/HoopsClips/HoopsClips/Config/*.xcconfig` |
| iOS cloud edit base URL | `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev` | blank placeholder | `Debug.xcconfig`, `Release.xcconfig` |
| iOS cloud analysis base URL | local debug default `http://127.0.0.1:8080` | blank placeholder | `Debug.xcconfig`, `Release.xcconfig` |
| Worker service | `hoopsclips-control-plane-staging` | production Worker env not yet defined | `services/control-plane/wrangler.jsonc` |
| Worker URL | `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev` | production URL placeholder | live smoke docs and runtime config |
| Cloud Run editing service | `hoopclips-editing-staging` | production service placeholder | `services/editing/cloudbuild.yaml` |
| Cloud Run region | `us-central1` | production region placeholder, likely `us-central1` unless changed | `services/editing/cloudbuild.yaml` |
| R2 upload bucket | `hoopsclips-uploads-staging` | `hoopsclips-uploads` placeholder | `wrangler.jsonc`, `cloudbuild.yaml` |
| R2 results bucket | `hoopsclips-results-staging` | `hoopsclips-results` placeholder | `wrangler.jsonc`, `cloudbuild.yaml` |
| R2 account | `78fb4442e6e37b2c46d7e539c6e79172` | same account or production account TBD | `wrangler.jsonc` |
| D1 control-plane DB | `hoopsclips-control-plane-staging` / `9d44a3b3-b89f-4ddf-b88f-de5b5ac42f23` | production D1 ID placeholder | `wrangler.jsonc` |
| Statsig | safe local placeholders only | production Statsig env/key TBD | backend feature flag defaults |
| Sentry backend | optional SDK breadcrumbs/messages if DSN is configured | production DSN/env TBD | `services/editing/editing_app/main.py` |
| Sentry iOS | Release requires `HOOPS_SENTRY_DSN` in release preflight | production DSN required before TestFlight | `.github/workflows/release-secrets-preflight.yml` |
| RevenueCat | Debug test key present | production key required | `.github/workflows/release-secrets-preflight.yml` |
| Google auth | blank debug defaults | client ID and reversed client ID required | `.github/workflows/release-secrets-preflight.yml` |

Production cloud edit cutover is still gated. Do not enable Release cloud mode until production Worker, Cloud Run, R2, D1, Sentry, Statsig, auth, and retention settings are explicitly approved.

## Deploy Checklist

Required CI secrets and variables:

```text
CLOUDFLARE_API_TOKEN
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_DEPLOY_SERVICE_ACCOUNT
GCP_PROJECT_ID
GCP_REGION
```

Required GCP Secret Manager secrets for the editing service:

```text
HOOPS_EDITING_SERVICE_SECRET
HOOPS_R2_ACCESS_KEY_ID
HOOPS_R2_SECRET_ACCESS_KEY
```

Required Worker secrets:

```text
ADMIN_API_TOKEN
CONTROL_PLANE_BASE_URL
CONTROL_PLANE_SHARED_SECRET
INFERENCE_BASE_URL
INFERENCE_SHARED_SECRET
EDITING_BASE_URL
EDITING_SHARED_SECRET
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
```

Cloudflare token requirements:

```text
Account: target HoopClips Cloudflare account
Workers Scripts: Edit
Workers Routes: Edit if route-managed deploys are added
D1: Edit for migrations
R2: Edit for bucket bindings/config verification
Queues: Edit if analysis queue deploys are included
Account Settings: Read
```

GCP deploy identity requirements:

```text
Cloud Run Admin
Artifact Registry Writer
Cloud Build Editor or Cloud Build Service Account-compatible submit permission
Secret Manager Secret Accessor for deploy/runtime secret checks
Service Account User for the Cloud Run runtime service account
Viewer on the target project for preflight describe commands
```

Deploy commands:

```bash
cd services/control-plane
npx wrangler deploy --env staging

gcloud builds submit . \
  --project="$GCP_PROJECT_ID" \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG="$GITHUB_SHA"
```

Rollback commands:

```bash
gcloud run services update-traffic hoopclips-editing-staging \
  --project="$GCP_PROJECT_ID" \
  --region="$GCP_REGION" \
  --to-revisions <previous-revision>=100

cd services/control-plane
npx wrangler rollback --env staging
```

Current CI state:

- `.github/workflows/cloud-edit-deploy-preflight.yml` verifies required Cloudflare/GCP deploy inputs and prints deploy/rollback commands without secrets.
- `.github/workflows/release-secrets-preflight.yml` verifies release iOS secret/config presence without printing values.
- No CircleCI config is present in this repo; GitHub Actions is the current CI surface.
- `CLOUDFLARE_API_TOKEN` remains the top deploy automation blocker.

## R2 Retention Policy

Cleanup rules for beta:

| Retention class | Default retention | Execute allowed | Notes |
| --- | --- | --- | --- |
| `preview_render` | 24 hours | later, behind explicit flag | Temporary previews only |
| `free_final_render` | 14 days | yes after dry-run review | Free outputs keep watermark/outro |
| `pro_final_render` | 30 to 90 days placeholder | not until billing/tier policy finalizes | Placeholder only |
| `failed_render_scratch` | 7 days | yes after dry-run review | Failed scratch/object fragments |
| `render_log` | 90 days | not before video unless policy says so | Keep logs longer than videos for support |

Cleanup safety:

- Dry-run remains default.
- Destructive cleanup requires explicit `--execute`.
- Never delete fresh renders.
- Never delete logs earlier than their paired video unless a documented retention class allows it.
- Report candidate count, object key count, and estimated output bytes before execute.
- Log object keys and metadata only. Do not log presigned URLs, R2 credentials, or secret values.

Cleanup smoke command:

```bash
ios/backend/.venv/bin/python services/editing/scripts/render_retention_cleanup.py
```

## Observability Checklist

Event names:

```text
edit_plan.created
edit_revision.created
render.requested
render.started
render.completed
render.failed
render.failed_timeout
policy.failed
download_url.created
ios.preview.loaded
ios.share.opened
ios.share.failed
```

Safe event fields:

```text
editJobId
renderJobId
revisionId
templateId
planTier
rendererVersion
failureReason
outputBytes
durationSeconds
```

Never log:

```text
secret values
R2 credentials
full presigned download URLs
Authorization headers
Cloudflare or GCP access tokens
```

Dashboard metrics:

```text
render success rate
p50 render duration
p95 render duration
failureReason distribution
daily render count
duplicate render count
template usage
revision usage
policy rejection count
output size distribution
cleanup candidate bytes
```

## Statsig Rollout Flags

Target flag names:

```text
ai_edit_enabled
ai_edit_templates_enabled
ai_edit_revisions_enabled
ai_edit_live_render_enabled
ai_edit_free_tier_limits_enabled
ai_edit_cleanup_enabled
ai_edit_max_daily_renders
ai_edit_max_render_seconds
```

Safe defaults:

```text
AI Edit disabled in Release until cloud cutover is approved
templates enabled only where AI Edit is enabled
revisions enabled only where AI Edit is enabled
live render enabled only for staging/internal beta
free-tier limits enforced
cleanup execute disabled
max daily renders falls back to plan policy
max render seconds falls back to plan policy
```

Current backend placeholders:

| Target flag | Current source |
| --- | --- |
| `ai_edit_enabled` | `HOOPS_AI_EDIT_ENABLED` / default feature flag |
| `ai_edit_templates_enabled` | `HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED` / default feature flag |
| `ai_edit_revisions_enabled` | `HOOPS_AI_EDIT_REVISION_ENABLED` / default feature flag |
| `ai_edit_live_render_enabled` | Worker `EDITING_BASE_URL` plus iOS cloud launch mode |
| `ai_edit_free_tier_limits_enabled` | plan-tier policy registry, enforced by default |
| `ai_edit_cleanup_enabled` | cleanup script remains dry-run unless `--execute` is passed |
| `ai_edit_max_daily_renders` | `HOOPS_AI_EDIT_MAX_DAILY_RENDERS` or plan policy |
| `ai_edit_max_render_seconds` | plan-tier policy registry |

## iOS Beta Failure UX

Required user-facing states:

| State | User-facing copy |
| --- | --- |
| render in progress | `Rendering your highlight reel` |
| render failed | `Cloud rendering failed. Try again in a moment.` |
| render timeout | `Rendering timed out. Try a shorter edit.` |
| render too long | `That edit is over this plan's render limit. Choose a shorter length or upgrade later.` |
| daily limit reached | `You've used today's AI edit renders. Try again tomorrow.` |
| active render limit | `Another AI edit is still rendering. Let that finish before starting another.` |
| download expired | `The download link expired. Hoopclips is requesting a fresh one.` |
| share failed | `Could not prepare the MP4 for sharing. Try again in a moment.` |
| template asset missing | `This template is missing a required asset. Try another template while we fix it.` |

Implementation notes:

- `failed_timeout` is a first-class decoded render state in iOS.
- Full presigned URLs are still not logged.
- Share/Open In still uses a downloaded local MP4 file, not the raw presigned URL.
- No local video rendering or composition was added.

## Controlled Staging Load Smoke Plan

Run after CI deploy auth is installed or during a manual staging window:

```text
1. Start 3 to 5 Personal Highlight 30s render requests.
2. Trigger one duplicate render request with the same idempotency key.
3. Trigger one More Hype revision render.
4. Trigger one policy failure, such as over free-tier duration.
5. Run retention cleanup dry-run.
```

Expected result:

```text
all normal renders complete
duplicate render returns existing renderJobId
revision render completes
policy failure returns safe failureReason
cleanup dry-run reports candidates without deletion
no full presigned URLs are logged
```

Cloud Run scaling:

- Keep `max-instances=1` for staging by default.
- Any `max-instances=2` smoke must be temporary, documented, and rolled back unless explicitly approved.

## Known Limitations

- `CLOUDFLARE_API_TOKEN` is still required for Wrangler automation in CI.
- Production Worker, Cloud Run, R2, D1, Statsig, and Sentry values are placeholders until beta cutover approval.
- Cleanup execute mode exists as an explicit path, but beta should start with reviewed dry-run output.
- Live load smoke was not rerun in this hardening pass; Phase Edit7b1 remains the latest Worker -> Cloud Run -> R2 live concurrency evidence.

## Validation

Commands run for this branch:

```bash
git diff --check
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service
npm --prefix services/control-plane run typecheck
cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing CODE_SIGNING_ALLOWED=NO
ios/backend/.venv/bin/python services/editing/scripts/render_retention_cleanup.py
```

Results:

```text
git diff --check: pass
services/editing unittest: pass, 24 tests
control-plane typecheck: pass
control-plane editing proxy tests: pass, 6 tests
retention cleanup dry-run smoke: pass, 0 candidates, 0 object keys, 0 estimated bytes
iOS Debug simulator build: pass
iOS Debug build-for-testing: pass
```

Notes:

- iOS builds still emit pre-existing Swift concurrency/deprecation warnings in analysis/export/test code.
- Live Worker -> Cloud Run -> R2 load smoke was not rerun in this hardening pass because no live render contract or renderer behavior changed. Phase Edit7b1 remains the latest live concurrency evidence.

# Phase Edit6b Live Policy And Observability Smoke

## Goal

Phase Edit6b verifies the Phase Edit6 safety layer against staging:

```text
Worker request -> policy checks -> Cloud Run editing -> FFmpeg -> R2 final.mp4/render_log.json -> download URL -> revision/failure observability
```

No new templates, renderer architecture changes, local iOS rendering, or timeline editor work were added. The iOS app remains a cloud-editing client for export configuration, status, preview, download, share, and Open In.

## Branch And Commits

- Branch: `codex/phase-edit6b-live-policy-and-observability-smoke`
- Base branch: `codex/phase-edit6-agent-polish-and-cost-controls`
- Base commit from prompt: `82c07b5`
- Phase6b implementation commits:
  - `7e01911` - Track revision IDs in render metadata
  - `2470724` - Add live policy observability smoke
  - `c15d168` - Emit policy failure observability events
  - `0cb2e25` - Verify live AI edit policy smoke
  - `46d61ab` - Fix edit policy failure event fields
  - `511c3b0` - Document final policy smoke evidence

The revision ID patch was required by the live-smoke checklist. Before the patch, revision renders did not carry `revisionId` into render status, retention metadata, or `render_log.json`.

The final policy observability patch was required by live verification. The first live smoke proved policy rejection, but the staging logs did not expose `policy.failed`; the final Cloud Run revision now emits it safely for policy/cost-control failures.

The final smoke rerun exposed a staging Cloud Run config issue: the service used in-memory render job state while Cloud Run allowed multiple instances and request-based CPU. Normal render completed, but revision status polling could hit an instance without the render map and return `render_job_not_found`. The staging deploy config now pins the current background-task renderer to one instance and disables CPU throttling until a durable job store lands.

## Staging Deployment

`services/editing` was first deployed for full live smoke from code hash `c15d168`, then redeployed during closeout from runtime code hash `46d61ab`.

Final deployment evidence:

- Cloud project: `hoopsclips-9d38f`
- Artifact Registry repo: `us-central1/hoopsclips`
- Cloud Build ID: `2e927740-b294-4831-8986-5d58f87034dc`
- Image: `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:c15d168`
- Cloud Run service: `hoopclips-editing-staging`
- Cloud Run revision: `hoopclips-editing-staging-00011-ktq`
- Cloud Run URL: `https://hoopclips-editing-staging-npya43jiia-uc.a.run.app`
- Worker URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Active Worker deployment version observed by Wrangler: `3dc0312f-9043-4762-b8c1-dfd46f0a0ad1`

Cloud Build reported the non-blocking Cloud Run IAM policy warning:

```text
Setting IAM policy failed, try "gcloud beta run services add-iam-policy-binding ..."
```

The service still deployed, routed traffic to the new revision, and returned healthy `/readyz` and `/version` responses.

`/version` after the full live smoke deploy:

```json
{
  "gitSha": "c15d168",
  "ffmpegAvailable": true,
  "ffprobeAvailable": true,
  "drawtextAvailable": true,
  "featureFlags": {
    "aiEditEnabled": true,
    "aiEditRevisionEnabled": true,
    "aiEditTemplatePackEnabled": true,
    "aiEditMaxDailyRenders": null,
    "aiEditFreeWatermarkRequired": true,
    "aiEditProExportsEnabled": false
  }
}
```

`/readyz` confirmed:

- `auth=configured`
- `renderStorage.provider=r2`
- `providerReady=true`
- `downloadTtlSeconds=900`
- required R2 bucket, endpoint, access key, and secret key config present

Final runtime closeout deploy after the edit-job error-field cleanup:

- Cloud Build ID: `643da3d8-3e3b-4563-8206-c1cf5fa7f806`
- Image: `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:46d61ab`
- Image digest: `sha256:2439335e41cfdf5faeecd3e2cc230be65e22b15f4b18b025e1e90f967d6cbbbc`
- Cloud Run revision: `hoopclips-editing-staging-00013-vbl`
- Traffic: 100 percent to `hoopclips-editing-staging-00013-vbl`
- `/version` gitSha: `46d61ab`
- `/readyz`: `status=ok`, `auth=configured`, `renderStorage.provider=r2`, `providerReady=true`

Final staging config update after the rerun exposed split in-memory render state:

- Cloud Run revision: `hoopclips-editing-staging-00014-q89`
- Traffic: 100 percent to `hoopclips-editing-staging-00014-q89`
- `/version` gitSha: `46d61ab`
- `autoscaling.knative.dev/maxScale=1`
- `run.googleapis.com/cpu-throttling=false`
- `services/editing/cloudbuild.yaml` now codifies `--max-instances 1` and `--no-cpu-throttling`

Statsig API verification was not run because no Statsig server secret is configured locally. The deployed service safe-default feature flags were verified through `/version`.

## Live Policy Smoke Command

The final live smoke used the active Worker and final Cloud Run editing URL:

```text
PYTHONPATH=services/editing/scripts \
ios/backend/.venv/bin/python services/editing/scripts/policy_observability_smoke.py \
  --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --editing-url https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
```

Summary artifact:

```text
/private/var/folders/zd/0b3nmw551mdgk8ybwgcbt1380000gn/T/hoopclips-policy-smoke-3v8z5086/policy_observability_smoke_summary.json
```

The script intentionally does not print full presigned upload or download URLs.

## Normal Free Render

- editJobId: `edit_aa16d33034df461893737a7e72e4406a`
- renderJobId: `render_cce01e1ca70f4a4b898a8fbe263ba457`
- duplicate renderJobId: `render_cce01e1ca70f4a4b898a8fbe263ba457`
- duplicate behavior: `idempotent_existing_render_returned`
- source object: `uploads/9a5aac9c35c545ec8a8aaab1c1fbc454/source.mp4`
- final object: `edits/edit_aa16d33034df461893737a7e72e4406a/render_jobs/render_cce01e1ca70f4a4b898a8fbe263ba457/final.mp4`
- render log: `edits/edit_aa16d33034df461893737a7e72e4406a/render_jobs/render_cce01e1ca70f4a4b898a8fbe263ba457/render_log.json`
- templateId: `personal_highlight_v1`
- planTier: `free`

ffprobe summary:

```text
H.264/AAC MP4
720x1280
duration 18.422005s
size 447584 bytes
```

Policy evidence:

- `maxRenderSeconds=45`
- `maxDailyRenders=3`
- `maxActiveRenders=1`
- `maxRevisionsPerEdit=3`
- `maxOutputResolution=720p`
- `watermarkRequired=true`
- `outroRequired=true`
- `renderRetentionDays=14`
- `staleRenderTimeoutSeconds=900`
- `maxRenderRetries=1`

Retention metadata in status and render log:

```json
{
  "expiresAt": "2026-05-17T06:15:48.293037+00:00",
  "retentionClass": "free_final_render",
  "deleteEligible": true,
  "planTier": "free",
  "editJobId": "edit_aa16d33034df461893737a7e72e4406a",
  "renderJobId": "render_cce01e1ca70f4a4b898a8fbe263ba457",
  "revisionId": null,
  "templateId": "personal_highlight_v1",
  "outputBytes": 447584,
  "durationSeconds": 18.422
}
```

Template/render log metadata included:

- `captionStyle=bold_hype`
- `effectProfile=hype_effects`
- `audioProfile=hype`
- `outroProfile=free_social_outro`
- `plannedDurationSeconds=17.2`
- `complexityUnits=22.704`

## Revision Render Smoke

The live smoke requested `make_more_hype`, validated the revised plan, and rendered the revision.

- editJobId: `edit_aa16d33034df461893737a7e72e4406a`
- revisionId: `rev_58906db938564fda9cef627877f6014d`
- revised renderJobId: `render_c58a1e0d6c4545e18b2b3e245df536e8`
- revised final object: `edits/edit_aa16d33034df461893737a7e72e4406a/render_jobs/render_c58a1e0d6c4545e18b2b3e245df536e8/final.mp4`
- revised render log: `edits/edit_aa16d33034df461893737a7e72e4406a/render_jobs/render_c58a1e0d6c4545e18b2b3e245df536e8/render_log.json`
- validationResult: `valid=true`, `errors=[]`

ffprobe summary:

```text
H.264/AAC MP4
720x1280
duration 18.422005s
size 440194 bytes
```

Revision metadata was present in both status and render log:

```json
{
  "revisionId": "rev_58906db938564fda9cef627877f6014d",
  "retentionMetadata": {
    "expiresAt": "2026-05-17T06:16:05.338725+00:00",
    "retentionClass": "free_final_render",
    "deleteEligible": true,
    "planTier": "free",
    "editJobId": "edit_aa16d33034df461893737a7e72e4406a",
    "renderJobId": "render_c58a1e0d6c4545e18b2b3e245df536e8",
    "revisionId": "rev_58906db938564fda9cef627877f6014d",
    "templateId": "personal_highlight_v1",
    "outputBytes": 440194,
    "durationSeconds": 18.422
  }
}
```

## Policy Rejection Smoke

The live smoke requested a free `personal_highlight_v1` edit with `targetDurationSeconds=120`.

Expected result:

```text
rejected before render
```

Observed result:

```json
{
  "httpStatus": 400,
  "errorCode": "render_duration_limit",
  "failureReason": "Requested AI edit length exceeds this plan's render limit.",
  "status": "rejected_before_render"
}
```

No render job was started for this over-limit request.

A final Cloud Run log query on revision `hoopclips-editing-staging-00014-q89` confirmed the safe policy failure event:

```json
{
  "event": "policy.failed",
  "failureReason": "render_duration_limit",
  "planTier": "free",
  "templateId": "personal_highlight_v1"
}
```

No URL, secret, R2 credential, or presigned URL fields were present in the `policy.failed` event.

## Observability Evidence

Cloud Run logs for `edit_aa16d33034df461893737a7e72e4406a` contained these safe structured events:

```text
edit_plan.created
render.requested
render.started
render.completed
download_url.created
edit_revision.created
render.requested
render.started
render.completed
download_url.created
```

The final policy rejection probe also emitted:

```text
policy.failed
```

Observed event fields included:

- `editJobId`
- `renderJobId`
- `revisionId`
- `templateId`
- `planTier`
- `rendererVersion`
- `outputBytes`
- `durationSeconds`
- `failureReason`

No secret values, R2 credentials, or full presigned URLs were present in the captured smoke summaries or Cloud Run event excerpts.

Sentry API verification was not run because `SENTRY_AUTH_TOKEN` is not configured in the local environment. The service code adds Sentry breadcrumbs when `sentry_sdk` is available, but this branch verified the Cloud Run structured-log surface directly.

## Download URL Refresh Behavior

The live smoke downloaded MP4s from backend-issued URLs but did not force-expire a presigned URL. Client-side recovery remains covered by the iOS implementation:

- `CloudEditError.downloadURLExpired` maps to `The download link expired. Hoopclips is requesting a fresh one.`
- `AIEditView.prepareShareSheet()` refreshes the download URL before sharing if it is near expiry.
- If a download fails with `downloadURLExpired`, the view fetches a fresh URL and retries downloading the local MP4.

The share path still shares a downloaded local `.mp4`, not the raw presigned URL.

## CI And Deploy Auth Blocker

Manual Wrangler OAuth worked for this branch. CI still needs:

```text
CLOUDFLARE_API_TOKEN
```

Recommended CI secret location:

```text
GitHub Actions / repository or environment secret: CLOUDFLARE_API_TOKEN
```

Minimum deployment needs:

- deploy `services/control-plane` with Wrangler
- read/list Worker deployments for smoke evidence
- set/update staging Worker secrets when ops rotates them

Recommended token permissions:

- Account: Workers Scripts Edit
- Account: Workers Tail Read, optional for live log smoke
- Account: D1 Edit, if migrations or DB-bound Worker deploy validation runs in CI
- Account: Queues Edit, if queue-bound Worker deploy validation runs in CI
- Account: R2 Read/Write, if CI smoke fetches `render_log.json` or verifies R2 objects with Wrangler

Do not store Cloudflare tokens in plaintext `vars` or repo files.

## Validation

Passed:

- `git diff --check`
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service`
- `npm --prefix services/control-plane run typecheck`
- `cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO -derivedDataPath /tmp/hoopclips-phase6b-build`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing CODE_SIGNING_ALLOWED=NO -derivedDataPath /tmp/hoopclips-phase6b-build-for-testing`
- `PYTHONPATH=services/editing/scripts ios/backend/.venv/bin/python services/editing/scripts/policy_observability_smoke.py --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev --editing-url https://hoopclips-editing-staging-npya43jiia-uc.a.run.app`

The backend suite also caught and covered a real exception-path bug during closeout: some edit-job GET error handlers referenced request-only fields that do not exist on GET routes. The final patch now emits safe policy metadata using stored edit-job fields when available, and missing edit-job GET/plan/revisions routes return proper `edit_job_not_found` responses.

After the final error-field cleanup, these focused checks also passed:

- `ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/main.py`
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v`

## Remaining Notes

- Live normal free render, revision render, duplicate/idempotency, policy rejection, retention metadata, and safe Cloud Run observability were verified.
- The staging renderer is intentionally pinned to one Cloud Run instance with CPU always allocated while render state is in memory. Durable render job storage remains a beta-hardening item before scaling beyond one instance.
- Persistent render quota/job state outside a single Cloud Run instance remains a beta-hardening item.
- A non-destructive R2 cleanup dry run should be added in Phase Edit7 before any destructive cleanup job.
- The full live policy smoke is too slow for routine PR CI. Keep it manual or nightly; use fast fixture/mocked checks in ordinary CI.
- CI deploy automation remains blocked until `CLOUDFLARE_API_TOKEN` is installed in the CI secret store with the necessary Wrangler permissions.

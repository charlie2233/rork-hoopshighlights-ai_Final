# Phase Edit6b Live Policy And Observability Smoke

## Goal

Phase Edit6b verifies the Phase Edit6 safety layer against staging:

```text
Export/Worker request -> policy checks -> Cloud Run editing -> FFmpeg -> R2 final.mp4/render_log.json -> download URL -> revision/failure observability
```

No new templates, renderer architecture changes, local iOS rendering, or timeline editor work were added. The iOS app remains a cloud-editing client for export configuration, status, preview, download, share, and Open In.

## Branch And Commits

- Branch: `codex/phase-edit6b-live-policy-and-observability-smoke`
- Base branch: `codex/phase-edit6-agent-polish-and-cost-controls`
- Base commit from prompt: `82c07b5`
- Phase6b commits before this documentation closeout:
  - `7e01911` - Track revision IDs in render metadata
  - `2470724` - Add live policy observability smoke
  - `c15d168` - Emit policy failure observability events
  - `0cb2e25` - Verify live AI edit policy smoke

The revision ID patch was required by the live-smoke checklist. Before the patch, revision renders did not carry `revisionId` into render status, retention metadata, or `render_log.json`.

## Staging Deployment

`services/editing` was deployed to Cloud Run from commit `2470724`.

```text
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG=2470724
```

Deployment evidence:

- Cloud Build ID: `1ac02234-7e5d-4311-8702-88754b53f98d`
- Image: `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:2470724`
- Cloud Run service: `hoopclips-editing-staging`
- Cloud Run revision: `hoopclips-editing-staging-00010-7px`
- Cloud Run URL: `https://hoopclips-editing-staging-npya43jiia-uc.a.run.app`
- Worker URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Active Worker deployment version observed by Wrangler: `3dc0312f-9043-4762-b8c1-dfd46f0a0ad1`

Cloud Build again reported the non-blocking Cloud Run IAM policy warning:

```text
Setting IAM policy failed, try "gcloud beta run services add-iam-policy-binding ..."
```

The service still deployed, routed 100 percent traffic to the new revision, and returned healthy `/readyz` and `/version` responses.

`/version` after deploy:

```json
{
  "gitSha": "2470724",
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
- required R2 bucket/endpoint/access-key/secret-key config present

Final closeout deployment after the revision-limit fix and documentation pass:

- Cloud Build ID: `e8105faf-33e6-4336-82e4-a267d4d349bc`
- Image: `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:0cb2e25`
- Image digest: `sha256:04494e7226a58b04a269ed41a52d6222a1968bcbb4944beb061c024c03ee88cf`
- Cloud Run revision: `hoopclips-editing-staging-00012-ndv`
- Traffic: 100 percent to `hoopclips-editing-staging-00012-ndv`
- `/version` gitSha: `0cb2e25`
- `/readyz`: `status=ok`, `auth=configured`, `renderStorage.provider=r2`, `providerReady=true`

## Live Policy Smoke

The live smoke used:

```text
PYTHONPATH=services/editing/scripts:services/editing:ios/backend \
ios/backend/.venv/bin/python services/editing/scripts/policy_observability_smoke.py \
  --output-dir /tmp/hoopclips-phase6b-policy-smoke-20260502-223921
```

Summary artifact:

```text
/private/tmp/hoopclips-phase6b-policy-smoke-20260502-223921/policy_observability_smoke_summary.json
```

The script intentionally does not print full presigned upload or download URLs.

### Normal Free Render

- editJobId: `edit_a131a05278ec475785294e86605c490a`
- renderJobId: `render_00f7e212fab244048bac184081ab8321`
- source object: `uploads/133dbc8cdb13479f852c4dfa8f35bbf4/source.mp4`
- final object: `edits/edit_a131a05278ec475785294e86605c490a/render_jobs/render_00f7e212fab244048bac184081ab8321/final.mp4`
- render log: `edits/edit_a131a05278ec475785294e86605c490a/render_jobs/render_00f7e212fab244048bac184081ab8321/render_log.json`
- templateId: `personal_highlight_v1`
- planTier: `free`
- duplicate behavior: second render request returned the same active/rendered `renderJobId`

ffprobe summary:

```text
H.264/AAC MP4
720x1280
duration 18.422005s
size 447717 bytes
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

Retention metadata in status and render log:

```json
{
  "expiresAt": "2026-05-17T05:40:44.021737+00:00",
  "retentionClass": "free_final_render",
  "deleteEligible": true,
  "planTier": "free",
  "editJobId": "edit_a131a05278ec475785294e86605c490a",
  "renderJobId": "render_00f7e212fab244048bac184081ab8321",
  "revisionId": null,
  "templateId": "personal_highlight_v1",
  "outputBytes": 447717,
  "durationSeconds": 18.422
}
```

Template/render log metadata included:

- `captionStyle=bold_hype`
- `effectProfile=hype_effects`
- `audioProfile=hype`
- `watermarkAssetId=hoopclips_app_icon_v1`
- `outroAssetId=personal_highlight_outro_free_v1`

## Revision Render Smoke

The live smoke requested `make_more_hype`, validated the revised plan, and rendered the revision.

- editJobId: `edit_a131a05278ec475785294e86605c490a`
- revisionId: `rev_b2aad8f533764d91acafb188706b8bcd`
- revised renderJobId: `render_9d5b656785124f8caffbade87e96d52a`
- revised final object: `edits/edit_a131a05278ec475785294e86605c490a/render_jobs/render_9d5b656785124f8caffbade87e96d52a/final.mp4`
- revised render log: `edits/edit_a131a05278ec475785294e86605c490a/render_jobs/render_9d5b656785124f8caffbade87e96d52a/render_log.json`
- validationResult: `valid=true`, `errors=[]`

ffprobe summary:

```text
H.264/AAC MP4
720x1280
duration 18.422005s
size 441071 bytes
```

Revision metadata was present in both status and render log:

```json
{
  "revisionId": "rev_b2aad8f533764d91acafb188706b8bcd",
  "retentionMetadata": {
    "revisionId": "rev_b2aad8f533764d91acafb188706b8bcd",
    "retentionClass": "free_final_render",
    "planTier": "free",
    "templateId": "personal_highlight_v1"
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

The local backend regression test also verifies that this rejection emits a safe `policy.failed` event with `failureReason=render_duration_limit`, `planTier=free`, `templateId=personal_highlight_v1`, and no URL/secret fields. The live Cloud Run log query did not surface a `policy.failed` entry for this specific over-limit request, so a separate controlled failed-render probe was run to prove the live `render.failed` observability path.

After deploying final commit `0cb2e25`, a focused live revision-limit probe created three free-tier revisions and verified that the fourth revision request was blocked before render:

- editJobId: `edit_628f2ac1ac744e73856138d42404f954`
- accepted revision count: `3`
- rejected request status: `429`
- errorCode: `revision_limit`
- failureReason: `Revision limit reached for this edit.`

Cloud Run logs for the final deploy included the expected safe events:

```json
[
  {
    "event": "edit_plan.created",
    "editJobId": "edit_628f2ac1ac744e73856138d42404f954",
    "templateId": "personal_highlight_v1",
    "planTier": "free"
  },
  {
    "event": "edit_revision.created",
    "editJobId": "edit_628f2ac1ac744e73856138d42404f954",
    "revisionId": "rev_15e7f2f05db447b3a33c18717cb438aa",
    "templateId": "personal_highlight_v1",
    "planTier": "free"
  },
  {
    "event": "edit_revision.created",
    "editJobId": "edit_628f2ac1ac744e73856138d42404f954",
    "revisionId": "rev_71fb140f196a48b4a8c945832cd2a3d7",
    "templateId": "personal_highlight_v1",
    "planTier": "free"
  },
  {
    "event": "edit_revision.created",
    "editJobId": "edit_628f2ac1ac744e73856138d42404f954",
    "revisionId": "rev_34b4e59ce7054c1ab43509003dd3dbe9",
    "templateId": "personal_highlight_v1",
    "planTier": "free"
  },
  {
    "event": "policy.failed",
    "editJobId": "edit_628f2ac1ac744e73856138d42404f954",
    "failureReason": "revision_limit",
    "templateId": "personal_highlight_v1",
    "planTier": "free"
  }
]
```

## Controlled Failed Render Probe

A separate edit job intentionally rendered with a missing source object to prove live failed-render state, failed-render retention metadata, and `render.failed` logging.

- editJobId: `edit_5e785855aae24fe5ab9c92d2f630bb3a`
- renderJobId: `render_cf44ab8fdb1a4a8481933af710214ed4`
- status: `failed`
- failureReason: `invalid_edit_plan`
- validation error: `source_missing`
- render log: `edits/edit_5e785855aae24fe5ab9c92d2f630bb3a/render_jobs/render_cf44ab8fdb1a4a8481933af710214ed4/render_log.json`

Failed-render retention metadata:

```json
{
  "expiresAt": "2026-05-10T05:45:12.808432+00:00",
  "retentionClass": "free_failed_render",
  "deleteEligible": true,
  "planTier": "free",
  "editJobId": "edit_5e785855aae24fe5ab9c92d2f630bb3a",
  "renderJobId": "render_cf44ab8fdb1a4a8481933af710214ed4",
  "revisionId": null,
  "templateId": "personal_highlight_v1",
  "outputBytes": 0,
  "durationSeconds": 0.0
}
```

Cloud Run structured events for this probe:

```json
[
  {
    "event": "edit_plan.created",
    "editJobId": "edit_5e785855aae24fe5ab9c92d2f630bb3a",
    "templateId": "personal_highlight_v1",
    "planTier": "free"
  },
  {
    "event": "render.failed",
    "editJobId": "edit_5e785855aae24fe5ab9c92d2f630bb3a",
    "renderJobId": "render_cf44ab8fdb1a4a8481933af710214ed4",
    "failureReason": "invalid_edit_plan",
    "planTier": "free"
  }
]
```

## Observability Evidence

Cloud Run logs for `edit_a131a05278ec475785294e86605c490a` contained these safe structured events:

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

Observed event fields included:

- `editJobId`
- `renderJobId`
- `revisionId` on revision creation
- `templateId`
- `planTier`
- `rendererVersion`
- `outputBytes`
- `durationSeconds`
- `failureReason` on the controlled failed render

No secret values, R2 credentials, or full presigned URLs were present in the captured smoke summaries or Cloud Run event excerpts.

Sentry API verification was not run because `SENTRY_AUTH_TOKEN` is not configured in the local environment. The service code adds Sentry breadcrumbs when `sentry_sdk` is available, but this branch verified the Cloud Run structured-log surface directly.

Statsig API verification was not run because no Statsig server secret is configured locally. The deployed service safe-default feature flags were verified through `/version`.

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

Passed after the revision-limit exception fix:

- `git diff --check`
- `ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/main.py services/editing/editing_app/models.py services/editing/editing_app/render_storage.py services/editing/scripts/policy_observability_smoke.py`
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v`
- `npm --prefix services/control-plane run typecheck`
- `npx tsx --test test/control-plane-editing-proxy.test.ts` from `services/control-plane`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-phase6b-dd build CODE_SIGNING_ALLOWED=NO`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-phase6b-dd build-for-testing CODE_SIGNING_ALLOWED=NO`

The first full `services.editing.tests.test_editing_service` run caught a real issue in the `revision_limit` error path: the revision endpoint exception handler referenced fields that do not exist on `ReviseEditJobRequest`. The final patch now emits `policy.failed` with the path `editJobId` and stored plan metadata instead, and the focused regression passed before the full suite rerun.

## Remaining Notes

- Live normal free render, revision render, duplicate/idempotency, policy rejection, failed-render retention, and safe Cloud Run observability were verified.
- `policy.failed` is verified by unit test and by a final live revision-limit probe on deployed commit `0cb2e25`. The live `render.failed` path was also visible.
- Persistent render quota/job state outside a single Cloud Run instance remains a beta-hardening item.
- A non-destructive R2 cleanup dry run should be added in Phase Edit7 before any destructive cleanup job.
- The full live policy smoke is too slow for routine PR CI. Keep it manual or nightly; use fast fixture/mocked checks in ordinary CI.

# Phase Edit7d TestFlight Release Candidate

Date: 2026-05-06

Branch:

```text
codex/phase-edit7d-testflight-release-candidate
```

Base commit:

```text
80fb04f
```

Goal:

```text
Prepare a TestFlight-ready release candidate for HoopClips AI Edit Agent by
finalizing deploy readiness, configuration audit, feature flags, privacy/storage
copy, final staging smoke evidence, and release documentation without adding
new product features.
```

This branch keeps the cloud-first architecture intact. iOS remains the control surface for upload, review, export configuration, status, native preview, download, share sheet, and Open In. Analysis, edit planning, revision planning, template application, policy enforcement, durable render state, and FFmpeg rendering remain backend-owned.

## RC Go/No-Go Checklist

| Gate | Status | Notes |
| --- | --- | --- |
| Export-page AI Edit flow | pass | Phase Edit4c proved live UI preview/share; this branch reran Worker-path base plus revision render. |
| Cloud render path | pass | Worker -> Cloud Run editing -> durable state -> R2 object keys -> download URL -> ffprobe passed. |
| Revision render | pass | More Hype revision validated and rendered through Worker path. |
| Durable state/concurrency | pass from Phase Edit7b1 | Latest live durable/idempotency/reload proof remains Phase Edit7b1. |
| Cleanup lifecycle | beta-ready dry-run | Dry-run remains default; execute requires explicit `--execute`. |
| CI deploy auth | blocked | `CLOUDFLARE_API_TOKEN` must be installed in GitHub Actions staging environment. |
| Production config | blocked | Production Worker, Cloud Run, R2, D1, Sentry, Statsig, and cloud cutover values remain placeholders. |
| TestFlight upload | not attempted | This branch prepares RC docs and build validation; upload is a separate release operation. |

## CI Deploy Auth Readiness

Required GitHub Actions environment secret:

```text
CLOUDFLARE_API_TOKEN
```

Cloudflare token requirements:

```text
Environment: staging
Account: HoopClips Cloudflare account
Workers Scripts: Edit
Account Settings: Read
D1: Edit, if migrations run from CI
R2: Edit, if CI verifies bucket bindings or render artifacts
Workers Routes: Edit, only if route-managed deploys are added
Rotation: create a replacement token in Cloudflare, update GitHub Actions environment secret, run preflight, then revoke the old token
```

Required GitHub Actions secrets and variables:

```text
secrets.CLOUDFLARE_API_TOKEN
secrets.GCP_WORKLOAD_IDENTITY_PROVIDER
secrets.GCP_DEPLOY_SERVICE_ACCOUNT
vars.GCP_PROJECT_ID
vars.GCP_REGION
```

Required GCP roles for the deploy identity:

```text
Cloud Run Admin
Artifact Registry Writer
Cloud Build submit permissions
Secret Manager Secret Accessor for deploy-time checks
Service Account User on the Cloud Run runtime service account, if required
Viewer on the target project for preflight describe commands
```

Workflow surfaces:

```text
.github/workflows/cloud-edit-deploy-preflight.yml
.github/workflows/release-secrets-preflight.yml
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

Do not print or commit token values.

## Staging/Production Config Matrix

| Surface | Staging | Production/TestFlight |
| --- | --- | --- |
| iOS bundle ID | `atrak.charlie.hoopsclips` | same unless App Store Connect uses a separate beta bundle |
| iOS version/build | `MARKETING_VERSION=1.0.0`, `CURRENT_PROJECT_VERSION=1` | bump before upload if App Store Connect already has build `1` |
| Development team | `K99RADPB9G` from local resolved build settings | must be provided by `HOOPS_DEVELOPMENT_TEAM` in CI |
| iOS cloud launch mode | `enabled` in Debug | `disabled` in Release until explicit cloud cutover |
| iOS cloud edit URL | `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev` | blank while Release cloud mode is disabled |
| iOS cloud analysis URL | local debug default unless overridden | blank while Release cloud mode is disabled |
| Worker service | `hoopsclips-control-plane-staging` | production Worker env not defined |
| Worker URL | `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev` | production URL placeholder |
| Worker version lookup | blocked locally | requires `CLOUDFLARE_API_TOKEN` or valid Wrangler auth |
| Cloud Run editing service | `hoopclips-editing-staging` | production service placeholder |
| Cloud Run region | `us-central1` | likely `us-central1`, pending production decision |
| Cloud Run current staging revision | `hoopclips-editing-staging-00022-btg` | not applicable |
| Cloud Run current staging `/version` | `gitSha=d00d0d5`, renderer `ffmpeg-renderer-v1` | production version TBD |
| Cloud Run max instances | `1` | do not raise without controlled multi-instance smoke |
| R2 upload bucket | `hoopsclips-uploads-staging` | `hoopsclips-uploads` placeholder |
| R2 results bucket | `hoopsclips-results-staging` | `hoopsclips-results` placeholder |
| R2 account | `78fb4442e6e37b2c46d7e539c6e79172` | same account or production account TBD |
| D1 database | `hoopsclips-control-plane-staging` | production D1 placeholder |
| Sentry iOS | `HOOPS_SENTRY_DSN` required by release preflight | production DSN required before upload |
| Sentry backend | optional when DSN is configured | production DSN/env TBD |
| Statsig | safe backend defaults | production server/client env TBD |
| RevenueCat | test key in Debug | production key required by release preflight |
| Google client ID | blank in Debug defaults | production client ID and reversed ID required |
| Firebase Auth API key | blank in Debug defaults | production key required |

Release cloud cutover is still gated. Do not change Release cloud mode from `disabled` until production Worker, Cloud Run, R2, D1, Sentry, Statsig, auth, privacy/storage policy, and rollback gates are approved.

## Feature Flags And Kill Switches

Target rollout flags:

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
Release iOS cloud mode remains disabled until cutover approval
backend free-tier limits are enforced by default
templates and revisions are only useful where AI Edit is enabled
cleanup execute is disabled unless --execute is explicitly passed
max daily renders and max render seconds fall back to plan-tier policy
pro exports remain disabled until billing/pro policy exists
```

Current implementation mapping:

| Target flag | Current source |
| --- | --- |
| `ai_edit_enabled` | `HOOPS_AI_EDIT_ENABLED` / backend defaults |
| `ai_edit_templates_enabled` | `HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED` / backend defaults |
| `ai_edit_revisions_enabled` | `HOOPS_AI_EDIT_REVISION_ENABLED` / backend defaults |
| `ai_edit_live_render_enabled` | Worker `EDITING_BASE_URL`, editing shared secret, and iOS cloud launch mode |
| `ai_edit_free_tier_limits_enabled` | plan-tier policy registry |
| `ai_edit_cleanup_enabled` | cleanup script dry-run by default; execute requires `--execute` |
| `ai_edit_max_daily_renders` | `HOOPS_AI_EDIT_MAX_DAILY_RENDERS` or plan policy |
| `ai_edit_max_render_seconds` | plan-tier policy registry |

## Privacy And Storage Copy

Beta-facing copy added or verified:

```text
Hoopclips uploads the selected source to cloud services, creates the edit there,
and stores the finished MP4 temporarily for preview and sharing.
```

Recommended TestFlight notes copy:

```text
AI Edit renders videos in the HoopClips cloud. Export can take a few minutes.
Rendered videos are stored temporarily so you can preview, download, and share
them. Free beta exports include a HoopClips watermark/outro.
```

Retention summary:

| Artifact | Beta retention |
| --- | --- |
| Preview renders | 24 hours target |
| Free final renders | 14 days |
| Pro final renders | 30 to 90 days placeholder |
| Failed render scratch files | 7 days |
| Render logs | 90 days target, retained longer than video for support |

Do not promise deletion timing until cleanup execute mode is enabled and monitored.

## R2 Cleanup Lifecycle

Cleanup command:

```bash
ios/backend/.venv/bin/python services/editing/scripts/render_retention_cleanup.py
```

Safety rules:

```text
dry-run remains default
destructive cleanup requires explicit --execute
object keys and metadata may be logged
presigned URLs, R2 credentials, and secrets must never be logged
fresh renders must not be deleted
render logs should outlive videos unless a reviewed policy says otherwise
```

## Final Live RC Smoke

Command:

```bash
HOOPS_SMOKE_TRACE_ID=phase-edit7d-rc-smoke \
HOOPS_SMOKE_TIMEOUT_SECONDS=540 \
ios/backend/.venv/bin/python services/editing/scripts/template_pack_smoke.py \
  --templates personal_highlight_v1 \
  --output-dir /tmp/hoopclips-phase7d-rc-smoke
```

Result:

```text
status: pass
workerUrl: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
editingUrl: https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
sourceObjectKey: uploads/8e944fcc609d405cb64eb8a0174326a9/source.mp4
editJobId: edit_6a0c52265d714fd78a5e3db5c44bca43
baseRenderJobId: render_1a5cd90c6e27493d8803928d6d753c2d
revisionId: rev_4cdc9deedc834c0aa11b2b30092f0019
revisionRenderJobId: render_65dec598307b46c6bf0172354135dfd1
```

Object keys:

```text
base final: edits/edit_6a0c52265d714fd78a5e3db5c44bca43/render_jobs/render_1a5cd90c6e27493d8803928d6d753c2d/final.mp4
base render log: edits/edit_6a0c52265d714fd78a5e3db5c44bca43/render_jobs/render_1a5cd90c6e27493d8803928d6d753c2d/render_log.json
revision final: edits/edit_6a0c52265d714fd78a5e3db5c44bca43/render_jobs/render_65dec598307b46c6bf0172354135dfd1/final.mp4
revision render log: edits/edit_6a0c52265d714fd78a5e3db5c44bca43/render_jobs/render_65dec598307b46c6bf0172354135dfd1/render_log.json
```

Base ffprobe summary:

```json
{
  "format": {
    "duration": "16.222005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "380238"
  },
  "video": {
    "codec_name": "h264",
    "width": 720,
    "height": 1280,
    "pix_fmt": "yuv420p",
    "r_frame_rate": "30/1"
  },
  "audio": {
    "codec_name": "aac"
  }
}
```

Revision ffprobe summary:

```json
{
  "format": {
    "duration": "16.222005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "375212"
  },
  "video": {
    "codec_name": "h264",
    "width": 720,
    "height": 1280,
    "pix_fmt": "yuv420p",
    "r_frame_rate": "30/1"
  },
  "audio": {
    "codec_name": "aac"
  }
}
```

Limitations:

```text
R2 render_log.json bodies were not fetched locally because R2 credentials are not configured.
The smoke still verified render log object keys, download URLs, MP4 download, and ffprobe.
No full presigned URLs were printed.
Worker deployment version lookup remains blocked by missing CLOUDFLARE_API_TOKEN/local Wrangler auth.
```

## TestFlight Build Checklist

Resolved local release settings:

```text
scheme: HoopsClips
configuration: Release
bundle id: atrak.charlie.hoopsclips
marketing version: 1.0.0
build number: 1
development team: K99RADPB9G locally; CI must provide HOOPS_DEVELOPMENT_TEAM
Info.plist: HoopsClips/App-Info.plist
cloud launch mode: disabled
```

Archive command:

```bash
xcodebuild archive \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath /tmp/HoopsClips-AIEdit-RC.xcarchive
```

Export command skeleton:

```bash
xcodebuild -exportArchive \
  -archivePath /tmp/HoopsClips-AIEdit-RC.xcarchive \
  -exportPath /tmp/HoopsClips-AIEdit-RC \
  -exportOptionsPlist ios/exportOptions.plist
```

Upload options:

```text
Xcode Organizer upload, or
xcrun altool/notarytool/App Store Connect API workflow after credentials are approved.
```

Do not upload until production release secrets and App Store Connect signing are verified.

## Draft TestFlight Release Notes

```text
HoopClips AI Edit Agent beta:
- Review detected basketball clips, then create a cloud-rendered highlight reel from Export.
- Choose Personal Highlight, Full Game Highlight, or Coach Review templates.
- Preview the rendered MP4, request quick revisions like More Hype, and share/open the result.
- Cloud rendering may take a few minutes and requires network access.
- Free beta exports include a HoopClips watermark/outro.
Known limitation: AI Edit is gated by staging/internal cloud configuration until production cutover is approved.
```

## Support And Debug Instructions

Ask beta testers to provide:

```text
app version/build
approximate render time
template selected
revision command, if any
failure message shown in app
editJobId/renderJobId/revisionId if visible in debug/support logs
whether preview loaded
whether share sheet opened
```

Support should check:

```text
render status by editJobId/renderJobId
render_log.json by object key
Cloud Run logs for safe event IDs
policy failureReason
download URL refresh events
Sentry event trail if DSN is configured
```

Never ask users to send presigned download URLs publicly.

## Known Limitations

- AI Edit rendering can take several minutes.
- Cloud rendering requires network access.
- Rendered outputs are stored temporarily for preview and sharing.
- Free users include HoopClips watermark/outro.
- AI Edit can fail on unusually long, unsupported, or policy-limited videos.
- CI deploy requires `CLOUDFLARE_API_TOKEN` before automated Worker releases.
- Production cloud config placeholders must be finalized before TestFlight cloud cutover.
- Cloud Run remains at `max-instances=1` until a controlled scaling smoke is approved.

## Validation

Commands for this branch:

```bash
git diff --check
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
npm --prefix services/control-plane run typecheck
cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts
ios/backend/.venv/bin/python services/editing/scripts/render_retention_cleanup.py
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing CODE_SIGNING_ALLOWED=NO
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Release -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO
```

Results:

```text
git diff --check: pass
services/editing unittest: pass, 24 tests
control-plane typecheck: pass
control-plane editing proxy tests: pass, 6 tests
cleanup dry-run smoke: pass, 0 candidates, 0 object keys, 0 estimated bytes
iOS Debug simulator build: pass
iOS Debug build-for-testing: pass
iOS Release simulator build: pass
final Worker-path RC smoke: pass
```

Release built Info.plist verification:

```text
HOOPSCloudLaunchMode: disabled
HOOPSCloudAnalysisBaseURL: blank
HOOPSCloudEditBaseURL: blank
CFBundleIdentifier: atrak.charlie.hoopsclips
CFBundleShortVersionString: 1.0.0
CFBundleVersion: 1
```

Notes:

```text
iOS builds still emit pre-existing Swift concurrency/deprecation warnings in analysis/export/test code.
The RC smoke did not fetch render_log.json bodies because local R2 credentials are not configured.
```

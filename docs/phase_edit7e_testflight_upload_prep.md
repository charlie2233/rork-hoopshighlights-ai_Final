# Phase Edit7e TestFlight Upload Prep

Date: 2026-05-06

Branch:

```text
codex/phase-edit7e-testflight-upload-prep
```

Base commit:

```text
1b7127c
```

Requested Phase Edit7d reference `3b7a9d6` is still in the branch ancestry. This
branch starts from the latest local Phase Edit7d RC evidence merge.

Goal:

```text
Prepare HoopClips AI Edit Agent for actual TestFlight upload by finalizing the
backend mode decision, CI deploy token requirements, feature flag safety,
archive/export commands, release notes, known limitations, and go/no-go gates
without adding product features.
```

This branch does not add templates, effects, payments, local rendering, local composition, Remotion runtime, Canva runtime, or new model work. iOS remains the control surface. Cloud analysis, edit planning, revision planning, template application, policy enforcement, durable render state, and FFmpeg rendering remain backend-owned.

## Backend Mode Decision

Recommendation:

```text
Use staging backend for the first internal TestFlight only.
Use production backend only after production cutover approval and 3-5 successful internal beta runs.
```

Current release posture:

| TestFlight lane | Backend | Status | Decision |
| --- | --- | --- | --- |
| Internal TestFlight, cloud-enabled AI Edit | staging Worker, staging Cloud Run editing, staging R2 | allowed only with an explicit staging-enabled signed build | recommended first cloud beta lane |
| Internal TestFlight, cloud-disabled safety build | no cloud AI Edit in Release | allowed now after release secrets/signing pass | safest packaging proof |
| External TestFlight | production Worker/Cloud Run/R2 | blocked | wait for production config and cutover approval |
| App Store/public | production only | blocked | out of scope for this phase |

Important build-mode note:

```text
The normal Release configuration still has HOOPS_CLOUD_LAUNCH_MODE=disabled and blank cloud URLs.
That is correct for public safety, but it means AI Edit is disabled in a default Release/TestFlight build.

To run internal TestFlight against staging, create an explicitly approved staging-enabled signed archive
using command-line build setting overrides or a future dedicated InternalStaging build configuration.
Do not silently change Release defaults.
```

## Go/No-Go Gates

| Gate | Internal staging TestFlight | External/production TestFlight |
| --- | --- | --- |
| AI Edit product loop | historical RC smoke passed; installed TestFlight proof and Worker `/v1/editing/version` refresh still required | go after production smoke |
| Staging Worker URL | historical RC smoke passed; current `/v1/editing/version` refresh still required | not applicable |
| Production Worker URL | not required | blocked, placeholder |
| Staging Cloud Run editing | historical RC smoke passed; refresh live version after deploy | not applicable |
| Production Cloud Run editing | not required | blocked, placeholder |
| Staging R2 buckets | historical RC smoke passed; object-key evidence is operator-only | not applicable |
| Production R2 buckets | not required | blocked, placeholder |
| CI Worker deploy | blocked until `CLOUDFLARE_API_TOKEN` is installed | blocked |
| iOS release signing secrets | verify in release preflight | required |
| App Store Connect upload credentials | not verified locally | required |
| R2 render log body fetch | operator-only gap; not user-flow blocker | should be verified before external beta |
| Cleanup execute | keep disabled | keep disabled until policy reviewed |

## CI Deploy Auth Checklist

Required GitHub Actions environment secret:

```text
staging / CLOUDFLARE_API_TOKEN
```

Cloudflare token scope for staging deploy automation:

```text
Account: HoopClips Cloudflare account
Workers Scripts: Edit
Account Settings: Read
D1: Edit, when running migrations
R2: Edit, when CI verifies bucket bindings or render artifacts
Workers Routes: Edit, only if route-managed deploys are added
```

Rotation plan:

```text
1. Create replacement token in the Cloudflare dashboard.
2. Update GitHub Actions staging environment secret CLOUDFLARE_API_TOKEN.
3. Run Cloud Edit Deploy Preflight.
4. Deploy Worker to staging or run wrangler whoami validation.
5. Revoke old token.
```

Required GCP deploy identity:

```text
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_DEPLOY_SERVICE_ACCOUNT
GCP_PROJECT_ID
GCP_REGION
```

Required GCP roles:

```text
Cloud Run Admin
Artifact Registry Writer
Cloud Build submit permissions
Secret Manager Secret Accessor for deploy-time checks
Service Account User on the Cloud Run runtime service account, if required
Viewer on the project for preflight describe commands
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

Do not print or commit secret values.

## Config Matrix

| Config key / surface | Staging | Production | Status |
| --- | --- | --- | --- |
| iOS bundle ID | `atrak.charlie.hoopsclips` | `atrak.charlie.hoopsclips` unless App Store Connect differs | verify in App Store Connect |
| iOS version/build | `1.0.0` / `1` | same currently | bump build number before upload if build `1` already exists |
| iOS `HOOPS_CLOUD_LAUNCH_MODE` | `enabled` in Debug | `disabled` in Release | safe default verified |
| iOS `HOOPS_CLOUD_EDIT_BASE_URL` | staging Worker in Debug | blank in Release | safe default verified |
| iOS `HOOPS_CLOUD_ANALYSIS_BASE_URL` | local debug default unless overridden | blank in Release | safe default verified |
| Worker service | `hoopsclips-control-plane-staging` | not defined | production blocked |
| Worker URL | `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev` | placeholder | production blocked |
| Cloud Run editing service | `hoopclips-editing-staging` | placeholder | production blocked |
| Cloud Run editing URL | `https://hoopclips-editing-staging-npya43jiia-uc.a.run.app` | placeholder | production blocked |
| Cloud Run revision | `hoopclips-editing-staging-00022-btg` observed locally | not applicable | staging observed |
| Cloud Run git SHA | `/version` reports `d00d0d5` | not applicable | staging observed |
| Cloud Run max instances | `1` | TBD | do not raise without scaling smoke |
| R2 upload bucket | `hoopsclips-uploads-staging` | `hoopsclips-uploads` placeholder | production blocked |
| R2 results bucket | `hoopsclips-results-staging` | `hoopsclips-results` placeholder | production blocked |
| D1 database | `hoopsclips-control-plane-staging` | placeholder ID in base config | production blocked |
| Sentry iOS | configured through release secret | production DSN required | verify in release preflight |
| Sentry backend | optional DSN/env | production DSN/env TBD | production blocked |
| Statsig | safe backend defaults | server/client env TBD | production blocked |
| RevenueCat | Debug test key; Release secret present locally | production key required | verify in release preflight |
| Google client ID | Release value present locally | production value required | verify in release preflight |
| Firebase Auth API key | Release value present locally | production value required | verify in release preflight |
| Privacy/Terms URLs | Release values present locally | production values required | verify in release preflight |

## Feature Flag Safety

Flags and current safety behavior:

| Flag | Current backing | Safe if missing? |
| --- | --- | --- |
| `ai_edit_enabled` | `HOOPS_AI_EDIT_ENABLED` / backend defaults | yes, Release iOS remains cloud-disabled until cutover |
| `ai_edit_live_render_enabled` | Worker editing URL/secret plus iOS cloud launch mode | yes, missing config disables/unavailable state |
| `ai_edit_templates_enabled` | `HOOPS_AI_EDIT_TEMPLATE_PACK_ENABLED` / backend defaults | yes, backend gates template endpoint behavior |
| `ai_edit_revisions_enabled` | `HOOPS_AI_EDIT_REVISION_ENABLED` / backend defaults | yes, backend returns revision-disabled failure |
| `ai_edit_free_tier_limits_enabled` | plan-tier policy registry | yes, free-tier policy enforced by default |
| `ai_edit_cleanup_enabled` | cleanup command | yes, dry-run default; execute requires explicit `--execute` |
| `ai_edit_max_daily_renders` | `HOOPS_AI_EDIT_MAX_DAILY_RENDERS` or plan policy | yes, falls back to plan policy |
| `ai_edit_max_render_seconds` | plan-tier policy registry | yes, falls back to plan policy |

Expected missing-config behavior:

```text
iOS hides/disables AI Edit when cloud edit config is unavailable.
iOS shows a friendly unavailable/failure state when backend policy rejects or render fails.
iOS never falls back to local video rendering/composition.
Backend rejects disabled feature paths with structured failureReason.
```

## TestFlight Archive Prep

Resolved local release settings:

```text
scheme: HoopsClips
configuration: Release
bundle identifier: atrak.charlie.hoopsclips
marketing version: 1.0.0
build number: 1
signing style: Automatic
development team: configured locally; CI must provide HOOPS_DEVELOPMENT_TEAM
Info.plist: HoopsClips/App-Info.plist
cloud launch mode: disabled
cloud analysis URL: blank
cloud edit URL: blank
```

Safe cloud-disabled archive command:

```bash
xcodebuild archive \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath /tmp/HoopsClips-AIEdit-RC.xcarchive
```

Internal staging AI Edit archive command, only after explicit approval:

```bash
xcodebuild archive \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath /tmp/HoopsClips-AIEdit-InternalStaging.xcarchive \
  HOOPS_CLOUD_LAUNCH_MODE=enabled \
  HOOPS_CLOUD_EDIT_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

Upload/export command:

```bash
xcodebuild -exportArchive \
  -archivePath /tmp/HoopsClips-AIEdit-RC.xcarchive \
  -exportPath /tmp/HoopsClips-AIEdit-RC \
  -exportOptionsPlist ios/exportOptions.testflight-internal.example.plist
```

The example export options file uses:

```text
method: app-store-connect
destination: upload
testFlightInternalTestingOnly: true
signingStyle: automatic
```

Actual upload requires App Store Connect credentials through Xcode account state or `xcodebuild` authentication key flags. Those credentials are not committed.

## Draft TestFlight Notes

```text
HoopClips AI Edit Agent beta:
- Create a cloud-rendered basketball highlight reel from the Export page.
- Choose a template style: Personal Highlight, Full Game Highlight, or Coach Review.
- Preview the rendered MP4, request quick revisions like More Hype, and share/open the result.
- Cloud rendering can take a few minutes and requires network access.
- Rendered videos are stored temporarily for preview and sharing.
- Free/internal beta exports may include a HoopClips watermark/outro.
- Known failures show a retry or friendly failure message instead of raw backend errors.
```

## Privacy And Storage Copy

Verified beta-facing copy in Export AI Edit:

```text
Hoopclips uploads the selected source to cloud services, creates the edit there,
and stores the finished MP4 temporarily for preview and sharing.
```

Retention copy:

```text
Rendered videos are retained temporarily for preview, download, sharing, support,
and abuse/cost controls. Cleanup execute mode is not enabled by default, so do
not promise immediate deletion timing until destructive cleanup is approved and monitored.
```

Failure/retry copy:

```text
Cloud rendering may fail or time out for unusually long, unsupported, or policy-limited videos.
When safe, users can retry or choose a shorter edit.
```

## R2 Render Log Body Note

Current support posture:

```text
Render log object keys are exposed by render status and RC smoke evidence.
Fetching render_log.json bodies requires operator R2 credentials.
The user-facing app flow does not need render log body access.
No full presigned URLs should be logged or shared.
An admin/operator render-log endpoint can be considered later, but is out of scope for Phase Edit7e.
```

## Final Smoke Evidence

This is historical RC smoke evidence. Storage object-key fields below are intentionally redacted in this launch-readiness reconciliation pass; use operator logs or R2/audit tooling for exact object-key lookup when needed.

Latest full Worker-path RC smoke:

```text
source: Phase Edit7d
status: pass
Worker -> Cloud Run editing -> redacted R2 object-key evidence -> download URL -> ffprobe
Worker URL: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
Cloud Run editing URL: https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
sourceObjectKey: uploads/<redacted>/source.mp4
base editJobId: edit_caf79ea7c9c34e3e96e4032818a4e645
base renderJobId: render_95210e7c55ac4c68a9c80c050922ca9c
base outputObjectKey: edits/<redacted>/render_jobs/<redacted>/final.mp4
base renderLogObjectKey: edits/<redacted>/render_jobs/<redacted>/render_log.json
revisionId: rev_1f3d2694b1714403b2a3f57df0f799c5
revision renderJobId: render_8a94b0188e7445a39eed6215ecde2798
revision outputObjectKey: edits/<redacted>/render_jobs/<redacted>/final.mp4
revision renderLogObjectKey: edits/<redacted>/render_jobs/<redacted>/render_log.json
base ffprobe: duration 16.222005s, size 379466 bytes, H.264 720x1280 yuv420p 30fps, AAC
revision ffprobe: duration 16.222005s, size 374403 bytes, H.264 720x1280 yuv420p 30fps, AAC
summaryPath: /private/tmp/hoopclips-phase7d-rc-smoke-rerun/template_pack_smoke_summary.json
```

This branch did not rerun the full live render because it does not change render contracts or cloud renderer behavior. It focuses on packaging/upload readiness. Re-run the live smoke immediately before actual TestFlight upload if a deployment or config value changes.

## Known Limitations

- Default Release/TestFlight build keeps cloud AI Edit disabled until cutover approval.
- Internal staging TestFlight requires explicit staging-enabled build settings or a future dedicated build configuration.
- `CLOUDFLARE_API_TOKEN` is still required for CI Worker deploy automation.
- Production Worker, Cloud Run editing, R2, D1, Statsig, and backend Sentry values remain placeholders.
- R2 render log bodies require operator credentials; object keys are operator-only evidence and should not be pasted into docs, tickets, or user-facing support.
- Cloud Run remains `max-instances=1` until controlled scaling smoke is approved.
- Cleanup execute mode should remain disabled until retention policy is reviewed.
- Actual App Store Connect upload credentials are not configured in this repo.

## Validation

Commands for this branch:

```bash
git diff --check
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
npm --prefix services/control-plane run typecheck
cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts
ios/backend/.venv/bin/python services/editing/scripts/render_retention_cleanup.py
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Release -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing CODE_SIGNING_ALLOWED=NO
xcodebuild archive -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Release -destination 'generic/platform=iOS' -archivePath /tmp/HoopsClips-AIEdit-RC.xcarchive CODE_SIGNING_ALLOWED=NO
```

Results:

| Check | Result | Notes |
| --- | --- | --- |
| `git diff --check` | passed | no whitespace errors after final doc update |
| Export options / app plist lint | passed | `ios/exportOptions.testflight-internal.example.plist` and `ios/HoopsClips/App-Info.plist` are valid plists |
| `services.editing.tests.test_editing_service` | passed | 24 unittest cases |
| Control-plane typecheck | passed | `npm --prefix services/control-plane run typecheck` |
| Control-plane editing proxy tests | passed | 6 `node:test` cases |
| R2 cleanup dry-run | passed | dry-run reported 0 candidates and no deletion |
| iOS Debug simulator build | passed | warnings only; no errors |
| iOS Release simulator build | passed | warnings only; no errors |
| iOS Debug build-for-testing | passed | warnings only; no errors |
| Release plist safety check | passed | built Release simulator app has `HOOPSCloudLaunchMode=disabled` and blank cloud URLs |
| Staging override check | passed | command-line Release overrides resolve `HOOPS_CLOUD_LAUNCH_MODE=enabled` and staging Worker URLs |
| Unsigned archive compile check | passed | `/tmp/HoopsClips-AIEdit-RC.xcarchive` created with `CODE_SIGNING_ALLOWED=NO` |

Observed pre-existing iOS warnings:

```text
Swift concurrency warnings remain in analysis/export services and iOS tests.
AVAssetExportSession deprecation warnings remain in VideoExportService.
These warnings were not introduced by Phase Edit7e and are not changed in this release-prep branch.
```

Archive/upload status:

```text
The unsigned archive compile check passed locally.
A real TestFlight upload still requires App Store Connect authentication and signing/export credentials.
```

# Phase Edit7f Internal TestFlight Upload Prep

Date: 2026-05-06

Branch:

```text
codex/phase-edit7f-internal-testflight-upload
```

Base commit:

```text
7a56f27
```

Requested Phase Edit7e reference `b986fb4` is in the branch ancestry. This branch starts from the latest local Phase Edit7e head because it includes the follow-up release-evidence clarification commit.

Goal:

```text
Prepare HoopClips AI Edit Agent for first internal TestFlight upload using the staging backend, while keeping production cutover blocked until approval.
```

This phase does not add templates, video effects, payments, local rendering, local composition, Remotion runtime, Canva runtime, manual timeline editing, or new model work. The iOS app remains the control surface. Cloud analysis, edit planning, revision planning, template policy, durable render state, and FFmpeg rendering remain backend-owned.

## Backend Mode Decision

Recommended first internal beta mode:

```text
Internal TestFlight
-> staging Worker
-> staging Cloud Run editing service
-> staging R2 upload/results buckets
-> AI Edit enabled for internal testers only
```

Production cutover remains blocked until production Worker, Cloud Run, R2, Sentry, Statsig, RevenueCat, Google, and release deploy credentials are approved and verified.

| Lane | Backend | Decision | Status |
| --- | --- | --- | --- |
| Internal TestFlight, AI Edit enabled | staging | recommended | ready after signed archive/upload credentials |
| Internal TestFlight, cloud-disabled packaging proof | none | allowed | safe Release default |
| External TestFlight | production | blocked | production placeholders remain |
| App Store/public | production | blocked | out of scope |

Release default remains conservative:

```text
Release HOOPS_CLOUD_LAUNCH_MODE=disabled
Release HOOPS_CLOUD_EDIT_BASE_URL is blank
Release HOOPS_CLOUD_ANALYSIS_BASE_URL is blank
```

An internal staging TestFlight archive must be explicitly built with staging cloud overrides or a future dedicated InternalStaging configuration. Do not silently enable cloud AI Edit in the default Release configuration.

## Config Matrix Summary

| Config key / surface | Internal staging TestFlight | Production / external beta | Status |
| --- | --- | --- | --- |
| Bundle identifier | `atrak.charlie.hoopsclips` | `atrak.charlie.hoopsclips` unless App Store Connect differs | verify ASC app record |
| Marketing version | `1.0.0` | `1.0.0` | unchanged |
| Build number | `2` | `2` after this branch | incremented from `1` |
| Apple team | `K99RADPB9G` | `K99RADPB9G` unless ASC differs | local build settings verified |
| Release cloud launch mode | explicit staging override required | disabled by default | safe |
| Staging Worker URL | `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev` | not applicable | latest RC smoke passed |
| Production Worker URL | not required | placeholder | blocked |
| Staging Cloud Run editing URL | `https://hoopclips-editing-staging-npya43jiia-uc.a.run.app` | not applicable | latest RC smoke passed |
| Production Cloud Run editing URL | not required | placeholder | blocked |
| Staging R2 buckets | `hoopsclips-uploads-staging`, `hoopsclips-results-staging` | not applicable | latest RC smoke passed |
| Production R2 buckets | not required | placeholders | blocked |
| Sentry | staging/internal env | production env required | verify before external beta |
| Statsig | staging/internal env or safe defaults | production env required | verify before external beta |
| RevenueCat | release secret required | production key required | release preflight gate |
| Google client ID | release secret required | production value required | release preflight gate |
| AI Edit feature flags | enabled for internal/staging only | gated/off until cutover | safe default |
| Cleanup execute | disabled | disabled | dry-run only |

## CI Deploy Token Checklist

Required GitHub Actions staging environment secret:

```text
CLOUDFLARE_API_TOKEN
```

Required Cloudflare scope:

```text
HoopClips Cloudflare account
Workers Scripts: Edit
Account Settings: Read
D1: Edit when running migrations
R2: Edit when verifying bucket bindings/artifacts
Workers Routes: Edit only if route-managed deploys are added
```

Required GCP CI inputs:

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
Project Viewer for preflight describe commands
```

Deploy commands remain:

```bash
cd services/control-plane
npx wrangler deploy --env staging

gcloud builds submit . \
  --project="$GCP_PROJECT_ID" \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG="$GITHUB_SHA"
```

Rollback commands remain:

```bash
gcloud run services update-traffic hoopclips-editing-staging \
  --project="$GCP_PROJECT_ID" \
  --region="$GCP_REGION" \
  --to-revisions <previous-revision>=100

cd services/control-plane
npx wrangler rollback --env staging
```

No secret values are stored in this repo.

## Signing And Upload Audit

Resolved local build settings:

| Item | Value |
| --- | --- |
| Project | `ios/HoopsClips.xcodeproj` |
| Scheme | `HoopsClips` |
| Configuration | `Release` |
| Bundle ID | `atrak.charlie.hoopsclips` |
| Marketing version | `1.0.0` |
| Previous build number | `1` |
| New build number | `2` |
| Signing style | Automatic |
| Development team | `K99RADPB9G` |
| Export options | `ios/exportOptions.testflight-internal.plist` |
| Upload method | App Store Connect upload through Xcode Organizer, Transporter, or `xcodebuild -exportArchive` when credentials are installed |

Local credential audit:

```text
codesigning identities: Apple Development only
Apple Distribution identity: not found locally
App Store Connect API key/env: not found locally
Fastlane config: not present
Cloudflare/GCP deploy env vars: not found locally
```

Current upload blocker:

```text
Archive compile can be validated locally.
Signed export/upload is blocked until Apple Distribution signing and App Store Connect upload credentials are available.
```

Do not commit signing certificates, private keys, app-specific passwords, issuer IDs, API keys, or CI tokens.

## Build And Archive Commands

Release simulator compile:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-phase7f-release-build \
  CODE_SIGNING_ALLOWED=NO \
  build
```

Unsigned internal staging archive compile:

```bash
xcodebuild archive \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath /tmp/HoopsClips-AIEdit-InternalStaging-1.0.0-2.xcarchive \
  CODE_SIGNING_ALLOWED=NO \
  HOOPS_CLOUD_LAUNCH_MODE=enabled \
  HOOPS_CLOUD_EDIT_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

Signed upload command after credentials are installed:

```bash
xcodebuild -exportArchive \
  -archivePath /path/to/HoopsClips.xcarchive \
  -exportOptionsPlist ios/exportOptions.testflight-internal.plist \
  -exportPath /tmp/HoopsClips-TestFlight-Export
```

Use Xcode Organizer or Transporter if App Store Connect authentication is easier locally. Do not use Fastlane unless the project intentionally adopts it later.

## Feature Flag Safety

Internal TestFlight intended values:

| Flag | Internal staging value | Safe fallback |
| --- | --- | --- |
| `ai_edit_enabled` | true | disabled/unavailable state |
| `ai_edit_live_render_enabled` | true | disabled/unavailable state |
| `ai_edit_templates_enabled` | true | backend default or disabled |
| `ai_edit_revisions_enabled` | true | backend structured failure |
| `ai_edit_free_tier_limits_enabled` | true | free policy enforced |
| `ai_edit_cleanup_enabled` | false / dry-run only | execute disabled |
| `ai_edit_max_daily_renders` | plan policy | plan policy |
| `ai_edit_max_render_seconds` | plan policy | plan policy |

If Statsig or cloud config is unavailable, AI Edit should hide, disable, or show an unavailable state. It must not fall back to local rendering.

## TestFlight Release Notes Draft

```text
HoopClips AI Edit Agent beta

- Create cloud-rendered basketball highlight reels from detected clips.
- Choose Personal Highlight, Full Game Highlight, or Coach Review templates.
- Preview, revise, and share rendered MP4s.
- Use quick revision commands like More Hype after a render.
- AI Edit uses cloud upload/rendering and temporary MP4 storage.
- Some renders may take several minutes or fail on unusual videos.
- Internal/free beta outputs may include HoopClips branding.
```

Known limitations:

```text
- Cloud rendering requires network access.
- First internal TestFlight uses staging backend, not production.
- Production backend cutover is not approved yet.
- Render cleanup execute remains disabled; cleanup dry-run is available.
- AI clip labels and template choices may still be imperfect.
- Very long or unsupported videos may be limited by policy.
- R2 render log body fetch requires operator credentials.
```

## Privacy And Storage Copy

Suggested beta-facing copy:

```text
AI Edit uploads your video to HoopClips cloud services to create a highlight reel.
Rendered MP4s are stored temporarily so you can preview, download, and share them.
Internal/free beta exports may include HoopClips branding.
Rendering may take a few minutes, and unusually long or unsupported videos may fail.
```

Retention summary:

```text
preview renders: short-lived
free/internal final renders: temporary
failed render scratch artifacts: temporary
render logs: retained longer for debugging
cleanup execute: disabled until explicitly approved
```

Do not promise immediate deletion while cleanup execute remains disabled.

## Post-Install Internal Smoke Checklist

After TestFlight processing:

```text
1. Install the TestFlight build.
2. Open HoopClips.
3. Import/upload a sample basketball video.
4. Review detected clips.
5. Navigate to Export -> AI Edit Agent.
6. Select Personal Highlight.
7. Render with staging backend.
8. Confirm MP4 preview loads.
9. Share/Open In the rendered MP4.
10. Tap More Hype.
11. Render revision.
12. Confirm revised MP4 preview loads.
13. Share/Open In revised MP4.
14. Record editJobId, renderJobId, revisionId, revisedRenderJobId, Worker version, Cloud Run revision, and any failureReason.
```

## Validation

Local validation run:

```text
git diff --check: passed
plutil -lint iOS plist files: passed
iOS Release simulator build: passed
iOS build-for-testing: passed
unsigned iOS archive compile with explicit staging overrides: passed
archive Info.plist verification: passed
```

Archive path:

```text
/tmp/HoopsClips-AIEdit-InternalStaging-1.0.0-2.xcarchive
```

Archive Info.plist verification:

```text
bundle identifier: atrak.charlie.hoopsclips
marketing version: 1.0.0
build number: 2
HOOPSCloudLaunchMode: enabled
HOOPSCloudEditBaseURL: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
HOOPSCloudAnalysisBaseURL: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

Backend services are not changed in this branch, so services/editing tests and services/control-plane typecheck are not required unless a backend file changes.

Final upload status:

```text
Upload not attempted.
Signed export/upload remains blocked by missing Apple Distribution signing and App Store Connect upload credentials.
```

## Remaining Blockers

```text
1. Apple Distribution signing/App Store Connect upload credentials are not available locally.
2. CLOUDFLARE_API_TOKEN still needs to be installed in CI for Worker deploy automation.
3. Production backend config values remain placeholders until cutover approval.
4. R2 render log body access remains operator-credential-only.
5. Real TestFlight install smoke cannot run until upload and processing succeed.
```

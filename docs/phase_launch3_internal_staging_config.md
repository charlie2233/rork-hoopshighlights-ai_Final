# Phase Launch3 Internal Staging Config

Date: 2026-05-22
Branch: `codex/phase-launch3-internal-staging-config`

## Scope

- Added a committed internal-staging xcconfig for the first cloud-enabled internal TestFlight lane.
- Added a verifier script that proves the explicit Release override resolves to the staging Worker for both analysis upload/status and AI Edit.
- Kept normal Release cloud-disabled for public/external safety.
- Did not add local video analysis, local rendering, local composition, Remotion, Canva, or any secret values.

## Why This Exists

Phase Edit7f uploaded build `3` with command-line cloud overrides:

```text
HOOPS_CLOUD_LAUNCH_MODE=enabled
HOOPS_CLOUD_EDIT_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

That worked, but it made the internal TestFlight lane depend on remembering several ad hoc flags. This phase turns the staging cloud settings into a reusable, inspectable override file:

```text
ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig
```

The file is intentionally an overlay used with `-configuration Release -xcconfig ...`. It does not include `Release.xcconfig` directly because Xcode prints values from the `-xcconfig` file at build start, and `Release.xcconfig` may include local secret values. The selected Release configuration still loads the normal project release settings; the overlay only opts into:

```text
HOOPS_APP_ENV=internal_staging
HOOPS_CLOUD_LAUNCH_MODE=internal_only
HOOPS_CLOUD_ANALYSIS_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
HOOPS_CLOUD_EDIT_BASE_URL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

Normal `Release.xcconfig` still sets:

```text
HOOPS_APP_ENV=production
HOOPS_CLOUD_LAUNCH_MODE=disabled
HOOPS_CLOUD_ANALYSIS_BASE_URL=
HOOPS_CLOUD_EDIT_BASE_URL=
```

## Internal TestFlight Build Command

Use this only for the internal staging AI Edit candidate:

```bash
xcodebuild archive \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath /tmp/HoopsClips-AIEdit-InternalStaging.xcarchive \
  -xcconfig ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig \
  -allowProvisioningUpdates
```

Then export/upload with:

```bash
xcodebuild -exportArchive \
  -archivePath /tmp/HoopsClips-AIEdit-InternalStaging.xcarchive \
  -exportPath /tmp/HoopsClips-AIEdit-InternalStaging \
  -exportOptionsPlist ios/exportOptions.testflight-internal.plist \
  -allowProvisioningUpdates
```

Do not use this config for external TestFlight or public App Store release until the production cloud cutover gates are approved.

## Config Verification

The verifier does not require signing secrets or cloud credentials:

```bash
bash ios/scripts/verify_internal_staging_config.sh
```

Expected checks:

```text
HOOPS_APP_ENV=expected
HOOPS_CLOUD_LAUNCH_MODE=expected
HOOPS_CLOUD_ANALYSIS_BASE_URL=expected
HOOPS_CLOUD_EDIT_BASE_URL=expected
PRODUCT_BUNDLE_IDENTIFIER=expected
MARKETING_VERSION=expected
CURRENT_PROJECT_VERSION=expected
INFOPLIST_FILE=expected
Internal staging Release config is explicit and cloud-enabled for staging only.
```

Built Release simulator Info.plist verification:

```bash
rm -rf /tmp/hoopclips-internal-staging-release
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-internal-staging-release \
  -xcconfig ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig \
  CODE_SIGNING_ALLOWED=NO \
  build
```

Result:

```text
internal staging Release simulator build: passed
HOOPSAppEnvironment=internal_staging
HOOPSCloudLaunchMode=internal_only
HOOPSCloudAnalysisBaseURL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
HOOPSCloudEditBaseURL=https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
CFBundleIdentifier=atrak.charlie.hoopsclips
CFBundleShortVersionString=1.0.0
CFBundleVersion=3
```

Local build output was redirected and then removed after verification so local secret settings from `LocalSecrets.xcconfig` are not retained as evidence.

## Remaining Blockers

- Real post-install TestFlight smoke still needs an online trusted iPhone with build `3` or the next internal staging build installed.
- GitHub `staging` environment still needs `CLOUDFLARE_API_TOKEN`, GCP Workload Identity, deploy service account, project, and region inputs before CI can prove real Worker deploy/rollback.
- Cloud deploy workflow pull_request checks are visible on PR #3, but manual/default-branch dispatch is unavailable until the workflow branch stack lands on `main`.
- Production Worker, Cloud Run, R2, D1, Sentry, Statsig, RevenueCat, Google, and rollback gates remain blocked for external/public cutover.
- The documented Statsig kill-switch names are not yet wired to a single runtime flag source of truth; current behavior is split across backend env/defaults and iOS URL/launch-mode availability.
- The legacy local export button remains visible in the non-AI-Edit Export surface. That is allowed as a launch-safe fallback, but post-install smoke evidence must explicitly use the AI Edit Agent cloud path.

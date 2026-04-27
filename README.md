# Hoopclips

Hoopclips is a cloud-first AI video editing product for basketball clips. The target product is HoopClips AI Edit Agent: users upload video from iOS, choose an edit style, review generated clips/edit plans, request a cloud render, preview the finished MP4, then download, save, share, or open the export in editors such as CapCut, iMovie, Adobe, Files, or Photos.

Cloud analysis, AI edit planning, and final rendering are the intended production architecture. The current public release posture keeps cloud disabled as a safety gate until production auth, storage, observability, render reliability, and Phase 4h data-truth gates are cleared.

## Current Launch Posture

- Current public-safe fallback: iOS app with local import, review, export, save, and on-device analysis while cloud gates stay locked.
- Target GA architecture: cloud analysis, cloud EditPlan generation, cloud rendering, and iOS as the control surface.
- Cloud ML/rendering path: gated off for public launch until the cutover rules below are satisfied.
- Release bundle ID: `atrak.charlie.hoopsclips`.
- Release cloud mode: `HOOPS_CLOUD_LAUNCH_MODE = disabled`.
- Release cloud base URL: empty.
- Release email/password auth: Firebase Auth via `HOOPS_FIREBASE_AUTH_API_KEY`.
- Phase 4h: labeling-only; no retrain, smoke, medium batch, or threshold changes until confirmed labels land.

## Latest Verified State

Last local verification: April 26, 2026.

- iOS unit tests: `38/38` passed.
- iOS UI tests: `7/7` passed.
- Backend guardrail tests: `6/6` passed.
- Release simulator build: passed.
- Release physical-device build: passed on the connected iPhone.
- Release physical-device install and command launch: passed for `atrak.charlie.hoopsclips`.
- GitHub Actions `Release Secrets Preflight`: passed on `main` in run `24968469454`.

Known launch blocker: the remaining human real-device smoke still needs to complete purchase/restore, Photos import, Files import, on-device analysis, review, export, save to Photos, and legal-link checks. RevenueCat configuration previously returned `Unable to load subscription options`, so App Store Connect and RevenueCat product/offering wiring must be verified before submission.

## Repo Layout

- `ios/HoopsClips/` - SwiftUI iOS app, tests, configuration, and app resources.
- `ios/backend/` - internal cloud-analysis backend scaffold and future cloud editing service home.
- `docs/architecture/video_editing_cloud_backend.md` - cloud-first HoopClips AI Edit Agent architecture.
- `docs/video_editing_repo_audit.md` - current repo audit for the cloud editing pivot.
- `skills/hoopclips-ai-edit-agent/SKILL.md` - repo-local Codex skill for cloud-backend edit-agent work.
- `ios/docs/checklists/public-launch-cloud-gated.md` - public launch checklist.
- `ios/docs/runbooks/public-launch-cloud-gated.md` - launch-day support and fallback runbook.
- `ios/docs/runbooks/firebase-auth-setup.md` - Firebase email/password auth setup.
- `ios/docs/app-store/app-review-sign-in.md` - App Review sign-in notes template.
- `ios/docs/reports/release-device-smoke-report.md` - real-device smoke evidence report.
- `.github/workflows/release-secrets-preflight.yml` - manual Release config/build preflight.

## Local Setup

Use Xcode 17 or newer with the iOS 26 SDK and an Apple Developer team that can sign `atrak.charlie.hoopsclips`.

Create the ignored local secret mirror from operator-held values:

```bash
cd /Users/hanfei/rork-hoopshighlights-ai_Final
source .localsecrets
./ios/scripts/materialize_local_secrets.sh
```

Do not commit `.localsecrets` or `ios/HoopsClips/HoopsClips/Config/LocalSecrets.xcconfig`.

## Test Commands

Run iOS unit tests:

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -only-testing:HoopsClipsTests \
  -skip-testing:HoopsClipsUITests \
  -parallel-testing-enabled NO
```

Run iOS UI tests:

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -only-testing:HoopsClipsUITests \
  -parallel-testing-enabled NO
```

Run backend tests:

```bash
python3 -m venv /tmp/hoops-backend-test-venv
/tmp/hoops-backend-test-venv/bin/python -m pip install -r ios/backend/requirements.txt pytest httpx
PYTHONPATH=ios/backend /tmp/hoops-backend-test-venv/bin/python -m pytest ios/backend/tests -q
```

Run Release simulator build:

```bash
xcodebuild build \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2'
```

Run Release device build:

```bash
xcodebuild build \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'platform=iOS,id=00008130-000A001A1178001C' \
  -allowProvisioningUpdates
```

Trigger the GitHub Release preflight:

```bash
gh workflow run release-secrets-preflight.yml --ref main
run_id=$(gh run list --workflow release-secrets-preflight.yml --branch main --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$run_id" --exit-status
```

## Public Launch Checklist

Before App Store submission:

- Confirm GitHub `production` secrets are present for signing, RevenueCat, Google, Firebase auth, and telemetry.
- Confirm Firebase Authentication has Email/Password enabled and the App Review account works in Release.
- Confirm `HOOPS_PRIVACY_POLICY_URL` and `HOOPS_TERMS_OF_SERVICE_URL` resolve in the Release build.
- Confirm Release Settings shows cloud is disabled for the current fallback launch.
- Complete the real-device smoke and update `ios/docs/reports/release-device-smoke-report.md`.
- Fix RevenueCat product/offering/package wiring if subscription options still fail to load.
- Keep cloud ML and cloud rendering disabled for public users until the cloud cutover rules pass.

## Cloud Cutover Rules

Do not make cloud ML or cloud rendering public until all of these are true:

- Production Worker/backend/dashboard contracts are hardened.
- Public authn/authz, storage, queues, render jobs, error reporting, and trace propagation are production-ready.
- Phase 4h reviewed labels are imported and the confirmed-label gate unlocks.
- Acceptor retrain happens in a dedicated branch.
- Replay passes before smoke.
- Smoke passes before a 60-80 clip medium shadow batch.
- Medium-batch metrics pass the Phase 4h promotion gate.

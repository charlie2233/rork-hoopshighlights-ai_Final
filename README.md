# hoopclips

hoopclips is an iOS app that turns basketball videos into share-ready highlight reels. The public launch path is on-device only: video import, Vision/CoreML analysis, review, export, and save all run locally on the phone.

Cloud analysis and backend moderation remain internal-only until the production cloud gates and Phase 4h data-truth gate are cleared.

## Current Launch Posture

- Public GA path: iOS app with local/on-device analysis.
- Cloud ML path: gated off for public launch.
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
- `ios/backend/` - internal cloud-analysis backend scaffold; not public launch-critical.
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
- Confirm Release Settings shows `Analysis Path = On-device only`.
- Complete the real-device smoke and update `ios/docs/reports/release-device-smoke-report.md`.
- Fix RevenueCat product/offering/package wiring if subscription options still fail to load.
- Keep cloud ML disabled for public users.

## Cloud Cutover Rules

Do not make cloud ML public until all of these are true:

- Production Worker/backend/dashboard contracts are hardened.
- Phase 4h reviewed labels are imported and the confirmed-label gate unlocks.
- Acceptor retrain happens in a dedicated branch.
- Replay passes before smoke.
- Smoke passes before a 60-80 clip medium shadow batch.
- Medium-batch metrics pass the Phase 4h promotion gate.

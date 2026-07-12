# Hoopclips

Hoopclips is a cloud-first AI video editing product for basketball clips. The target product is HoopClips AI Edit Agent: users upload video from iOS, choose an edit style, review generated clips/edit plans, request a cloud render, preview the finished MP4, then download, save, share, or open the export in editors such as CapCut, iMovie, Adobe, Files, or Photos.

Cloud analysis, AI edit planning, and final rendering are the intended production architecture. Internal beta builds can point at the staging cloud stack, while public release remains gated until production auth, storage, observability, render reliability, and the data-truth gates are cleared.

## Current Launch Posture

- PR #43 is merged into `main` at `449cd0907f62dd728741fb43a81e4f9e3815a4ff`; the enhancement integration workstream is complete on `main`.
- Build `44` launch proof baseline is `4540381752db2eb5ac22442c8f49971e0d49f6cb`, with launch testing/proof UI hidden, Settings Formspree support retained, and the next iOS TestFlight build bumped to `44`.
- Current beta launch status: staging deploy passed, live Worker/direct editing version proof passed, deterministic Worker render smoke passed, build `44` archive passed, and TestFlight upload is blocked by Apple certificate/provisioning state.
- Remaining beta blocker: the Apple account holder must clear the certificate limit / provisioning issue for bundle ID `atrak.charlie.hoopsclips`, then rerun the upload workflow. See `TESTFLIGHT_BLOCKER.md`.
- Public submission posture: no on-device analysis fallback is approved; Release requires the production cloud analysis, edit-planning, and rendering gates to pass.
- Target GA architecture: cloud analysis, cloud EditPlan generation, cloud rendering, and iOS as the control surface.
- Cloud ML/rendering path: available to internal staging/TestFlight only after signing succeeds; gated off for public launch until the cutover rules below are satisfied.
- Release bundle ID: `atrak.charlie.hoopsclips`.
- Internal staging cloud mode: `HOOPS_CLOUD_LAUNCH_MODE = internal_only`.
- Internal staging cloud base URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`.
- Release email/password auth: Firebase Auth via `HOOPS_FIREBASE_AUTH_API_KEY`.
- Release auth UI excludes local demo-code phone verification and guest-account linking; those helpers are Debug-only until a real provider-backed flow exists.
- Automatic Formspree stability/upload diagnostics are limited to Debug and `internal_only` builds; the user-submitted Settings support form remains available.
- The app bundle includes `PrivacyInfo.xcprivacy`, and the TestFlight archive workflow verifies that it is present and valid.
- Phase 4h: labeling-only; no retrain, smoke, medium batch, or threshold changes until confirmed labels land.

## Latest Verified State

Last launch-gate verification: July 11, 2026.

- Build `44` launch proof baseline: `4540381752db2eb5ac22442c8f49971e0d49f6cb`.
- PR #43: merged, `Integrate HoopClips enhancement workstream`.
- PR #46: merged, hidden launch proof/testing UI.
- PR #47: merged, Settings Formspree support banners auto-dismiss.
- PR #48: merged, next TestFlight build bumped to `44`.
- PR #49: merged, build `44` TestFlight blocker docs refreshed after archive/upload proof.
- GitHub Actions on merged `main`:
  - `Cloud Edit Deploy Preflight` push run `28992814533` on current `main` `725f6720407a2c295eed316e66437deb77442c3a`: success.
  - `iOS Internal TestFlight Upload` push/codecheck run `28992814540` on current `main`: success; this is unsigned test compilation, not a TestFlight upload.
  - `Cloud Edit Deploy Preflight` credential-check run `28317383878`: success.
  - `Cloud Edit Deploy Preflight` deploy run `28317412159`: success.
  - `iOS Internal TestFlight Upload` upload run `28470081179`: success for build `43`.
  - `iOS Internal TestFlight Upload` archive run `28756536677`: success for build `44`.
  - `iOS Internal TestFlight Upload` upload run `28756673502`: failed during signed archive because Apple certificate limit/provisioning must be repaired.
  - `iOS Internal TestFlight Upload` upload rerun `28764285946`: failed the same signed archive gate because Apple certificate limit/provisioning still must be repaired.
  - `iOS Internal TestFlight Upload` corrected automatic-signing upload rerun `28765926589`: failed the same signed archive gate because Apple certificate limit/provisioning still must be repaired.
- Live staging version proof: Worker `/v1/editing/version` and direct editing `/version` reported the merged SHA and required AI Edit/GPT feature flags.
- Deterministic Worker render smoke: passed through the active Worker render path and produced a valid H.264/AAC MP4.
- Synthetic GPT client smoke: classified as an expected synthetic-video no-clips result (`empty_clip_list`), not evidence of a Worker/direct-edit contract bug. Real basketball TestFlight smoke remains required.

Known beta launch blocker: the Apple account holder must clear the Apple certificate limit and ensure valid provisioning for bundle ID `atrak.charlie.hoopsclips`. After that, rerun the upload workflow and complete the real-basketball TestFlight smoke checklist.

## Repo Layout

- `ios/HoopsClips/` - SwiftUI iOS app, tests, configuration, and app resources.
- `ios/backend/` - internal cloud-analysis backend scaffold and future cloud editing service home.
- `docs/architecture/video_editing_cloud_backend.md` - cloud-first HoopClips AI Edit Agent architecture.
- `docs/video_editing_repo_audit.md` - current repo audit for the cloud editing pivot.
- `docs/phase_beta_launch_gates_after_pr43.md` - post-merge beta launch gate report and real-basketball TestFlight smoke checklist.
- `skills/hoopclips-ai-edit-agent/SKILL.md` - repo-local Codex skill for cloud-backend edit-agent work.
- `TESTFLIGHT_BLOCKER.md` - Apple account certificate/provisioning blocker handoff.
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
- Resolve the Apple account certificate/provisioning blocker in `TESTFLIGHT_BLOCKER.md`.
- Rerun the internal upload workflow from `main` after Apple provisioning is repaired.
- Complete the real-basketball TestFlight smoke checklist in `docs/phase_beta_launch_gates_after_pr43.md`.
- Confirm Firebase Authentication has Email/Password enabled and the App Review account works in Release.
- Confirm `HOOPS_PRIVACY_POLICY_URL` and `HOOPS_TERMS_OF_SERVICE_URL` resolve in the Release build.
- Confirm public Release Settings keeps public cloud gates locked unless a separate public cutover decision has been made.
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

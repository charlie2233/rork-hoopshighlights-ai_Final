# Hoopclips

Hoopclips is a cloud-first AI video editing product for basketball clips. The target product is HoopClips AI Edit Agent: users upload video from iOS, choose an edit style, review generated clips/edit plans, request a cloud render, preview the finished MP4, then download, save, share, or open the export in editors such as CapCut, iMovie, Adobe, Files, or Photos.

Cloud analysis, AI edit planning, and final rendering are the intended production architecture. Internal beta builds can point at the staging cloud stack, while public release remains gated until production auth, storage, observability, render reliability, and the data-truth gates are cleared.

## Current Launch Posture

- PR #43 is merged into `main` at `449cd0907f62dd728741fb43a81e4f9e3815a4ff`; the enhancement integration workstream is complete on `main`.
- Builds `44` through `49` established signing, ownership, upload recovery, adaptive multipart, and simplified upload/AI Edit baselines. PR #74 is merged into `main` at `6c6ae4ffc267d7b4853dbb955c512f3a098fe601`, released as internal TestFlight build `50`.
- Current internal-beta status: staging deploy run `29632345235` passed live Worker/direct editing version proof, and the deterministic Worker render smoke passed. Build `55` keeps the direct-to-R2 byte-progress/shared-session path and fixes expired saved multipart uploads by renewing missing-part targets without discarding completed chunks. Signed upload run `29706183087` and read-only status run `29706397510` prove current main SHA `bc7218c6ca412cdc1241dd74772b8f84a27a2597` is available in App Store Connect as internal TestFlight build `1.0.0 (55)`, `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, and ready for internal testers.
- PR #60 is merged. iOS sends its scoped `installId` on analysis polling, and the deployed strict Worker rejects missing or mismatched ownership on analysis job reads and cancellation. A live create/read/cancel ownership smoke passed after deployment.
- Build `49` was installed and launched on a trusted iPhone, then reproduced the large-upload defect with a real 380 MB source: 24 parts were planned, upload reached about 15%, background transfer handed off, and the saved upload expired before any part completed. Build `50` is deployed with one-hour signed upload leases, bounded multipart lease renewal, and active/completed background-session reconciliation. Live capabilities and a fresh secret-safe presign probe both confirmed a 3,600-second lease.
- Apple account agreements and certificates are active, and build `55` proved automatic signing, archive, provisioning, upload, processing, and internal TestFlight availability. Apple signing is not the current blocker; see `TESTFLIGHT_BLOCKER.md`.
- App Store submission is not ready yet. The latest available internal TestFlight build must pass the installed real-basketball upload-through-export smoke, and the human-reviewed 85% team/highlight accuracy report remains an independent hard gate.
- Production Release preflight run `29639140468` passed all required input checks, production-compatible RevenueCat validation, Release cloud-mode validation, an unsigned Release simulator build, and built `Info.plist` wiring checks. This is configuration/build proof only; it is not a signed production archive, App Store upload/submission, installed-device proof, or public cloud cutover proof.
- Public submission posture: no on-device analysis fallback is approved; Release requires the production cloud analysis, edit-planning, and rendering gates to pass.
- Target GA architecture: cloud analysis, cloud EditPlan generation, cloud rendering, and iOS as the control surface.
- Cloud ML/rendering path: available to internal staging/TestFlight; gated off for public launch until the cutover rules below are satisfied.
- Release bundle ID: `atrak.charlie.hoopsclips`.
- Internal staging cloud mode: `HOOPS_CLOUD_LAUNCH_MODE = internal_only`.
- Internal staging cloud base URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`.
- Release email/password auth: Firebase Auth via `HOOPS_FIREBASE_AUTH_API_KEY`.
- Release auth UI excludes local demo-code phone verification and guest-account linking; those helpers are Debug-only until a real provider-backed flow exists.
- Automatic Formspree stability/upload diagnostics are limited to Debug and `internal_only` builds; the user-submitted Settings support form remains available.
- The app bundle includes `PrivacyInfo.xcprivacy`, and the TestFlight archive workflow verifies that it is present and valid.
- Signed archive and production Release preflights reject RevenueCat Test Store keys without printing key contents.
- Phase 4h: labeling-only; no retrain, smoke, medium batch, or threshold changes until confirmed labels land.

## Latest Verified State

Last launch-gate verification: July 19, 2026.

- Build `44` launch proof baseline: `4540381752db2eb5ac22442c8f49971e0d49f6cb`.
- PR #43: merged, `Integrate HoopClips enhancement workstream`.
- PR #46: merged, hidden launch proof/testing UI.
- PR #47: merged, Settings Formspree support banners auto-dismiss.
- PR #48: merged, next TestFlight build bumped to `44`.
- PR #49: merged, build `44` TestFlight blocker docs refreshed after archive/upload proof.
- PR #58: merged, launch privacy/auth/telemetry hardening and Worker dependency cleanup.
- PR #59: merged at `45c383a91d6b8223a33032593a839e72e041b955`, focused iOS tests and serial-bound automatic-signing certificate cleanup.
- PR #60: merged at `51df354cf945069ef55a13f5f0ec50a3065fc53c`, install-bound analysis job reads/cancellation and build `45` compatibility.
- PR #62: merged at `22e24d35b32e784b0d6f9e290504118e965fa105`, build `46` upload-expiry recovery, team-scan reliability, smoke-tooling fixes, and launch UX polish.
- PR #63: merged at `c4a9776be82787551efd25808516775f891468bb`, read-only App Store Connect build-status proof without archive/signing side effects.
- PR #65: merged at `cb7d8f3c946a6933f52ad18255318c8c4ae3e151`, adaptive multipart planning, path-aware concurrency, safe retry staging, build `47`, and a seven-test upload-policy CI lane.
- PRs #67-#70: merged upload UI simplification, persisted AI Edit state, active-session recovery, and build `48` preparation.
- PR #71: merged at `87688527d61c9e87c49a7ff322b4705e261afa43`, internal TestFlight build `48` preparation.
- PR #72: merged at `9b185bbcd839f28caf955048a9f7d1fc2e72cdb5`, simplified AI Edit workflow feedback.
- PR #73: merged at `2affd1d0049434cda9c3026cd7db77c003b14852`, internal TestFlight build `49` preparation.
- PR #74: merged at `6c6ae4ffc267d7b4853dbb955c512f3a098fe601`, one-hour upload leases, bounded multipart renewal, background-session-first resume recovery, build `50`, focused tests, and Release RevenueCat Test Store safeguards.
- PR #80: merged at `ca82e6b8552844c149f84157b043bf8f0d6c7f46`, AI Edit selected-style polish.
- PR #81: merged at `60eda29b7989e97a93ebdf973c0d80446caa07bf`, build `51` TestFlight prep and proof docs.
- PR #85: merged at `202b56c5d332529b7bae0006eb743f45bccd9b70`, upload pipeline banner declutter and fresh-upload wording.
- PR #86: merged at `fdb482d334b0a063a508e3e52c843dfa32ecd906`, build `52` TestFlight prep for current-main phone smoke.
- PR #87: merged at `f46705959eb1d792e93d03999eb43c828de114f0`, build `52` archive metadata guard correction.
- PR #92: merged at `f52f443198638d79dce81e5a2d7e4aba117a68fa`, streamlined AI Edit studio and progress UI with focused policy tests.
- PR #93: merged at `55a402b4b6cc48038306af5eed72367adab15bbf`, build `53` archive/status guard updates for the current-main TestFlight candidate.
- PRs #94-#97: merged build `53` proof corrections, private Mac beta recommendation, and cloud AI Edit resume recovery.
- PR #98: merged at `0e003629d3aa57d38be5bbf7647219553722a68e`, true byte-transfer upload progress.
- PR #99: merged at `0eda72e527322afdb9ccbf15e51e414d05a5cdcc`, shared-session multipart throughput and recovery improvements.
- PR #100: merged at `e72ebac3b1469387aa08af370395f887d8cd4e52`, canonical asset-first upload routes with legacy fallback compatibility.
- PR #101: merged at `409e5c0c5f9700c3c75006804e7d5bdbe163b797`, signed-archive readiness proof recognition without treating archive proof as upload proof.
- PR #102: merged at `80d2405582042da44cfec92022ab3a33212851b6`, internal TestFlight build `54` preparation.
- PR #108: merged at `5ed46d26b023e40dde737fcd5597f61a40dcadf0`, expired canonical-asset multipart lease renewal and build `55` preparation.
- PR #109: merged at `bc7218c6ca412cdc1241dd74772b8f84a27a2597`, shared backend accuracy-gate documentation; this is the exact source SHA archived for build `55`.
- GitHub Actions on merged `main`:
  - `Cloud Edit Deploy Preflight` push run `29632159204`: success on build `50` main SHA `6c6ae4ffc267d7b4853dbb955c512f3a098fe601`.
  - `iOS Internal TestFlight Upload` push/codecheck run `29632159207`: success; all 12 focused tests passed.
  - `Cloud Edit Deploy Preflight` deploy run `29632345235`: success; staging editing and Worker deploy/version proof passed for the build `50` main SHA.
  - `iOS Internal TestFlight Upload` upload run `29632723114`: success for build `50`; signed archive, metadata/privacy verification, upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29636059497`: success; build `50` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, and ready for internal testing.
  - `iOS Internal TestFlight Upload` push/codecheck run `29644908038`: success for merged build `51` main; internal staging build settings, export options, and 12 focused simulator tests passed.
  - `iOS Internal TestFlight Upload` upload run `29644918870`: success for build `51`; signed archive, metadata/privacy verification, App Store Connect upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29645129050`: success; build `51` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
  - `iOS Internal TestFlight Upload` push/codecheck run `29655523209`: success for build `52` prep on merged main.
  - `iOS Internal TestFlight Upload` upload run `29655548305`: failed after the signed archive passed because the workflow metadata guard still expected build `51`; no App Store upload was attempted from that failed run.
  - `iOS Internal TestFlight Upload` push/codecheck run `29656404272`: success after PR #87 corrected the build `52` metadata guard.
  - `iOS Internal TestFlight Upload` upload run `29656420482`: success for build `52`; signed archive, metadata/privacy verification, App Store Connect upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29656700078`: success; build `52` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
  - `iOS Internal TestFlight Upload` push/codecheck run `29667213808`: success for build `53` on merged main SHA `55a402b4b6cc48038306af5eed72367adab15bbf`.
  - `iOS Internal TestFlight Upload` upload run `29667373531`: success for build `53`; signed archive, metadata/privacy verification, App Store Connect upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29667648668`: success; build `53` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
  - `iOS Internal TestFlight Upload` upload run `29701267324`: success for build `54` on merged main SHA `80d2405582042da44cfec92022ab3a33212851b6`; signing capacity, signed archive, metadata/privacy verification, upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29701467040`: success; build `54` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
  - `Cloud Edit Deploy Preflight` push run `29706005325`: success on the PR #108 merged main SHA.
  - `iOS Internal TestFlight Upload` push/codecheck run `29706005364`: success; all 14 focused tests passed for build `55` source.
  - `iOS Internal TestFlight Upload` upload run `29706183087`: success for build `55` on current main SHA `bc7218c6ca412cdc1241dd74772b8f84a27a2597`; signing capacity, signed archive, metadata/privacy verification, upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29706397510`: success; build `55` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
  - `Release Secrets Preflight` run `29639140468`: success; required production inputs, production-compatible RevenueCat configuration, Release cloud mode, unsigned Release simulator compilation, and built `Info.plist` wiring passed without exposing secret values.
  - `iOS Internal TestFlight Upload` push/codecheck run `29623096223`: success for merged build `49` main.
  - `iOS Internal TestFlight Upload` upload run `29623108647`: success for build `49`; signed archive, metadata/privacy verification, upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29623416437`: success; the read-only Apple API proof found build `49` and confirmed internal-testing availability.
  - `Cloud Edit Deploy Preflight` push run `29448705938` on `cb7d8f3c946a6933f52ad18255318c8c4ae3e151`: success.
  - `iOS Internal TestFlight Upload` push/codecheck run `29448706013`: success; all seven focused upload-policy tests passed.
  - `Cloud Edit Deploy Preflight` deploy run `29449140849`: success; staging editing and Worker deploy/version proof passed for the build `47` app SHA.
  - `iOS Internal TestFlight Upload` upload run `29449525744`: success for build `47`; signed archive, metadata/privacy verification, upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29450181533`: success; the read-only Apple API proof found build `47` and confirmed internal-testing availability.
  - `Cloud Edit Deploy Preflight` push run `29443527257` on `22e24d35b32e784b0d6f9e290504118e965fa105`: success.
  - `Cloud Edit Deploy Preflight` deploy run `29443552918`: success; staging editing and Worker deploy/version proof passed for the build `46` app SHA.
  - `iOS Internal TestFlight Upload` push/codecheck run `29443528171`: success; all six focused tests passed.
  - `iOS Internal TestFlight Upload` upload run `29443559399`: success for build `46`; signed archive, metadata/privacy verification, upload, and runner-owned certificate cleanup passed.
  - `iOS Internal TestFlight Upload` status run `29445202395`: success; the read-only Apple API proof found build `46` and confirmed internal-testing availability.
  - `Cloud Edit Deploy Preflight` push run `29311128829` on merged `main` `51df354cf945069ef55a13f5f0ec50a3065fc53c`: success.
  - `iOS Internal TestFlight Upload` push/codecheck run `29311128820` on merged `main`: success; all six focused tests passed.
  - `iOS Internal TestFlight Upload` upload run `29311514901`: success for build `45`; signed archive, metadata/privacy checks, upload, and runner-owned certificate cleanup passed.
  - `Cloud Edit Deploy Preflight` deploy run `29312118314`: success for the strict build `45` Worker/direct editing baseline; staging Worker version `640ca379-99c7-43fa-815a-b1ec9a15f5a6` was verified.
  - `Cloud Edit Deploy Preflight` push run `29309388677` on merged `main` `45c383a91d6b8223a33032593a839e72e041b955`: success.
  - `iOS Internal TestFlight Upload` push/codecheck run `29309388686` on merged `main`: success; all six focused tests passed.
  - `iOS Internal TestFlight Upload` archive-only run `29309860620`: success for build `44`; upload was intentionally skipped and the runner-owned signing certificate was revoked.
  - `Cloud Edit Deploy Preflight` push run `29181429497` on the earlier PR #58 baseline `7a0af43cc21acbe57fa7ba28b4efe9764c3e397e`: success.
  - `iOS Internal TestFlight Upload` push/codecheck run `29181429487` on that PR #58 baseline: success; this is unsigned test compilation, not a TestFlight upload.
  - `Cloud Edit Deploy Preflight` credential-check run `28317383878`: success.
  - `Cloud Edit Deploy Preflight` deploy run `28317412159`: success.
  - `iOS Internal TestFlight Upload` upload run `28470081179`: success for build `43`.
  - `iOS Internal TestFlight Upload` archive run `28756536677`: success for build `44`.
  - `iOS Internal TestFlight Upload` upload run `28756673502`: failed during signed archive because Apple certificate limit/provisioning must be repaired.
  - `iOS Internal TestFlight Upload` upload rerun `28764285946`: failed the same signed archive gate because Apple certificate limit/provisioning still must be repaired.
  - `iOS Internal TestFlight Upload` corrected automatic-signing upload rerun `28765926589`: failed the same signed archive gate because Apple certificate limit/provisioning still must be repaired.
  - `iOS Internal TestFlight Upload` diagnostic upload run `29297858325`: confirmed ten stale API-created development certificates were still consuming the Apple account limit.
  - `iOS Internal TestFlight Upload` upload run `29298033420`: success for build `44`; signed archive, archive metadata/privacy checks, and App Store Connect upload all passed.
- App Store Connect build proof: `1.0.0 (55)` is available for internal TestFlight testing and matches archived main SHA `bc7218c6ca412cdc1241dd74772b8f84a27a2597`. Installed phone smoke remains unproven because the trusted iPhone must install/update build `55` from TestFlight before the real-basketball smoke.
- Live staging version proof: Worker `/v1/editing/version` and direct editing `/version` reported `6c6ae4ffc267d7b4853dbb955c512f3a098fe601` and the required AI Edit/GPT feature flags. Live analysis capabilities and a fresh presign probe reported a 3,600-second signed upload lease.
- Deterministic Worker render smoke: passed through the active Worker render path and produced a valid H.264/AAC MP4.
- Real-basketball cloud scan after the build `46` deploy: three consecutive team scans detected black/white teams and queued selected-team analysis; an all-teams collection completed with eight clips.
- Live analysis ownership smoke: missing owner returned `400`, a mismatched owner returned `403`, the matching owner could read and cancel its job, and the cancelled state remained readable only to that owner.
- Synthetic GPT client smoke: classified as an expected synthetic-video no-clips result (`empty_clip_list`), not evidence of a Worker/direct-edit contract bug. Real basketball TestFlight smoke remains required.
- Real-device build `49` upload smoke: installed and launched successfully, then failed near 15% on a 380 MB source. The app created 24 16 MiB parts and four background sessions, but the 15-minute saved plan expired with `0/24` completed parts. This is classified as an upload lease/background reconciliation bug, not a detection-threshold problem.
- Real-video quality diagnostic: one completed staging run returned 11 clips; conservative matching against prior reviewed moments found two known highlights and nine known negatives. Auto-keep selected one known highlight and eight negatives while missing the other known highlight. This does not satisfy the 85% gate and thresholds were not weakened.
- Build `55` proof: carries build `54` throughput/routing work and renews expired canonical-asset multipart targets while preserving saved completed chunks. Signed upload/status proof passed; installed phone proof remains required for current main.
- Current selected-white staging probe: team scan found black/yellow and white/red teams and selected-team analysis returned 11 clips. Reusing the same 43 human-reviewed timestamps produced `0.0909` highlight precision, `0.5` highlight recall, `0.5` selected-team recall with uncertain clips, two selected-team highlights, three opponent highlights, and no defensive-event coverage. This is supplemental same-video evidence, not a second independent launch case; the shared accuracy gate remains failed.

Known beta launch gate: install the latest available internal TestFlight build, then exercise it with real basketball footage using the checklist below and cross the old 15-minute failure point. Public launch remains separately gated by production identity and quota enforcement, observability/reliability, and Phase 4h confirmed-label evidence.

## Repo Layout

- `ios/HoopsClips/` - SwiftUI iOS app, tests, configuration, and app resources.
- `ios/backend/` - internal cloud-analysis backend scaffold and future cloud editing service home.
- `docs/architecture/video_editing_cloud_backend.md` - cloud-first HoopClips AI Edit Agent architecture.
- `docs/video_editing_repo_audit.md` - current repo audit for the cloud editing pivot.
- `docs/phase_beta_launch_gates_after_pr43.md` - post-merge beta launch gate report and real-basketball TestFlight smoke checklist.
- `docs/phase_build54_testflight_proof_2026-07-19.md` - build `54` upload method, signed upload/status proof, and remaining device gates.
- `docs/phase_build55_testflight_proof_2026-07-19.md` - build `55` saved-upload renewal fix, signed upload/status proof, and remaining device gates.
- `docs/phase_build55_selected_team_accuracy_refresh_2026-07-19.md` - current real-staging selected-team probe, accuracy-proof tooling fixes, and unchanged launch blocker.
- `skills/hoopclips-ai-edit-agent/SKILL.md` - repo-local Codex skill for cloud-backend edit-agent work.
- `TESTFLIGHT_BLOCKER.md` - resolved Apple certificate-capacity incident and signing rerun guide.
- `ios/docs/checklists/public-launch-cloud-gated.md` - public launch checklist.
- `ios/docs/runbooks/public-launch-cloud-gated.md` - launch-day support and fallback runbook.
- `ios/docs/runbooks/firebase-auth-setup.md` - Firebase email/password auth setup.
- `ios/docs/app-store/app-review-sign-in.md` - App Review sign-in notes template.
- `ios/docs/reports/release-device-smoke-report.md` - real-device smoke evidence report.
- `.github/workflows/release-secrets-preflight.yml` - manual Release config/build preflight.

## Local Setup

Use Xcode 17 or newer with the iOS 26 SDK, Python 3.13 for backend development, and an Apple Developer team that can sign `atrak.charlie.hoopsclips`.

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
  -scheme HoopsClipsUITests \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -parallel-testing-enabled NO
```

Run backend tests:

```bash
python3.13 -m venv /tmp/hoops-backend-test-venv
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
- Confirm App Store Connect shows the latest internal build as valid and available to the intended tester group.
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

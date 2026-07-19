# Beta Launch Gate Status After PR #43

Date: 2026-07-19

## Summary

PR #43 is merged into `main` at `449cd0907f62dd728741fb43a81e4f9e3815a4ff`. The enhancement integration workstream is complete on `main`; do not redo that integration.

Build `49` installed on a trusted iPhone and reproduced the large-upload failure near 15% on a real 380 MB source: its 15-minute saved upload plan expired with `0/24` completed parts after background handoff. PR #74 merged the longer-lease recovery, PRs #98-#100 added true byte-transfer progress, one shared background multipart session, and the canonical asset-first direct-to-R2 route, and PR #108 added missing-part lease renewal without discarding completed chunks. Upload run `29706183087` and status run `29706397510` prove build `55` from main SHA `bc7218c6ca412cdc1241dd74772b8f84a27a2597` is deployed to App Store Connect, `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, and ready for internal testers. The remaining internal-beta gate is installed real-basketball phone smoke on build `55`. App Store submission also remains blocked by the separate production-candidate and shared-backend accuracy gates.

## Confirmed Main State

- PR #43: merged at `2026-06-28T09:00:46Z`.
- Integration merge commit: `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- Build `44` launch proof baseline: `4540381752db2eb5ac22442c8f49971e0d49f6cb`.
- PR #46 and PR #47: merged; launch proof/testing UI hidden, Settings Formspree support retained, and Settings support banners auto-dismiss.
- PR #48: merged; next TestFlight build bumped to `1.0.0 (44)`.
- PR #58: merged; launch privacy/auth/telemetry hardening and Worker dependency cleanup.
- PR #59: merged; focused iOS tests and serial-bound automatic-signing certificate cleanup.
- PR #60: merged at `51df354cf945069ef55a13f5f0ec50a3065fc53c`; install-bound analysis job reads/cancellation and build `45` compatibility.
- PR #62: merged at `22e24d35b32e784b0d6f9e290504118e965fa105`; build `46` idle-upload recovery, team-scan reliability, smoke tooling, and launch UX follow-up.
- PR #63: merged at `c4a9776be82787551efd25808516775f891468bb`; read-only App Store Connect status proof.
- PR #65: merged at `cb7d8f3c946a6933f52ad18255318c8c4ae3e151`; build `47` adaptive multipart sizing, path-aware concurrency, safe retry staging, and a seven-test upload-policy CI lane.
- PRs #67-#73: merged upload UI simplification, persisted AI Edit state, active-session recovery, and internal builds `48` and `49`.
- PR #74: merged at `6c6ae4ffc267d7b4853dbb955c512f3a098fe601`; build `50` upload-lease/background-session recovery, focused tests, and Release RevenueCat Test Store safeguards.
- PR #77: merged at `e7379227760627ed07410edb728b4eff7c72625b`; upload-time Review waiting UI now stays focused on upload progress and hides redundant analysis/ETA copy until the upload stage completes.
- PR #80: merged at `ca82e6b8552844c149f84157b043bf8f0d6c7f46`; AI Edit selected-style polish.
- PR #81: merged at `60eda29b7989e97a93ebdf973c0d80446caa07bf`; build `51` TestFlight prep and proof docs.
- PR #85: merged at `202b56c5d332529b7bae0006eb743f45bccd9b70`; upload pipeline banner declutter and fresh-upload wording.
- PR #86: merged at `fdb482d334b0a063a508e3e52c843dfa32ecd906`; build `52` TestFlight prep.
- PR #87: merged at `f46705959eb1d792e93d03999eb43c828de114f0`; build `52` archive metadata guard correction.
- PR #92: merged at `f52f443198638d79dce81e5a2d7e4aba117a68fa`; streamlined AI Edit studio/progress UI and focused policy tests.
- PR #93: merged at `55a402b4b6cc48038306af5eed72367adab15bbf`; build `53` archive/status guard updates.
- PRs #94-#97: merged build `53` proof corrections, private Mac beta recommendation, and cloud AI Edit resume recovery.
- PR #98: merged at `0e003629d3aa57d38be5bbf7647219553722a68e`; true byte-transfer upload progress.
- PR #99: merged at `0eda72e527322afdb9ccbf15e51e414d05a5cdcc`; shared-session multipart throughput and recovery improvements.
- PR #100: merged at `e72ebac3b1469387aa08af370395f887d8cd4e52`; canonical asset-first upload routes with legacy fallback compatibility.
- PR #101: merged at `409e5c0c5f9700c3c75006804e7d5bdbe163b797`; signed-archive readiness proof recognition without treating archive proof as upload proof.
- PR #102: merged at `80d2405582042da44cfec92022ab3a33212851b6`; build `54` archive/status guards.
- PR #108: merged at `5ed46d26b023e40dde737fcd5597f61a40dcadf0`; expired canonical-asset missing-part target renewal and build `55` guards.
- PR #109: merged at `bc7218c6ca412cdc1241dd74772b8f84a27a2597`; shared backend accuracy-gate documentation and the exact archived build `55` main SHA.
- Branch posture: `main` contains the integration; follow-up work should stay scoped to launch gates, docs, signing, and smoke proof.

## GitHub Actions State

- `Cloud Edit Deploy Preflight` push run `28317247578`: success on `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- `iOS Internal TestFlight Upload` push/codecheck run `28317247560`: success on `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- `Cloud Edit Deploy Preflight` credential-check run `28317383878`: success on `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- `Cloud Edit Deploy Preflight` deploy run `28317412159`: success on `449cd0907f62dd728741fb43a81e4f9e3815a4ff`.
- `iOS Internal TestFlight Upload` upload run `28470081179`: success for build `43`.
- `iOS Internal TestFlight Upload` archive run `28756536677`: success for build `44` on `4540381752db2eb5ac22442c8f49971e0d49f6cb`.
- `iOS Internal TestFlight Upload` upload run `28756673502`: failed during signed archive because Apple certificate limit/provisioning is not ready on the fresh upload runner.
- `iOS Internal TestFlight Upload` upload rerun `28764285946`: failed the same signed archive gate because Apple certificate limit/provisioning is still not ready.
- `iOS Internal TestFlight Upload` diagnostic upload run `29297858325`: confirmed the certificate-capacity failure after the account holder's local certificate revocation.
- `iOS Internal TestFlight Upload` upload run `29298033420`: success for build `44` on `7a0af43cc21acbe57fa7ba28b4efe9764c3e397e`.
- App Store Connect build `1.0.0 (44)`: `VALID` with internal state `IN_BETA_TESTING`.
- `iOS Internal TestFlight Upload` push/codecheck run `29309388686`: success on merged `main` `45c383a91d6b8223a33032593a839e72e041b955`; six focused tests passed.
- `iOS Internal TestFlight Upload` archive-only run `29309860620`: success for build `44`; upload was intentionally skipped and runner-owned certificate cleanup passed.
- `Cloud Edit Deploy Preflight` push run `29311128829`: success on merged `main` `51df354cf945069ef55a13f5f0ec50a3065fc53c`.
- `iOS Internal TestFlight Upload` push/codecheck run `29311128820`: success on merged `main`; six focused tests passed.
- `iOS Internal TestFlight Upload` upload run `29311514901`: success for build `45`; signed archive, metadata/privacy checks, App Store Connect upload, and runner-owned certificate cleanup passed.
- App Store Connect build `1.0.0 (45)`: `VALID` with internal state `IN_BETA_TESTING`.
- `Cloud Edit Deploy Preflight` deploy run `29312118314`: success for the strict ownership baseline; Worker version `640ca379-99c7-43fa-815a-b1ec9a15f5a6` was verified.
- `Cloud Edit Deploy Preflight` push run `29443527257`: success on build `46` merge SHA `22e24d35b32e784b0d6f9e290504118e965fa105`.
- `Cloud Edit Deploy Preflight` deploy run `29443552918`: success; staging editing and Worker deploy/version proof passed.
- `iOS Internal TestFlight Upload` push/codecheck run `29443528171`: success; six focused tests passed.
- `iOS Internal TestFlight Upload` upload run `29443559399`: success for build `46`; signed archive, metadata/privacy checks, upload, and certificate cleanup passed.
- `iOS Internal TestFlight Upload` status run `29445202395`: success; build `46` is `VALID`, `IN_BETA_TESTING`, and ready for internal testing.
- `Cloud Edit Deploy Preflight` push run `29448705938`: success on build `47` merge SHA `cb7d8f3c946a6933f52ad18255318c8c4ae3e151`.
- `iOS Internal TestFlight Upload` push/codecheck run `29448706013`: success; seven focused upload-policy tests passed.
- `Cloud Edit Deploy Preflight` deploy run `29449140849`: success; staging editing and Worker deploy/version proof passed.
- `iOS Internal TestFlight Upload` upload run `29449525744`: success for build `47`; signed archive, metadata/privacy checks, upload, and certificate cleanup passed.
- `iOS Internal TestFlight Upload` status run `29450181533`: success; build `47` is `VALID`, `IN_BETA_TESTING`, and ready for internal testing.
- `Cloud Edit Deploy Preflight` push run `29632159204`: success on build `50` main SHA `6c6ae4ffc267d7b4853dbb955c512f3a098fe601`.
- `iOS Internal TestFlight Upload` push/codecheck run `29632159207`: success; all 12 focused tests passed.
- `Cloud Edit Deploy Preflight` deploy run `29632345235`: success; staging editing and Worker deploy/version proof passed for build `50`.
- `iOS Internal TestFlight Upload` upload run `29632723114`: success for build `50`; signed archive, metadata/privacy checks, upload, and certificate cleanup passed.
- `iOS Internal TestFlight Upload` status run `29636059497`: success; build `50` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, and ready for internal testing.
- `Cloud Edit Deploy Preflight` push run `29640853755`: success on PR #77 merge SHA `e7379227760627ed07410edb728b4eff7c72625b`.
- `iOS Internal TestFlight Upload` push/codecheck run `29640853783`: success on PR #77 merge SHA `e7379227760627ed07410edb728b4eff7c72625b`; focused unsigned simulator tests passed.
- `iOS Internal TestFlight Upload` upload run `29641040373`: signed archive, metadata/privacy, certificate capacity, and certificate cleanup passed; upload step failed only because App Store Connect already had build `50`.
- `iOS Internal TestFlight Upload` status run `29641232924`: success; build `50` is still found in App Store Connect and ready for internal testing.
- `iOS Internal TestFlight Upload` push/codecheck run `29644908038`: success for build `51` main SHA `60eda29b7989e97a93ebdf973c0d80446caa07bf`; build settings, export options, and 12 focused simulator tests passed.
- `iOS Internal TestFlight Upload` upload run `29644918870`: success for build `51`; signed archive, metadata/privacy checks, App Store Connect upload, and certificate cleanup passed.
- `iOS Internal TestFlight Upload` status run `29645129050`: success; build `51` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing.
- `iOS Internal TestFlight Upload` push/codecheck run `29655523209`: success for build `52` prep on merged main.
- `iOS Internal TestFlight Upload` upload run `29655548305`: signed archive passed, but archive metadata verification failed because the workflow still expected build `51`; no App Store upload was attempted.
- `iOS Internal TestFlight Upload` push/codecheck run `29656404272`: success after PR #87 corrected the build `52` metadata guard.
- `iOS Internal TestFlight Upload` upload run `29656420482`: success for build `52`; signed archive, metadata/privacy checks, App Store Connect upload, and certificate cleanup passed.
- `iOS Internal TestFlight Upload` status run `29656700078`: success; build `52` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing.
- `iOS Internal TestFlight Upload` push/codecheck run `29667213808`: success for build `53` on merged main SHA `55a402b4b6cc48038306af5eed72367adab15bbf`.
- `iOS Internal TestFlight Upload` upload run `29667373531`: success for build `53`; signed archive, metadata/privacy checks, App Store Connect upload, and certificate cleanup passed.
- `iOS Internal TestFlight Upload` status run `29667648668`: success; build `53` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing.
- `iOS Internal TestFlight Upload` upload run `29701267324`: success for build `54` on merged main SHA `80d2405582042da44cfec92022ab3a33212851b6`; signing-capacity validation, signed archive, metadata/privacy checks, App Store Connect upload, and certificate cleanup passed.
- `iOS Internal TestFlight Upload` status run `29701467040`: success; build `54` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing.
- `Cloud Edit Deploy Preflight` push run `29706005325`: success after the PR #108 merge.
- `iOS Internal TestFlight Upload` push/codecheck run `29706005364`: success; all 14 focused simulator tests passed for build `55` source.
- `iOS Internal TestFlight Upload` upload run `29706183087`: success for build `55` on current main SHA `bc7218c6ca412cdc1241dd74772b8f84a27a2597`; signing-capacity validation, signed archive, metadata/privacy checks, App Store Connect upload, and certificate cleanup passed.
- `iOS Internal TestFlight Upload` status run `29706397510`: success; build `55` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing.

## Staging Deploy And Version Proof

The original staging deploy passed after PR #43 was merged. Build `50` deploy run `29632345235` published the upload-lease/background-session recovery; the live Worker `/v1/editing/version` and direct editing `/version` checks reported `6c6ae4ffc267d7b4853dbb955c512f3a098fe601` and the expected AI Edit/GPT feature flags. Live capabilities and a fresh secret-safe presign probe both confirmed a 3,600-second signed upload lease.

Operator rerun command:

```bash
python3 scripts/staging_version_probe.py --expected-git-sha 6c6ae4ffc267d7b4853dbb955c512f3a098fe601 --json
```

## Deterministic Render Smoke

The deterministic Worker render smoke passed through the active Worker render path after the merge. It produced a valid MP4 with H.264 video and AAC audio.

This proves the Worker/direct editing render contract for a deterministic edit plan. It does not replace an installed TestFlight run on real basketball footage.

After the build `46` deploy, three consecutive real-basketball team scans detected the black/white teams and queued selected-team analysis. A separate all-teams collection completed with eight clips. These are cloud-path reliability proofs, not substitutes for the installed app flow.

## Synthetic GPT Smoke Classification

The synthetic GPT iOS client smoke uploaded generated test video and received `empty_clip_list` from `POST /v1/edit-jobs`.

Classification: expected synthetic-video no-clips case, not current evidence of a Worker/direct editing contract bug.

Reasoning:

- The smoke source is synthetic test video, not real basketball footage.
- Backend tests intentionally require `empty_clip_list` when GPT rejects every candidate and no render-worthy clips remain.
- The deterministic Worker render smoke passed with a valid edit plan against the same deployed path.
- Real launch proof must use real basketball footage and the installed TestFlight app.

## Live Analysis Ownership Smoke

After deploy run `29312118314`, a self-cleaning live smoke created an analysis job and verified the strict contract:

- A read without `installId` returned `400 invalid_request`.
- A read or cancellation with a different install returned `403 install_mismatch`.
- The owning install could read the job in `upload_pending`, cancel it, and read the resulting `cancelled` state.
- The smoke issued its owner-scoped cleanup and did not retain private identifiers or upload data.

## iOS Signing/TestFlight Resolution

Build `44` archive run `28756536677` passed and verified bundle ID `atrak.charlie.hoopsclips`, version `1.0.0`, build `44`, environment `internal_staging`, and cloud launch mode `internal_only`.

Earlier upload runs failed while re-archiving on fresh runners after CI materialized the required inputs. Live Apple API inspection showed that ten stale `Apple Development: Created via API` certificates from prior ephemeral runners had exhausted the account limit. The stale CI certificates were revoked while the distribution certificate was preserved.

Upload run `29298033420` then passed the signed archive, metadata/privacy verification, and App Store Connect upload. App Store Connect reports build `44` as `VALID` and `IN_BETA_TESTING`. The successful runner's new development certificate was removed after upload. The workflow now matches cleanup to the runner/archive certificate serial and blocks a later signed run if an earlier runner left a certificate behind.

Build `45` upload run `29311514901` then passed the same signed archive, metadata/privacy, upload, and certificate-cleanup gates. App Store Connect reports build `45` as `VALID` and `IN_BETA_TESTING`.

Build `46` upload run `29443559399` passed signed archive, metadata/privacy, upload, and certificate cleanup. Status run `29445202395` then read the processed build through Apple's API and confirmed `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, and no non-exempt encryption. Apple account state is not the remaining blocker.

Build `47` upload run `29449525744` passed the same signed archive, metadata/privacy, upload, and certificate-cleanup gates. Status run `29450181533` confirmed build `47` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, and ready for internal testing.

Build `50` upload run `29632723114` passed signed archive, metadata/privacy, production-compatible RevenueCat-key verification, upload, and certificate cleanup. Status run `29636059497` confirmed build `50` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, and ready for internal testing.

After PR #77, rerunning `operation=upload` on `main` produced a new signed archive and passed archive metadata checks, but App Store Connect rejected the upload because bundle version `50` was already used. This is not a signing/license/provisioning failure. Status run `29641232924` then confirmed the existing build `50` remains `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, and ready for internal testing.

Build `51` upload run `29644918870` passed signed archive, metadata/privacy, upload, and certificate cleanup on main SHA `60eda29b7989e97a93ebdf973c0d80446caa07bf`. Status run `29645129050` confirmed build `51` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing.

Build `52` upload run `29656420482` passed signed archive, metadata/privacy, upload, and certificate cleanup on main SHA `f46705959eb1d792e93d03999eb43c828de114f0`. Status run `29656700078` confirmed build `52` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing. Apple account state is not the remaining blocker.

Build `53` upload run `29667373531` passed signed archive, metadata/privacy, upload, and certificate cleanup on main SHA `55a402b4b6cc48038306af5eed72367adab15bbf`. Status run `29667648668` confirmed build `53` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing. Apple account state is not the remaining blocker.

Build `54` upload run `29701267324` passed signing-capacity validation, signed archive, metadata/privacy, upload, and certificate cleanup on main SHA `80d2405582042da44cfec92022ab3a33212851b6`. Status run `29701467040` confirmed build `54` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing. Apple account state is not the remaining blocker.

Build `55` upload run `29706183087` passed signing-capacity validation, signed archive, metadata/privacy, upload, and certificate cleanup on main SHA `bc7218c6ca412cdc1241dd74772b8f84a27a2597`. Status run `29706397510` confirmed build `55` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and ready for internal testing. Build `55` renews expired canonical-asset multipart part targets while preserving completed chunks.

The paired iPhone was visible through CoreDevice on 2026-07-18, but it still had HoopClips build `49` installed during the last successful metadata read. A later `devicectl` device list showed the same iPhone as `unavailable`, with `tunnelState=unavailable`. Install/update build `55` on the trusted iPhone, unlock the device, restore USB or same-network CoreDevice connectivity, then run the real-basketball installed smoke before claiming the internal-beta phone gate complete.

Use `TESTFLIGHT_BLOCKER.md` as the resolved incident record and future rerun guide.

## Real-Basketball TestFlight Smoke Checklist

Run this against internal TestFlight build `1.0.0 (55)`, whose upload and App Store Connect status proof have passed. Earlier builds are retained as launch evidence but are superseded for this smoke by the one-hour upload lease, true byte-transfer progress, shared-session multipart transfer, canonical asset-first route, saved-part lease renewal, and AI Edit launch/resume polish.

1. Install internal TestFlight build `1.0.0 (55)` on a trusted iPhone.
2. Confirm the build is `1.0.0 (55)` from archived main SHA `bc7218c6ca412cdc1241dd74772b8f84a27a2597`.
3. Confirm the app is in internal staging mode and points to `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`.
4. Upload a real basketball video from Photos or Files.
5. Keep the app active/backgrounded as a normal user would, cross the old 15-minute failure point, then wait for upload completion and `proxy_ready`.
6. Run team scan and select/confirm the target team if prompted.
7. Start cloud analysis and wait for completion.
8. Open Review and confirm real basketball clips are visible.
9. Keep/discard clips as needed without forcing weak clips into the edit.
10. Open AI Edit.
11. Choose a style and target length.
12. Create the AI edit plan.
13. Request cloud render and wait for the render to finish.
14. Download the final MP4.
15. Preview the downloaded MP4 in-app.
16. Save the MP4 to Photos.
17. Use the share sheet to open/export the MP4 to Files and at least one editor target such as CapCut, iMovie, or Adobe if installed.
18. Request one revision, such as higher energy or shorter length.
19. Render, download, preview, and share/open the revised export.
20. Record build number, SHA, workflow run IDs, source video duration, pass/fail notes, and screenshots/log snippets with no secrets.

## Next Gate

Install build `55`, complete the real-basketball TestFlight smoke checklist above, and update `ios/docs/reports/release-device-smoke-report.md` with the result. App Store submission remains blocked until that installed flow passes and the human-reviewed 85% team/highlight accuracy gate is resolved or explicitly accepted by the release owner. Public launch remains separately gated by production identity/quota enforcement, observability/reliability, and Phase 4h confirmed-label evidence.

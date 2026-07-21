# TestFlight Signing Incident

Status: Apple signing incident resolved. Builds `1.0.0 (44)` through `(57)` were uploaded successfully. Build `57` upload run `29723139547` passed, and read-only status run `29723517882` confirmed internal TestFlight availability.

This file is retained as the non-secret incident record and rerun guide. Apple signing, provisioning, archive, upload, and processing are not current blockers. The Apple Developer Program agreement and App Store Connect Free/Paid Apps agreements are active, `atrak.charlie.hoopsclips` remains registered, and valid development/distribution certificates are present. Build `57` independently proves automatic provisioning, signed upload, processing, and internal TestFlight availability.

Build `49` installed and launched on a trusted iPhone but reproduced a saved-upload expiry near 15% on a real 380 MB source. Build `57` is the current uploaded recovery candidate. It retains the longer upload lease, true byte-transfer progress, one shared background multipart session, the canonical asset-first direct-to-R2 route, missing-part target renewal, and up to six high-priority multipart lanes on normal Wi-Fi. It also prepares a smaller 720p upload source for recordings at least 12 minutes or 256 MiB when doing so saves at least 18 percent. Installed real-basketball smoke on build `57` must still pass before the internal beta gate closes.

## Resolution Evidence

- PR #43 remains merged; the enhancement integration workstream was not redone.
- Current merged signing-lifecycle baseline: `45c383a91d6b8223a33032593a839e72e041b955`.
- Staging deploy, live Worker/direct editing version proof, and deterministic Worker render smoke remain passed.
- Build `44` signed archive run `28756536677`: passed.
- Upload diagnostic run `29297858325`: failed at signing with the certificate-capacity and missing-profile errors.
- Apple API inspection found ten stale `Apple Development: Created via API` certificates left by earlier ephemeral CI runners. Their private keys no longer existed after those runners ended.
- The ten stale CI development certificates were revoked while the existing distribution certificate was preserved.
- Upload run `29298033420`: passed the signed archive, archive metadata/privacy checks, and `Upload to internal TestFlight`.
- App Store Connect build `1.0.0 (44)`: `VALID`, `IN_BETA_TESTING`, not expired, minimum iOS `17.0`, and no non-exempt encryption declaration required.
- The one development certificate created by the successful ephemeral runner was revoked after upload.
- PR #59 merged at `45c383a91d6b8223a33032593a839e72e041b955`. Its archive-only run `29309860620` passed signed archive/metadata checks, intentionally skipped upload, and revoked the runner-owned development certificate through the new serial-bound cleanup.
- PR #60 merged at `51df354cf945069ef55a13f5f0ec50a3065fc53c` with install-bound analysis ownership and build `45` compatibility.
- Upload run `29311514901`: passed signed archive, metadata/privacy verification, build `45` upload, and serial-bound runner certificate cleanup.
- App Store Connect build `1.0.0 (45)`: `VALID`, `IN_BETA_TESTING`, not expired, minimum iOS `17.0`, and no non-exempt encryption declaration required.
- Strict staging deploy run `29312118314`: passed Worker and direct editing deployment/version proof at the PR #60 merge SHA.
- Live ownership smoke passed: missing ownership was rejected with `400`, mismatched ownership with `403`, and only the matching install could read and cancel its analysis job.
- PR #62 merged at `22e24d35b32e784b0d6f9e290504118e965fa105` with the build `46` upload-expiry fix and focused smoke reliability changes.
- Strict staging deploy run `29443552918`: passed editing/Worker deploy and live version proof for `22e24d35b32e784b0d6f9e290504118e965fa105`.
- Upload run `29443559399`: passed signed archive, metadata/privacy verification, build `46` upload, and serial-bound runner certificate cleanup.
- PR #63 merged at `c4a9776be82787551efd25808516775f891468bb` with a read-only status operation that does not archive, sign, or upload.
- App Store Connect status run `29445202395`: build `1.0.0 (46)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, and does not use non-exempt encryption.
- PR #65 merged at `cb7d8f3c946a6933f52ad18255318c8c4ae3e151` with build `47` adaptive multipart planning and path-aware concurrency.
- Strict staging deploy run `29449140849`: passed editing/Worker deploy and live version proof for the PR #65 merge SHA.
- Upload run `29449525744`: passed signed archive, metadata/privacy verification, build `47` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29450181533`: build `1.0.0 (47)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, and does not use non-exempt encryption.
- PR #73 merged at `2affd1d0049434cda9c3026cd7db77c003b14852` with internal TestFlight build `49` preparation.
- Upload run `29623108647`: passed signed archive, metadata/privacy verification, build `49` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29623416437`: build `1.0.0 (49)` is available for internal TestFlight testing.
- Apple account recheck on July 17 confirmed active developer/app agreements, the registered HoopClips bundle ID, and valid development/distribution certificates.
- PR #74 merged at `6c6ae4ffc267d7b4853dbb955c512f3a098fe601` with build `50` upload-lease and background-session recovery.
- Main push runs `29632159204` and `29632159207`: cloud checks and all 12 focused iOS tests passed.
- Staging deploy run `29632345235`: editing/Worker deployment and live version proof passed for the build `50` main SHA. Live capabilities and a fresh secret-safe presign probe both confirmed a 3,600-second signed upload lease.
- Upload run `29632723114`: passed signed archive, metadata/privacy verification, build `50` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29636059497`: build `1.0.0 (50)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, and ready for internal testing.
- PR #81 merged at `60eda29b7989e97a93ebdf973c0d80446caa07bf` with build `51` TestFlight prep.
- Upload run `29644918870`: passed signed archive, metadata/privacy verification, build `51` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29645129050`: build `1.0.0 (51)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
- PR #86 merged at `fdb482d334b0a063a508e3e52c843dfa32ecd906` with build `52` TestFlight prep for current-main installed smoke.
- Initial build `52` upload run `29655548305`: signed archive passed, but archive metadata verification failed because the workflow still expected build `51`; no upload was attempted.
- PR #87 merged at `f46705959eb1d792e93d03999eb43c828de114f0` with the build `52` archive metadata guard correction.
- Upload run `29656420482`: passed signed archive, metadata/privacy verification, build `52` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29656700078`: build `1.0.0 (52)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
- PR #92 merged at `f52f443198638d79dce81e5a2d7e4aba117a68fa` with streamlined AI Edit studio/progress UI and focused policy tests.
- PR #93 merged at `55a402b4b6cc48038306af5eed72367adab15bbf` with build `53` archive/status guard updates.
- Main codecheck run `29667213808`: passed for build `53` on the PR #93 merged SHA.
- Upload run `29667373531`: passed signed archive, metadata/privacy verification, build `53` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29667648668`: build `1.0.0 (53)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
- PR #98 merged at `0e003629d3aa57d38be5bbf7647219553722a68e` with true byte-transfer upload progress.
- PR #99 merged at `0eda72e527322afdb9ccbf15e51e414d05a5cdcc` with one shared background `URLSession` per multipart upload and preserved relaunch recovery.
- PR #100 merged at `e72ebac3b1469387aa08af370395f887d8cd4e52` with the canonical asset-first upload route and legacy compatibility fallback.
- PR #102 merged at `80d2405582042da44cfec92022ab3a33212851b6` with build `54` archive/status guards.
- Upload run `29701267324`: passed signing-capacity validation, signed archive, metadata/privacy verification, build `54` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29701467040`: build `1.0.0 (54)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
- PR #108 merged at `5ed46d26b023e40dde737fcd5597f61a40dcadf0` with expired saved multipart lease renewal and build `55` preparation.
- Upload run `29706183087`: passed signing-capacity validation, signed archive, metadata/privacy verification, build `55` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29706397510`: build `1.0.0 (55)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, does not use non-exempt encryption, and is ready for internal testing.
- PR #112 merged at `b1a655eab95e67cb80d18bb3ba8c6be727910dcb` with the multipart startup throughput correction.
- PR #113 merged at `701624eb9fed343c43720d060a78e9fcada7df80` with build `56` archive/status guards.
- Main codecheck run `29716039765`: passed all 15 focused simulator tests for build `56`.
- Upload run `29716394858`: passed signing-capacity validation, signed archive, metadata/privacy verification, build `56` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29717019768`: build `1.0.0 (56)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, and ready for internal testing.
- PR #115 merged at `15339ce5c4602a61abb562db5c6d4ca97fe39dbb` with automatic upload-source optimization and build `57` archive/status guards.
- Upload run `29723139547`: passed signing-capacity validation, signed archive, metadata/privacy verification, build `57` upload, and serial-bound runner certificate cleanup.
- App Store Connect status run `29723517882`: build `1.0.0 (57)` is `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, and ready for internal testing.
- PRs #117 and #118 advanced current main to `72701b2abfd229386cd9353e1056f45019a2c2e1`; post-merge cloud preflight run `29781455716` and no-secret iOS codecheck run `29781456008` passed. Those changes were not archived or uploaded as a newer TestFlight build.

No certificate contents, private keys, API key contents, provisioning profile contents, passwords, or tokens belong in this file.

## Root Cause

The automatic-signing workflow used a fresh GitHub-hosted runner for every archive. Xcode created a new development certificate through the App Store Connect API, but the certificate's private key disappeared with the runner. Repeated archive attempts accumulated ten unusable API-created development certificates and exhausted the account limit.

Revoking only the local Mac's development certificate did not remove those CI-created certificates. That is why the first July 13 retry still returned:

- `Choose a certificate to revoke. Your account has reached the maximum number of certificates.`
- `No profiles for 'atrak.charlie.hoopsclips' were found.`

## Recurrence Prevention

The signed workflow now serializes automatic-signing jobs and refuses to start Xcode while any preexisting API-created development certificate needs reconciliation. It records the runner's local certificate serials before signing, then its `always()` cleanup step revokes only a matching API certificate whose serial was newly installed on that runner or extracted from that runner's archive. It refuses to delete more than one.

If a runner disappears before cleanup, the leaked certificate causes the next signed run to stop before creating another certificate. The operator must then reconcile that single non-secret certificate record through Apple before retrying. This fail-closed path prevents another silent certificate buildup without deleting a same-named certificate created by another repository or manual Xcode session.

The workflow preserves the distribution certificate and never prints or commits private material.

## Future Rerun Command

Use this only when a later build needs to be uploaded:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
```

After the upload completes, verify processing and internal availability without creating another archive or certificate:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=status
```

Expected passing evidence:

- `Build signed internal staging archive`: success.
- Bundle ID: `atrak.charlie.hoopsclips`.
- Version/build: the values expected by the workflow.
- Environment: `internal_staging`.
- Launch mode: `internal_only`.
- App-owned `PrivacyInfo.xcprivacy`: present and valid at the app-bundle root.
- RevenueCat key: present and production-compatible; Test Store keys fail closed without printing the value.
- `Upload to internal TestFlight`: success for `operation=upload`.
- `Revoke this runner's automatic signing certificate`: success with zero or one serial-matched certificate revoked.

## Remaining TestFlight Work

Build `57` is uploaded, processed, and ready for internal testers from archived source SHA `15339ce5c4602a61abb562db5c6d4ca97fe39dbb`. The paired iPhone was available on July 20 but still reported installed build `53`; TestFlight was opened and the build `57` update remained pending. Install build `57`, then complete the real-basketball checklist in `docs/phase_beta_launch_gates_after_pr43.md`. The smoke must cross the old 15-minute/15% failure point and continue through `proxy_ready`, team scan, analysis, Review, AI Edit, render, download, Photos, and share/open export. Record the result in `ios/docs/reports/release-device-smoke-report.md` without secrets, private video contents, presigned URLs, object keys, or local file paths.

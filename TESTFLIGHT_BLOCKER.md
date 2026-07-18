# TestFlight Signing Incident

Status: Apple signing incident resolved. Builds `1.0.0 (44)` through `(52)` were uploaded successfully. Build `52` upload run `29656420482` passed, and read-only status run `29656700078` confirmed internal TestFlight availability.

This file is retained as the non-secret incident record and rerun guide. Apple signing, provisioning, archive, upload, and processing are not current blockers. On July 17, 2026, the Apple Developer Program agreement and App Store Connect Free/Paid Apps agreements were active, `atrak.charlie.hoopsclips` remained registered, and valid development/distribution certificates were present. Build `52` independently proves automatic provisioning, signed upload, processing, and internal TestFlight availability.

Build `49` installed and launched on a trusted iPhone but reproduced a saved-upload expiry near 15% on a real 380 MB source. Build `52` is the current uploaded recovery candidate and includes the build `51` upload recovery plus PR #85 upload-status declutter. Installed real-basketball smoke on build `52` must still pass before the internal beta gate closes.

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

Build `52` is merged, uploaded, processed, and ready for internal testers. Install it from TestFlight on the trusted iPhone, then complete the real-basketball checklist in `docs/phase_beta_launch_gates_after_pr43.md`. The smoke must cross the old 15-minute failure point and continue through `proxy_ready`, team scan, analysis, Review, AI Edit, render, download, Photos, and share/open export. Record the result in `ios/docs/reports/release-device-smoke-report.md` without secrets, private video contents, presigned URLs, object keys, or local file paths.

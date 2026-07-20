# Build 57 TestFlight Upload Optimization Proof

Date: 2026-07-20

## Result

HoopClips internal TestFlight build `1.0.0 (57)` is uploaded, processed, and ready for internal testing for bundle ID `atrak.charlie.hoopsclips`.

- PR #115 merged at `15339ce5c4602a61abb562db5c6d4ca97fe39dbb`.
- Merged-main codecheck run `29722969229` passed the exact 16-test iOS release selection.
- Signed archive/upload run `29723139547` passed required-input checks, certificate-capacity validation, automatic signing and provisioning, archive metadata/privacy verification, App Store Connect upload, and runner-owned certificate cleanup.
- Read-only status run `29723517882` reported `buildFound=true`, `processingState=VALID`, `internalBuildState=IN_BETA_TESTING`, `buildAudienceType=INTERNAL_ONLY`, `readyForInternalTesting=true`, and `expired=false`.

Apple signing, provisioning, upload, and processing are not current blockers.

## Upload Method

Build `57` sends video bytes from the iPhone directly to presigned Cloudflare R2 targets. The Worker is the control plane; it does not relay the video body.

1. Files below 64 MiB use one presigned R2 `PUT`.
2. Larger files use adaptive 8-32 MiB multipart chunks targeting about 24 parts.
3. Normal networks can schedule up to six high-priority tasks, expensive paths two, and constrained paths one in a shared background `URLSession`.
4. Completed part ETags and resumable session identity are persisted, and missing-part targets can be renewed without discarding completed chunks.
5. Recordings at least 12 minutes or 256 MiB are eligible for a balanced 720p upload source. Fast Upload Mode forces source preparation; recordings at least 45 minutes or 1.4 GiB prefer the compact 540p profile.
6. The prepared source replaces the original only when it is valid and at least 18 percent smaller. Otherwise the original uploads unchanged.
7. After upload completion, the cloud path waits for `proxy_ready`, then runs team scan and analysis.

This reduces transfer bytes when preparation produces a meaningful saving. It is not physical-iPhone wall-clock proof, and it does not change cloud detection thresholds, edit planning, or rendering architecture.

## Verification

- Upload throughput policy suite: `10/10` tests passed locally.
- Exact iOS release selection: `16/16` tests passed locally and on merged main.
- Launch script suite: `235/235` tests passed.
- Launch config/no-secret preflight: `85` passes, `12` existing warnings, and `0` failures.
- Internal staging config, export options, privacy manifest, JSON, and diff checks passed.
- App Store Connect status artifact confirms iOS `17.0` minimum, no non-exempt encryption, and expiration on `2026-10-18`.

## Remaining Gates

1. Install `1.0.0 (57)` from TestFlight on the trusted iPhone.
2. Upload a real basketball recording on normal Wi-Fi and record the original size, prepared size when available, time to first byte, progress beyond 15 percent, and total upload time.
3. Wait for `proxy_ready`, run team scan and analysis, open Review, create an AI Edit, render, download, preview, save to Photos, and share or open the export.
4. Record the secret-safe installed-device result in `ios/docs/reports/release-device-smoke-report.md`.
5. Produce a launch-grade human-reviewed report meeting the shared 85 percent team/highlight accuracy gate, or record explicit release-owner risk acceptance.

Build `57` uses `InternalStaging.xcconfig` and the staging Worker. It must not be selected for public App Store review. Production build `58` is reserved as the next Store candidate and still needs separate production configuration, metadata, privacy, account, archive/upload, and installed-candidate proof.

## Workflow Commands

Build `57` is already uploaded and its status is verified. Do not rerun its upload because App Store Connect build numbers are immutable.

For a later internal build, increment every build guard before running:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
gh workflow run ios-testflight-upload.yml --ref main -f operation=status
```

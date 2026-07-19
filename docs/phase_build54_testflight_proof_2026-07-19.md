# Build 54 TestFlight Proof

Date: 2026-07-19

## Result

Build `54` release SHA `80d2405582042da44cfec92022ab3a33212851b6` is uploaded and processed as HoopClips internal TestFlight build `1.0.0 (54)` for bundle ID `atrak.charlie.hoopsclips`.

- PR #98 merged at `0e003629d3aa57d38be5bbf7647219553722a68e` with true byte-transfer upload progress.
- PR #99 merged at `0eda72e527322afdb9ccbf15e51e414d05a5cdcc` with one shared background `URLSession` for multipart upload parts and preserved relaunch recovery.
- PR #100 merged at `e72ebac3b1469387aa08af370395f887d8cd4e52` with the canonical asset-first upload route and legacy compatibility fallback.
- PR #101 merged at `409e5c0c5f9700c3c75006804e7d5bdbe163b797` with readiness recognition for signed archive proof without misclassifying it as upload proof.
- PR #102 merged at `80d2405582042da44cfec92022ab3a33212851b6` with build `54` archive and status guards.
- Signed archive/upload run `29701267324`: passed certificate-capacity validation, automatic signing and provisioning, archive metadata/privacy checks, App Store Connect upload, and runner certificate cleanup.
- Read-only status run `29701467040`: `buildFound=true`, `processingState=VALID`, `internalBuildState=IN_BETA_TESTING`, `buildAudienceType=INTERNAL_ONLY`, `readyForInternalTesting=true`, and `expired=false`.
- Apple reports minimum iOS `17.0`, no non-exempt encryption, upload time `2026-07-19T12:53:54-07:00`, and expiration `2026-10-17T12:53:54-07:00`.

Apple signing, provisioning, upload, and processing are therefore not current blockers.

## Upload Method In Build 54

The iOS app remains a cloud-first control surface. It initializes an asset, receives presigned multipart targets, uploads the video bytes directly to Cloudflare R2, completes the asset, then waits for backend readiness before team scan and analysis.

- Multipart planning uses adaptive 8-32 MiB parts and targets about 24 parts for large videos.
- Normal networks can run up to six upload lanes; expensive networks use up to two, and constrained networks use one.
- All parts for one video share a single background `URLSession`, avoiding the per-part session creation and invalidation overhead present in build `53`.
- Progress reflects transferred bytes instead of only completed parts, so a large part no longer looks frozen while bytes are moving.
- The canonical path is `uploads/init -> direct R2 transfer -> uploads/{assetId}/complete -> assets/{assetId}`. The older analysis-job upload path remains only as a compatibility fallback for deployments that do not expose the asset routes.
- Part descriptions, completed ETags, staging files, and the shared session identifier remain persisted for suspension and relaunch recovery.

This release does not weaken basketball detection thresholds and does not move analysis, edit planning, or production rendering onto iOS.

## Remaining Gates

1. Install `1.0.0 (54)` from TestFlight on the trusted iPhone.
2. Upload real basketball footage and cross the prior 15-minute/15% failure area.
3. Continue through `proxy_ready`, team scan, cloud analysis, Review, AI Edit, render, download, in-app preview, save to Photos, and share/open export.
4. Record the secret-safe result in `ios/docs/reports/release-device-smoke-report.md`.
5. Complete the independent human-reviewed 85% selected-team/highlight accuracy report.

App Store submission is not ready until both the installed real-basketball smoke and the 85% accuracy gate pass. Public launch remains separately gated by production identity/quota enforcement, observability/reliability, and Phase 4h confirmed-label evidence.

## Future Build Commands

Only rerun these after incrementing the build number for a later release candidate:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
gh workflow run ios-testflight-upload.yml --ref main -f operation=status
```

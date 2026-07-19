# Build 55 TestFlight Upload Resume Proof

Date: 2026-07-19

## Result

HoopClips internal TestFlight build `1.0.0 (55)` is uploaded and processed for bundle ID `atrak.charlie.hoopsclips`.

- PR #108 merged at `5ed46d26b023e40dde737fcd5597f61a40dcadf0` with the saved-upload lease-renewal fix and build `55` release guards.
- The signed workflow archived current main SHA `bc7218c6ca412cdc1241dd74772b8f84a27a2597`, which includes PR #108.
- Main cloud checks passed in run `29706005325`.
- Main no-secret iOS codecheck passed in run `29706005364`, including all 14 focused simulator tests.
- Signed archive/upload run `29706183087` passed required-input checks, certificate-capacity validation, automatic signing and provisioning, archive metadata/privacy verification, App Store Connect upload, and runner-owned certificate cleanup.
- Read-only status run `29706397510` reported `buildFound=true`, `processingState=VALID`, `internalBuildState=IN_BETA_TESTING`, `buildAudienceType=INTERNAL_ONLY`, `readyForInternalTesting=true`, and `expired=false`.
- Apple reports minimum iOS `17.0`, no non-exempt encryption, upload time `2026-07-19T15:34:22-07:00`, and expiration `2026-10-17T15:34:22-07:00`.

Apple signing, provisioning, upload, and processing are not current blockers.

## Upload Method

Build `55` keeps the cloud-first direct upload path:

1. The app calls `POST /v1/uploads/init`.
2. Files below 64 MiB use one presigned R2 `PUT`.
3. Larger files use adaptive 8-32 MiB multipart chunks, targeting about 24 parts.
4. Normal Wi-Fi can use up to six lanes, expensive paths two, and constrained paths one.
5. Completed part ETags, byte progress, and the shared background-session identity are persisted.
6. The app completes the asset, waits for `proxy_ready`, then starts team scan and cloud analysis.

The build `55` correction applies when a saved canonical-asset multipart plan reaches its one-hour signed-URL expiry. The app now keeps completed chunks and requests fresh targets only for missing parts through the existing multipart-part endpoint. A nonrenewable single-part upload still asks for a fresh upload. Detection thresholds, cloud analysis, edit planning, and rendering architecture are unchanged.

## Verification

- Local iOS CI selection: `14/14` tests passed.
- Local control-plane suite: `49/49` tests passed.
- Readiness/helper suite: `68/68` tests passed.
- Control-plane TypeScript typecheck: passed.
- Internal staging config and privacy/export plist checks: passed.
- No-secret launch preflight: `85` passes, `0` failures.
- GitHub PR #108 and merged-main required checks: passed.

## Remaining Gates

1. Install `1.0.0 (55)` from TestFlight on the trusted iPhone.
2. Upload or resume real basketball footage and cross the prior 15-minute/15% failure area.
3. Continue through `proxy_ready`, team scan, analysis, Review, AI Edit, render, download, in-app preview, save to Photos, and share/open export.
4. Record the secret-safe installed-device result in `ios/docs/reports/release-device-smoke-report.md`.
5. Resolve the independent shared-backend accuracy gate or record explicit release-owner risk acceptance.

Build `55` uses `InternalStaging.xcconfig` and the staging Worker. It must not be selected for public App Store review. Because build `55` is now consumed, the production Store lane reserves build `56`; production endpoints, Store metadata/privacy, screenshots, review-account verification, and the production candidate smoke remain separate gates.

## Workflow Commands

Build `55` is already uploaded. For a later internal build, increment all internal build guards before rerunning:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
gh workflow run ios-testflight-upload.yml --ref main -f operation=status
```

For the reserved production candidate, do not dispatch until the production environment gates are corrected:

```bash
gh workflow run ios-app-store-production-upload.yml --ref main -f operation=config-check -f build_number=56
```

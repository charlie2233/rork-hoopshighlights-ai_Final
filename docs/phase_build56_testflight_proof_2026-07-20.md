# Build 56 TestFlight Multipart Startup Proof

Date: 2026-07-20

## Result

HoopClips internal TestFlight build `1.0.0 (56)` is uploaded, processed, and ready for internal testing for bundle ID `atrak.charlie.hoopsclips`.

- PR #112 merged at `b1a655eab95e67cb80d18bb3ba8c6be727910dcb` with the multipart startup throughput correction.
- PR #113 merged at `701624eb9fed343c43720d060a78e9fcada7df80` with build `56` release guards.
- The signed workflow archived main SHA `701624eb9fed343c43720d060a78e9fcada7df80`, which includes both changes.
- Main no-secret iOS codecheck run `29716039765` passed all 15 focused simulator tests.
- Signed archive/upload run `29716394858` passed required-input checks, certificate-capacity validation, automatic signing and provisioning, archive metadata/privacy verification, App Store Connect upload, and runner-owned certificate cleanup.
- Read-only status run `29717019768` reported `buildFound=true`, `processingState=VALID`, `internalBuildState=IN_BETA_TESTING`, `buildAudienceType=INTERNAL_ONLY`, `readyForInternalTesting=true`, and `expired=false`.

Apple signing, provisioning, upload, and processing are not current blockers.

## Upload Method

Build `56` uses the cloud-first direct upload path:

1. The app creates a canonical cloud asset and obtains presigned Cloudflare R2 upload targets.
2. Files below 64 MiB use one presigned R2 `PUT`.
3. Larger files use adaptive 8-32 MiB multipart chunks, targeting about 24 parts.
4. Before the first chunks are scheduled, the app waits up to 300 ms for `NWPathMonitor` to classify the network.
5. Normal networks can schedule up to six high-priority upload tasks, expensive paths two, and constrained or unavailable paths one.
6. The shared background `URLSession` permits six connections per host and persists completed part ETags, byte progress, and resumable session identity.
7. Missing-part targets can be renewed without discarding completed chunks when a saved plan expires.
8. After upload completion, the app waits for `proxy_ready`, then starts team scan and cloud analysis.

The phone sends video bytes directly to R2; the Worker controls asset creation, signed targets, completion, ownership, and later cloud processing. Detection thresholds, cloud analysis, edit planning, and rendering architecture were not changed.

## Verification

- PR #112 local iOS suite: `237/237` tests passed.
- PR #112 focused CI selection: `15/15` tests passed.
- A live 72 MiB multipart R2 benchmark completed end to end in about 31 seconds. This proves the staging multipart contract, not physical-iPhone speed.
- Build #56 release/preflight suite: `68/68` tests passed.
- Workflow-trigger suite: `4/4` tests passed.
- Internal staging config, export options, and privacy manifest checks passed.
- No-secret launch preflight: `85` passes and `0` failures.
- Merged-main codecheck, signed archive/upload, and read-only App Store Connect status checks passed.

## Remaining Gates

1. Install `1.0.0 (56)` from TestFlight on the trusted iPhone.
2. Upload a real large basketball video on normal Wi-Fi and verify progress continues beyond the former 15% stall and 15-minute expiry point.
3. Wait for `proxy_ready`, run team scan and analysis, review clips, create an AI Edit, render, download, preview, save to Photos, and share or open the export.
4. Record the secret-safe installed-device result in `ios/docs/reports/release-device-smoke-report.md`.
5. Produce a launch-grade human-reviewed report meeting the shared 85% team/highlight accuracy gate, or record explicit release-owner risk acceptance.

Build `56` uses `InternalStaging.xcconfig` and the staging Worker. It must not be selected for public App Store review. A future production candidate needs a unique build number higher than `56` plus separate production configuration, metadata, privacy, account, and installed-candidate proof.

## Workflow Commands

Build `56` is already uploaded and its status is already verified. For a later internal build, increment all build guards before rerunning:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
gh workflow run ios-testflight-upload.yml --ref main -f operation=status
```

Do not rerun `operation=upload` for build `56`; App Store Connect build numbers are immutable and cannot be reused.

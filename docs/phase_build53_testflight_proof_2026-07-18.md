# Build 53 TestFlight Proof

Date: 2026-07-18

## Result

Build `53` release SHA `55a402b4b6cc48038306af5eed72367adab15bbf` is uploaded and processed as HoopClips internal TestFlight build `1.0.0 (53)` for bundle ID `atrak.charlie.hoopsclips`.

- PR #92 merged at `f52f443198638d79dce81e5a2d7e4aba117a68fa` with the streamlined AI Edit studio/progress UI and focused policy tests.
- PR #93 merged at `55a402b4b6cc48038306af5eed72367adab15bbf` with build `53` archive/status guard updates.
- PR #94 merged at `920ca9ce69d6144f370f7299457c2fd31681d402` as a documentation-only descendant; it did not change the archived app source.
- Main codecheck run `29667213808`: passed.
- Signed archive/upload run `29667373531`: passed archive, provisioning, metadata/privacy checks, App Store Connect upload, and runner certificate cleanup.
- Read-only status run `29667648668`: `buildFound=true`, `processingState=VALID`, `internalBuildState=IN_BETA_TESTING`, `buildAudienceType=INTERNAL_ONLY`, `readyForInternalTesting=true`, and `expired=false`.

Apple signing, provisioning, upload, and processing are therefore not current blockers.

## Remaining Gates

1. Install `1.0.0 (53)` from TestFlight on the trusted iPhone.
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

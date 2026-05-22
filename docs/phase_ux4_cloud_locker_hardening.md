# Phase UX4 Cloud Locker Hardening

Date: 2026-05-22
Branch: `codex/phase-ux4-cloud-locker-hardening`
Base: `codex/phase-clip1-gpt-reranker-hardening` at `09de976`

## Scope

This branch hardens the My AI Edits / Cloud Locker path for internal iOS launch. It keeps the cloud-first boundary intact:

- Cloud owns render history, download URL minting, retention expiration, and re-render state.
- iOS only lists render metadata, asks cloud for a fresh download URL, downloads the finished MP4, previews, shares, or requests a fresh cloud re-render.
- No local iOS analysis, rendering, composition, or export logic was added.

## Changes

- Added control-plane proxy support for `GET /v1/render-jobs?installId=&limit=` so internal iOS builds pointed at the Worker can load My AI Edits.
- Added control-plane proxy support for `GET /v1/render-jobs/{renderJobId}/download-url` so locker re-download works by render ID.
- Redacted `outputObjectKey` and `renderLogObjectKey` from control-plane client-facing editing responses. The app still receives the short-lived `downloadUrl` when it explicitly asks for one.
- Enforced render expiration before minting download URLs. Expired renders now return `410 render_expired`, steering the app back to cloud re-render.
- Kept direct editing-service storage keys available for internal smoke scripts that inspect renderer artifacts.
- Added iOS tolerance for redacted download payloads by making `CloudEditDownloadResponse.outputObjectKey` optional.
- Added an iOS service test that maps expired/invalid download HTTP statuses `401`, `403`, `404`, and `410` to `CloudEditError.downloadURLExpired`.

## Evidence

Commands run from `/Users/hanfei/rork-hoopshighlights-ai_Final`.

```bash
git fetch origin codex/phase-clip1-gpt-reranker-hardening
git rev-parse HEAD FETCH_HEAD
git checkout -b codex/phase-ux4-cloud-locker-hardening
git push -u origin codex/phase-ux4-cloud-locker-hardening
```

Result: branch created from `09de976e5aebdfa53cf053cb71b2074f62ff4295` and pushed before edits.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
```

Result: `Ran 37 tests ... OK`.

```bash
npm --prefix services/control-plane run typecheck
```

Result: TypeScript typecheck passed.

```bash
npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-editing-proxy.test.ts
```

Result: `tests 11`, `pass 11`, `fail 0`.

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-derived-data \
  -skipPackagePluginValidation \
  -only-testing:HoopsClipsTests/CloudEditServiceTests \
  -skip-testing:HoopsClipsUITests \
  -parallel-testing-enabled NO
```

Result after adding `stopLoading()` to the mock URL protocol: `TEST SUCCEEDED`; Swift Testing ran `1 test in 1 suite`.

The first focused iOS test attempt failed because the mock `URLProtocol` did not implement `stopLoading()`. The implementation was fixed and the focused test passed.

```bash
# XcodeBuildMCP / Build iOS Apps
build_sim(extraArgs: ["-skipPackagePluginValidation"])
```

Result: simulator Debug build `SUCCEEDED`; build log path `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-22T22-00-27-001Z_pid2902_21a1586a.log`.

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-derived-data \
  -skipPackagePluginValidation \
  build-for-testing
```

Result: `TEST BUILD SUCCEEDED`.

```bash
git diff --check
```

Result: passed with no whitespace errors.

Changed-file secret/presigned URL scan:

Result: no matches for AWS/R2 secret names, signature query markers, or URL-query literals. The scan included new docs and iOS test files while leaving unrelated root Xcode project folders unstaged.

## Privacy And Storage

- Control-plane does not log the proxied response payloads.
- Control-plane now strips render storage object keys before returning editing responses to iOS.
- Editing service `download_url.created` telemetry includes only edit/render IDs and plan tier; it does not include the presigned URL, storage credentials, or R2 credentials.
- Full presigned URLs are still returned only to the app from explicit download URL endpoints, because the iOS control surface needs them to download the finished MP4.

## Blockers

- No live post-install TestFlight smoke was run in this branch. It still needs a trusted internal iPhone/TestFlight install and reachable staging backend to verify: install app -> upload/import -> cloud analysis -> Review -> Export -> AI Edit -> render -> preview -> More Hype revision -> revised preview -> share/open-in.
- No live Cloudflare deploy was run in this branch. CI deploy is still gated on `CLOUDFLARE_API_TOKEN` scope and environment wiring.
- No live render job IDs were generated in staging for this branch; validation is unit/integration/simulator-local only.

# Phase UX4 iOS Cloud Edit Service Tests

Date: 2026-05-23
Branch: `codex/phase-ux4-ios-cloud-edit-service-tests`

## Scope

- Added focused iOS tests for CloudEditService render-history and Cloud Locker request contracts.
- Protected iOS as the control surface for render history, re-download links, re-render requests, and revision render requests.
- Did not add local video analysis, composition, rendering, FFmpeg command generation, or storage-key handling to iOS.
- Did not change backend behavior, renderer behavior, feature flags, cloud storage, or production launch config.

## Coverage Added

`ios/HoopsClipsTests/CloudEditServiceTests.swift` now verifies:

- `fetchRenderHistory` calls `GET /v1/render-jobs` with `installId` and `limit`.
- `fetchDownloadURL(renderJobID:)` calls the render-scoped endpoint instead of the edit-job endpoint.
- `requestStoredRender` posts a force-new Cloud Locker re-render request without source object, edit plan, source clip, FFmpeg, or local-render payload.
- `requestRevisionRender` posts to the revision render endpoint with a deterministic revision idempotency key and without source object, edit plan, source clip, FFmpeg, or local-render payload.
- Download URL expiry mapping remains covered for HTTP 401/403/404/410.

## Validation

Commands run:

```sh
xcodebuildmcp test_sim -only-testing:HoopsClipsTests/CloudEditServiceTests -skipPackagePluginValidation
xcodebuildmcp test_sim -only-testing:HoopsClipsTests -skipPackagePluginValidation
```

Results:

- Focused CloudEditService tests: 5 passed, 0 failed.
- Full HoopsClips unit-test target: 60 passed, 0 failed.

## Remaining Launch Blockers

- Signed archive/upload still needs App Store Connect and signing inputs.
- Installed TestFlight smoke still needs a trusted online iPhone.
- Staging Worker `/v1/editing/version` still returns 404 until the Worker is refreshed.
- Cloudflare/GCP deploy credentials still need to be installed and verified through CI.

# Phase Launch139: Fast Cloud Status Checks

## Goal

Make Export feel less stuck when the non-blocking cloud status/version check is slow. The app should fail fast on status metadata, show a clear warning, and still let the user start the real AI Edit request when cloud rendering is otherwise configured.

## Changes

- Added short request timeouts for lightweight cloud metadata calls:
  - `/v1/editing/version`: 8 seconds
  - `/v1/render-jobs`: 12 seconds
- Kept standard signed GET requests at 30 seconds for normal cloud edit/download metadata.
- Preserved existing behavior where transient status-check failures are warnings, not render blockers.
- Updated cloud edit service tests to verify the real HoopClips user agent and the shorter metadata timeouts.

## Architecture Guardrails

- iOS still does not analyze, plan, render, compose, or export production video locally.
- No FFmpeg, Remotion, or Canva runtime was added to iOS.
- No secrets, R2 credentials, or presigned URLs are logged or displayed.
- Real cloud job/create/render/download responses still determine AI Edit state.

## Validation

- Passed: `git diff --check`
- Passed: focused cloud edit service tests on iPhone 17 Pro simulator:
  - `testFetchVersionUsesEditingVersionEndpointAndDecodesGptFlags`
  - `testFetchRenderHistoryUsesRenderJobsEndpointAndLimit`
  - `testFetchDownloadURLByRenderJobUsesRenderScopedEndpoint`
  - Result bundle: `/tmp/hoopclips-launch139-derived-data/Logs/Test/Test-HoopsClips-2026.05.31_18-35-45--0700.xcresult`
- Passed: Debug simulator build for `HoopsClips` on iPhone 17 Pro.
- Existing unrelated warnings remain in `CloudAnalysisService.swift` about `await` on synchronous progress callbacks.

## Notes

- This targets the tester-visible `cloud editing version check failed; request timed out` complaint without hiding real backend failures.
- GitHub Actions should stay skipped for this small iOS client patch because the Actions budget is tight.

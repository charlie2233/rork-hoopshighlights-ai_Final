# Phase AI Edit Status Timeout

## Goal

Reduce the Export screen stall when the advisory cloud editing version check is slow or times out.

The user-facing issue was: `Cloud editing version check failed; request timed out` during Export. The app already treats unknown network failures from `/v1/editing/version` as non-blocking, but the status check waited 15 seconds before showing the non-blocking warning. That made Export feel stuck before the real edit job could start.

## Architecture Guardrail

- Cloud still owns edit planning, GPT clip selection, rendering, storage, and render status.
- iOS still only requests jobs, displays status, previews, downloads, and shares.
- This change does not create local rendering, local analysis, fake ETA text, or simulated backend state.
- The version endpoint remains advisory; edit creation and render polling continue to use authoritative cloud responses.

## Change

- `CloudEditService.fetchVersion()` now uses a 6 second timeout for the advisory `/v1/editing/version` check.
- `AIEditView.refreshCloudEditVersion()` already keeps generic network failures non-blocking, including timeout warnings.
- `CloudEditServiceTests` now verifies the shorter timeout so the app does not regress back to a long preflight stall.

## Expected UX

- If cloud version responds quickly, the app still displays real feature flags and launch-readiness state.
- If cloud version is slow, Export shows the existing warning faster: users can still start the edit, and HoopClips uses the real job response.
- Hard configuration failures such as missing base URL, invalid response, or backend config errors can still block rendering.

## Validation

- `git diff --check` passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing` passed with `** TEST BUILD SUCCEEDED **`.
- Attempted targeted local test: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:HoopsClipsTests/CloudEditServiceTests test`.
  - Result: build phase completed, but CoreSimulator failed during app install/launch with `Invalid device state` and `Mach error -308 - (ipc/mig) server died` before the test bundle could run.
  - No GitHub Actions run was started for this small iOS patch to conserve CI budget.

## Launch Notes

This removes a launch-friction issue without changing backend policy or render behavior. If users still report timeouts after this patch, the next place to inspect is the real edit-job creation endpoint and Cloud Run/Worker latency, not the advisory version endpoint.

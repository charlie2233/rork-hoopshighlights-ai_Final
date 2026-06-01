# Phase Launch186 Cloud Status Copy Clarity

Branch: `codex/phase-launch186-cloud-status-copy-clarity`
Date: 2026-06-01

## Goal

Reduce tester confusion when the AI Edit cloud version check is slow or temporarily unavailable. The status check is non-blocking when cloud rendering is otherwise allowed, so the UI should make that clear without claiming fake progress or hiding real job/render failures.

## Changes

- Increased the AI Edit `/v1/editing/version` timeout from 8 seconds to 15 seconds.
- Changed non-blocking cloud status failures from a warning triangle to an info icon.
- Reworded timeout/error copy to say the user can still start the edit and that HoopClips will rely on the real job response.
- Kept hard render-blocking states unchanged.
- Updated the `CloudEditServiceTests` expectation for the longer timeout.

## Validation

- `git diff --check`
  - Result: passed before the final doc addition.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2 -derivedDataPath .codex-build/DerivedData -only-testing:HoopsClipsTests/CloudEditServiceTests/testFetchVersionUsesEditingVersionEndpointAndDecodesGptFlags test`
  - Result: interrupted after CoreSimulator failed to start the simulator service hub.
  - Error evidence: `DTServiceHubClient failed to bless service hub for simulator Clone 1 of iPhone 17 Pro`.
  - Assessment: simulator infrastructure failure, not a compile failure.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath .codex-build/DerivedData build-for-testing`
  - Result: passed, `TEST BUILD SUCCEEDED`.

## Launch Notes

- This does not fake backend work or fake ETA. It only clarifies that the preflight status check is separate from the real render job response.
- Remaining launch risk: real-device TestFlight smoke still needs to verify import, cloud analysis, AI Edit render, revision, preview, and share/open-in end to end against staging.

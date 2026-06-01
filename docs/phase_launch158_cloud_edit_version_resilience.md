# Phase Launch158 - Cloud Edit Version Resilience

## Goal

Reduce tester friction from the Export AI Edit status check timing out before a real render request is made.

## Architecture Guardrails

- Cloud remains responsible for AI edit planning, rendering, feature flags, and kill switches.
- iOS only checks status, sends validated user choices, displays state, previews, downloads, and shares.
- No local rendering, GPT editing, FFmpeg command generation, or backend simulation was added.

## Changes

- Increased the `/v1/editing/version` request timeout from 8 seconds to 15 seconds so cold staging services have more room to answer.
- Preserved the last known cloud edit version/feature flags after a transient status refresh failure.
  - This avoids losing known kill-switch state after a flaky refresh.
  - Transient status failures remain warnings, not fake success.
  - Hard configuration/backend errors still clear the version state and block rendering.
- Updated the CloudEditService contract test for the new version-status timeout.

## Validation

- Passed `git diff --check`.
- Passed focused simulator verification:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch158-derived-data test -only-testing:HoopsClipsTests/CloudEditServiceTests/testFetchVersionUsesEditingVersionEndpointAndDecodesGptFlags CODE_SIGNING_ALLOWED=NO -quiet`
- Passed broader cloud edit service regression coverage:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch158-derived-data test -only-testing:HoopsClipsTests/CloudEditServiceTests CODE_SIGNING_ALLOWED=NO -quiet`
  - 11 CloudEditServiceTests passed, covering version, render history, download URLs, stored renders, locker rerenders, and revision requests.
- Existing compile warnings remain around `VideoExportService` Sendable captures and `CloudAnalysisService` progress awaits. They were not introduced by this branch.

## Launch Notes

This does not prove staging render health by itself. The real launch gate still needs the installed TestFlight smoke:
import/upload -> cloud analysis -> Review -> AI Edit render -> preview -> revision -> revised preview -> share/open-in.

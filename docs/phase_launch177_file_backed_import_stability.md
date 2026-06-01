# Phase Launch177: File-Backed Import Stability

Branch: `codex/phase-launch177-file-backed-import-stability`

## Goal

Reduce the real-device Photos import symptom where HoopClips can persist a large video, but the current session stays on "Preparing video" until the app is force-closed and reopened.

## Findings

- The current Photos import path was already file-backed only.
- `Data.self`, `DataRepresentation`, and full-video memory fallback are not present in the Photos import path.
- Photos imports already support `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- Project copy and thumbnail generation are mostly off-main via detached work in `ProjectHistoryStore`.
- The remaining launch risk was import completion cleanup/reconciliation: a successful import could wait on nonessential temporary-file cleanup or miss a late visible-project state flip.

## Changes

- Photos temporary file removal is now scheduled as background cleanup after the imported video is copied into the HoopClips project library.
- Successful import completion now reconciles the current project state before deciding whether to keep showing the import UI.
- Added a short completion grace pass for the case where project persistence returns before SwiftUI observes `isVideoLoaded`.
- Added `HighlightsViewModel.reconcileCurrentProjectLoadState()` so the import surface can reopen the current persisted project record without adding local analysis, rendering, or export behavior.
- Added security-scoped access around file-backed Photos transfer copying.

## Architecture Check

- iOS still only imports, previews, uploads, reviews, exports status, downloads, and shares.
- No local production analysis, GPT selection, edit planning, FFmpeg command generation, rendering, or composition was added.
- No secrets, R2 credentials, or presigned URLs are logged.
- Import status remains real import/project state. No fake thinking/ETA copy was added.

## Validation

Passed:

```bash
git diff --check
```

Passed:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-launch177-derived-data \
  CODE_SIGNING_ALLOWED=NO \
  build-for-testing \
  -quiet
```

Passed:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-launch177-derived-data \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/testVideoImportPolicyUsesFileBackedVideoTypesOnly \
  -only-testing:HoopsClipsTests/testVideoImportPreflightAcceptsLongerFourMinuteThirtyEditSource \
  -only-testing:HoopsClipsTests/testResetProjectClearsVisibleVideoForAccountBoundary \
  -quiet
```

Notes:

- Build iOS Apps MCP `session_show_defaults` failed because the MCP transport closed, so local `xcodebuild` was used.
- A first test command with `generic/platform=iOS Simulator` failed because tests require a concrete simulator destination.
- A parallel early test attempt hit SPM dependency resolution before the build cache was ready; the focused concrete simulator retry passed.

## Remaining Real-Device Smoke

Needs manual or connected-device confirmation on the wired iPhone:

1. Install fresh build.
2. Import the same large Photos video that previously stuck on "Preparing video".
3. Confirm the screen opens the project without force-closing the app.
4. Confirm cloud team scan starts only after consent and real cloud state.
5. Continue TestFlight smoke: analysis -> Review -> AI Edit -> render -> preview -> revision -> share/open-in.

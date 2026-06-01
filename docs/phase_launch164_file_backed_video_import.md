# Phase Launch164 File-Backed Video Import

## Goal

Reduce the real-device "Preparing video" stuck state reported during large iPhone imports.

## Findings

- The current Photos path is already file-backed only.
- `ImportedVideoFile` already supports `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- There is no `Data.self` fallback in `VideoPlayerView.swift`.
- The main remaining risk found in this pass was a watchdog race: if the project loaded but import UI state failed to clear, the timeout path could still show an import failure.

## Change

- The import watchdog now checks `viewModel.isVideoLoaded` before showing the slow reminder and before timeout failure.
- If the video is already loaded, HoopClips clears the import state, starts the team scan if eligible, and records a non-secret recovery checkpoint.

## Guardrails

- No local analysis, rendering, composition, or export was added.
- Photos import remains file-backed.
- No full videos, paths, presigned URLs, secrets, or storage credentials are logged.

## Validation

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-launch164-derived-data \
  build-for-testing CODE_SIGNING_ALLOWED=NO -quiet

xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-launch164-derived-data \
  test -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -quiet
```

## Launch Notes

This does not replace a real wired-iPhone import smoke. Before TestFlight submission, retest:

1. Fresh install.
2. Import a large Photos video.
3. Confirm the import screen clears without app restart.
4. Confirm team scan starts or asks for cloud consent.
5. Confirm closing/reopening does not resurrect another user's video after sign-out.

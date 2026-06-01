# Phase Import1 - File-Backed Photos Import Recovery

Date: 2026-06-01
Branch: `codex/phase-import1-file-backed-photos-import`

## Goal

Fix the real app flow behind reports where Photos import stays on "Preparing video" even though reopening the app shows the project imported successfully.

## Findings

- The Photos import path is already file-backed only.
- No `Data.self` fallback is present.
- Supported transfer types already include `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- Video copy and thumbnail generation already run through detached/background work.
- The remaining failure mode matched an import state/UI recovery issue: the project can be saved while the visible import state keeps waiting.

## Change

- `VideoPlayerView` now observes `scenePhase` and reconciles the saved project whenever the app becomes active.
- Import completion now calls `reconcileCurrentProjectLoadState()` before keeping or clearing the import spinner.
- Successful recovery syncs the player URL immediately, clears import state, and starts the team scan path when appropriate.

## Architecture

- No local iOS video analysis, rendering, composition, or export was added.
- iOS remains the import/control surface.
- The change only improves import state recovery and video preview handoff.

## Evidence

Commands run:

```bash
git diff --check
```

Result: passed.

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyUsesFileBackedVideoTypesOnly
```

Result: `** TEST SUCCEEDED **`.

## Remaining Blockers

- Needs real iPhone confirmation with a large Photos video after reconnecting the device.
- If the real device still hangs, next target is collecting device logs around `video_import.persisted`, `video_import.visible`, and `video_import.loaded_but_not_visible`.
- Internal launch still requires the full TestFlight smoke and real cloud edit render/revision/share proof.

# Phase Launch90: Import Preparation Feedback

Date: 2026-05-30
Branch: `codex/phase-launch70-editing-analysis-progress`

## Scope

Reduce the user-visible risk behind "Preparing video" appearing stuck during large video import.

This phase only touches iOS import/library handling, which is allowed under the cloud-first architecture. It does not add iOS video analysis, rendering, composition, or export.

## Change

- Added honest import status phases in `VideoPlayerView`:
  - `Preparing video...`
  - `Reading video from Photos...`
  - `Copying video into HoopClips...`
- Updated the import button and accessibility labels/values to use the current import phase.
- Moved the imported source-video copy inside `ProjectHistoryStore.createProjectFromImportedVideo` onto a detached utility task so a large file copy is less likely to block the UI while the import status is visible.

## Validation

Commands run:

```text
build_sim
test_sim
git diff --check
```

Results:

- iOS Debug simulator build: passed.
- Full simulator test result bundle: passed, 98 passed, 4 skipped, 0 failed, 102 total.

Expected behavior:

- Photos import still uses file-backed transfer only.
- Files import and Photos import both show a concrete local import phase before the project is loaded.
- Cancel import remains available while the import task is active.

## Remaining Risk

Real-device import still needs a physical iPhone smoke once the device is available to Xcode again. The current submission preflight still reports the wired iPhone as detected but unavailable for install/smoke testing.

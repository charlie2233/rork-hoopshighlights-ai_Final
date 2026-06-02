# Phase Project I/O Polish

Branch: `codex/phase-project-io-polish`

## Goal

Move HoopClips closer to internal TestFlight readiness by reducing the chance that a successful video import stays stuck on the import status UI until the user closes and reopens the app.

## Current Import Audit

The Photos import path already has the important file-backed safeguards:

- `Data.self` fallback is absent.
- Photos import uses file-backed `Transferable` loading.
- Supported transfer/content types include `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- File copy work happens through detached tasks and `ProjectHistoryStore`.

So this phase does not re-add or duplicate that work.

## Change

- Added a temp-root test seam to `ProjectHistoryStore` so project-library recovery can be tested without touching real app history.
- Added `HighlightsViewModel.recoverVisibleProjectFromStoreIfNeeded()`.
- Updated the import status UI to use that recovery path for:
  - active-scene recovery
  - current-project changes
  - import completion
  - import watchdog polling
- Updated long-running import copy to say HoopClips will open a finished import here when possible.

## Why It Helps

The real-device symptom was: import appears stuck on "Preparing video," but closing and reopening the app shows the project was saved. This new recovery path mirrors the relaunch behavior while the app is still open by reloading the persisted project library and applying the current project if the source file exists.

## Architecture

- iOS still only handles import, local project persistence, playback, status, and cloud handoff.
- No local video analysis, local rendering, composition, Remotion, Canva, or GPT work was added.
- Cloud ownership of analysis, edit planning, rendering, and storage remains unchanged.
- Background work copy stays honest:
  - import/upload tells users to keep HoopClips open until cloud handoff
  - cloud analysis and AI Edit render reminders tell users they can switch apps after the backend job starts
  - the app refreshes real backend job status when reopened

## Validation

Local validation completed on June 2, 2026, without using GitHub Actions:

```bash
git diff --check
xcodebuildmcp test_sim -only-testing:HoopsClipsTests
xcodebuildmcp build_sim
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' -derivedDataPath /Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClipsCodex build-for-testing CODE_SIGNING_ALLOWED=NO
```

Results:

- `git diff --check`: passed.
- `HoopsClipsTests`: 173 passed, 0 failed, 0 skipped.
- Debug simulator build: passed.
- Debug build-for-testing: passed.
- Test result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-02T08-02-36-617Z_pid26025_039240c1.xcresult`.

## Remaining Launch Notes

- Needs real-device smoke with a large Photos video: import, visible project open, cloud team scan, team selection, analysis, Review, AI Edit render, preview, revision, and share/open-in.
- If a Photos asset is still only available in iCloud and cannot provide a local file-backed transfer, the app should keep showing the existing Files/import recovery path.

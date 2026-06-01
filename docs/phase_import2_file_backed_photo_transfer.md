# Phase Import2 File-Backed Photo Transfer

## Goal

Fix the real-device "Preparing video" hang path and keep improving AI/team accuracy without moving analysis or rendering into iOS.

## Changes

- Kept Photos import file-backed only; no `Data.self` fallback was reintroduced.
- Added an import recovery poll in `VideoPlayerView` that reconciles the saved project every 2 seconds during import.
- Reused the same reconciliation path for slow watchdog, timeout watchdog, successful load, and `didLoadVideo == false` cases.
- Raised the interactive GPT team prescan budget from 12 to 20 candidate clips, rich candidates from 8 to 12, per-clip frames from 4 to 5, total clip frames from 56 to 96, and timeout floor from 60s to 75s.
- Updated backend docs so the full team quick-scan rich default matches the current 320-candidate code path.

## Architecture Notes

- iOS still only imports, displays status, recovers saved project state, and starts cloud team scan/analysis.
- Cloud backend still owns team attribution, analysis, GPT selection, edit planning, rendering, and storage.
- No full videos are sent to GPT; team prescan uses sampled frames from bounded candidate clips.
- Uncertain team clips stay reviewable instead of being promoted to confident selected-team renders.
- No secrets, R2 credentials, or presigned URLs are logged.

## Validation

- `git diff --check` -> passed.
- `PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests -v` -> 40 tests passed.
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests -v` -> 76 tests passed.
- `PYTHONPATH=services/editing:ios/backend ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_team_scan_endpoint_uses_editing_secret_and_redacts_source_details -v` -> 1 test passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing` -> `** TEST BUILD SUCCEEDED **`.

Two earlier targeted `unittest` commands used stale test method names and failed before running assertions. They were replaced by the full current suites above.

## Remaining Launch Evidence Needed

- Real iPhone smoke after reconnect: import Photos video, confirm it leaves Preparing without app restart, team choices appear, analysis runs, Review opens, AI Edit render/revision/share works.
- Real labeled-footage accuracy report is still required before claiming the 85% selected-team/highlight target.

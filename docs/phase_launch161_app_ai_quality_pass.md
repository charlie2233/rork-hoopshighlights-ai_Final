# Phase Launch161 App + AI Quality Pass

Branch: `codex/phase-launch161-app-ai-quality-pass`

## Goal

Keep work on the app and highlight accuracy rather than logo polish. This pass targets two launch-quality issues:

- Import reliability: avoid a stale "Preparing video" state after the project has already been persisted and restored.
- GPT-led highlight quality: give the free/default GPT editor enough visual context to judge setup and outcome, not only start/event-center/finish.

## Changes

- `ios/HoopsClips/HoopsClips/Views/VideoPlayerView.swift`
  - Added completed-import recovery when `videoURL` or `currentProjectID` changes.
  - `finishVideoImport` now clears the import UI whenever `viewModel.isVideoLoaded` is true, even if the async import operation reports a late false state.
  - This keeps the fix in iOS import/status UI only. It does not add local production analysis, rendering, or composition.

- `ios/HoopsClips/HoopsClips/Services/CloudAnalysisService.swift`
  - Removed unnecessary `await` on synchronous main-actor progress callbacks.

- `ios/HoopsClips/HoopsClips/Services/VideoExportService.swift`
  - Removed the Swift concurrency warning from local export progress polling by keeping the AVFoundation progress read main-actor confined.

- `services/editing/editing_app/gpt_reranker.py`
  - Raised the default free-tier GPT keyframes per clip from 3 to 5.
  - The default sampled roles now include start, eventCenter, finish, preEvent, and outcome context.
  - The environment override remains bounded by the existing 3-10 range.

- `services/editing/tests/test_gpt_reranker.py`
  - Updated the sampling-limit expectation.
  - Added coverage that free/default GPT sampling includes setup and outcome roles.

## Architecture Notes

- Cloud still owns candidate analysis, GPT clip selection, edit planning, rendering, storage, and revisions.
- iOS remains the control surface for import/status/review/export/share.
- GPT still receives candidate clips and sampled keyframes only, never full videos.
- GPT still cannot output raw FFmpeg commands or bypass backend validators.

## Validation

- `git diff --check` passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest services.editing.tests.test_gpt_reranker`
  - 64 tests passed.
- `PYTHONPATH=/tmp/hoopclips-launch159-pydeps:ios/backend:services/editing /Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest ios.backend.tests.test_pipeline_quality ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker services.editing.tests.test_editing_service`
  - 276 tests passed.
  - First attempt without `/tmp/hoopclips-launch159-pydeps` failed to import `fastapi`; rerun with the existing local dependency path passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch161-derived-data build-for-testing CODE_SIGNING_ALLOWED=NO -quiet`
  - Passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch161-derived-data test -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -quiet`
  - Passed.

## Remaining Launch Gaps

- Real-device smoke still needs an installed-app run: import -> team scan -> cloud analysis -> Review -> AI Edit -> render -> preview -> revision -> share/open-in.
- Labeled accuracy proof still needs a real labeled clip bundle or user labeling pass.

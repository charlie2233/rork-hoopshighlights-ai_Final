# HoopClips UI Edit V2 Work Report

Branch: `feat/ui-edit-v2`  
Implementation commit: `46cc8313`  
Source brief: `HoopsClips 增强研究报告.docx`

## Summary

The incomplete UI agent work was finished as a workflow-first HoopClips app shell with four primary sections: Uploads, Review, AI Edit, and Exports. The implementation keeps the cloud-first architecture intact: iOS is the control surface for upload, review, edit requests, render status, preview, download, save, and share, while backend services remain responsible for analysis, edit planning, and production rendering.

## Implemented Work

### Workflow Shell

- Reworked the app navigation around `Uploads`, `Review`, `AI Edit`, and `Exports`.
- Preserved utility access to History and Settings without keeping them as primary workflow tabs.
- Added workflow-focused accessibility identifiers for UI smoke coverage.

Key files:

- `ios/HoopsClips/HoopsClips/ContentView.swift`
- `ios/HoopsClips/HoopsClips/Models/WorkflowState.swift`
- `ios/HoopsClips/HoopsClips/Views/UploadsWorkflowView.swift`
- `ios/HoopsClips/HoopsClips/Views/ExportView.swift`

### Uploads

- Added an Uploads workflow screen with an upload queue panel.
- Added `UploadAssetQueueContract` and `UploadQueueProjection` so the UI can consume asset-first upload fields when available.
- Supported canonical asset fields: `assetId`, `storageKey`, `proxyKey`, `status`, byte progress, `analysisJobId`, clip count, and failure reason.
- Kept legacy current-job display as a fallback, without pretending a legacy source object is a proxy-ready asset.
- Added asset-status lifecycle handling for `initialized`, `uploading`, `uploaded`, `processing`, `proxy_ready`, `ready`, and `failed`.

### Review

- Added Review sort modes for score, confidence, label, and time.
- Preserved keep/discard and team-aware review decisions.
- Added boundary nudge controls for clip start/end metadata.
- Added keyboard shortcuts:
  - `K` keep
  - `D` discard
  - `N` legacy Nah compatibility
  - `1`-`5` review feedback tags
  - `[` and `]` boundary nudges
- Expanded review feedback tags to five keyboard-addressable labels: Duplicate, Wrong team, Bad window, Wrong label, and Low quality.

Key files:

- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`
- `ios/HoopsClips/HoopsClips/Models/Clip.swift`
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`

### AI Edit

- Promoted AI Edit into its own primary workflow section.
- Preserved cloud-backed style, duration, aspect ratio, prompt, plan preview, render request, render polling, download, preview, save, and share behavior.
- Added live additive schema fields to `CreateCloudEditJobRequest`:
  - `assetId`
  - `sourceClipIds`
- Preserved `sourceObjectKey` and full candidate `clips` for current backend compatibility.
- Updated backend and Worker request types to accept the additive fields.

Key files:

- `ios/HoopsClips/HoopsClips/Models/CloudEditTypes.swift`
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
- `ios/backend/app/editing.py`
- `services/control-plane/src/types.ts`

### Exports

- Changed Exports into an output-focused section.
- Added render-output state display based on the latest AI Edit render status.
- Kept Exports responsible for downloaded MP4 preview, save, and share actions.
- Restored the local AVFoundation fallback outro duration to `0.0` so branding/outros remain cloud-rendering policy instead of a local black-tail effect.

### Documentation

Added or updated handoff docs:

- `CONTRACT.md`
- `UI_ARCH.md`
- `KEYBOARD_SHORTCUTS.md`
- `EDIT_PLAN_SCHEMA.md`
- `MERGE_GUIDE.md`
- `TODO_INTEGRATION.md`
- `UI_EDIT_V2_WORK_REPORT.md`

## Verification

Passed:

- `git diff --check`
- `git diff --cached --check`
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -quiet`
- `xcodebuild test-without-building -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:HoopsClipsTests/WorkflowStateTests -quiet`
- Targeted tests for edit request encoding, asset queue decode, and local outro behavior
- Workflow UI smoke:
  - `HoopsClipsUITests/testWorkflowSectionsNavigateEndToEndWithSmokeFixture`

Notes:

- Full `HoopsClipsTests` printed passing test cases but hit Xcode finalization/log-runner cleanup and was interrupted after the known long-tail hang. Focused lanes for the changed behavior passed.
- Build warnings from `CloudAnalysisService.swift` were pre-existing Swift actor/deprecation warnings, not introduced by this UI branch.

## Review Results

Two subagent reviews were used:

- Spec compliance review initially found gaps in upload contract consumption, AI Edit asset schema, and `1`-`5` shortcut coverage.
- Code-quality review found P2 risks around stale render state, proxy/source conflation, duplicate upload row identity, and local fallback outro policy.

All blocking/spec issues and reviewed P2 items were addressed before commit:

- Upload asset rows now require real asset fields.
- Upload queue row identity uses `assetId`.
- AI Edit sends additive `assetId` and `sourceClipIds`.
- Five feedback tags back the `1`-`5` shortcuts.
- Latest render status clears with source/project changes.
- Local fallback outro duration is back to `0.0`.

## Remaining Integration Notes

- When the upload-pipeline branch lands, feed its canonical asset DTOs into the view model asset fields used by `UploadsWorkflowView`.
- Keep `sourceObjectKey` and full `clips` in edit requests until backend editing no longer needs the compatibility payload.
- Re-run full unit and UI smoke lanes after merging upload, detection, and UI branches together.

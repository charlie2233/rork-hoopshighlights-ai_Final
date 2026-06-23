# Merge Guide: Workflow-First UI With Asset Uploads

## Summary

This branch integrates Agent A's asset-first upload pipeline with Agent B's workflow-first iOS UI. The app shell becomes Uploads, Review, AI Edit, and Exports while keeping History and Settings secondary. Upload and AI Edit state continue to flow through the canonical cloud/backend contracts.

## Key Files

- `CONTRACT.md`: integrated upload, workflow, AI Edit, and compatibility contract.
- `TODO_INTEGRATION.md`: remaining backend/UI/edit-agent follow-up checklist.
- `ios/backend/app/models.py`: asset/upload API models and job response asset fields.
- `ios/backend/app/upload_storage.py`: local disk and object-storage-compatible upload adapters.
- `ios/backend/app/asset_store.py`: in-memory and Firestore asset stores.
- `ios/backend/app/api.py`: upload init/complete/status routes, proxy-ready gate, and asset-backed inference materialization.
- `ios/backend/tests/test_upload_pipeline.py`: upload lifecycle coverage.
- `ios/backend/scripts/upload_benchmark.py`: timing and retry/resume benchmark.
- `ios/HoopsClips/HoopsClips/Models/CloudAnalysisTypes.swift`: asset upload/status/job contract models.
- `ios/HoopsClips/HoopsClips/Services/CloudAnalysisService.swift`: asset-first upload, proxy-ready wait, asset team scan, asset analysis start, and asset resume bridge.
- `ios/HoopsClips/HoopsClips/Models/WorkflowState.swift`: upload queue and workflow navigation projections.
- `ios/HoopsClips/HoopsClips/Views/UploadsWorkflowView.swift`: Uploads workflow surface.
- `ios/HoopsClips/HoopsClips/ContentView.swift`: primary workflow navigation and secondary History/Settings routes.
- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`: feedback tags, boundary nudges, and hardware-key shortcuts.
- `ios/HoopsClips/HoopsClips/Views/AIEditView.swift`: dedicated AI Edit workflow surface using cloud edit services.
- `ios/HoopsClips/HoopsClips/Views/ExportView.swift`: rendered/downloaded MP4 export surface.
- `ios/HoopsClipsTests/WorkflowStateTests.swift`: workflow projection tests.
- `ios/HoopsClipsUITests/HoopsClipsUITests.swift`: workflow UI navigation smoke.
- `services/control-plane/src/types.ts`: additive `assetId/storageKey` fields.
- `services/control-plane/src/routes/public.ts`: Worker create/poll payloads expose `assetId`; internal team-scan payloads carry `assetId/storageKey`.
- `services/control-plane/src/queue/consumer.ts`: inference dispatch includes `assetId/storageKey`.

## Integration Notes

- Review's existing `review.continueToExportButton` accessibility ID is preserved for compatibility, but it routes to the AI Edit tab.
- Uploads keeps History and Settings as utility sheet routes, not primary workflow tabs.
- `UploadQueueProjection.items(assets:)` consumes Agent A's asset queue fields and keeps `proxy_ready` as ready for analysis until clip review results arrive.
- `UploadQueueProjection` is display-only. Do not persist it or expose it as a backend DTO.
- `ExportView(viewModel:)` still defaults to embedding AI Edit for legacy callers. `ContentView` passes `showsAIEditAgentSection: false`.
- `CreateCloudEditJobRequest` carries additive `assetId` and `sourceClipIds` fields while preserving `sourceObjectKey` and full `clips` for the current editing backend.
- AI Edit mirrors latest cloud render status into `HighlightsViewModel.latestCloudEditRenderStatus`; Exports reads it but still only handles downloaded MP4 output.
- Boundary nudges clamp clip timing and event center; they do not create local renders or local edit plans.
- Public Worker responses continue redacting object keys. Internal dispatch can carry `assetId/storageKey`.
- Legacy manual URL analysis remains compatibility-only.

## Risk Areas

- `CloudAnalysisTypes.swift` is shared by upload models and workflow projections; keep field additions additive.
- Local post-upload processing attempts FFmpeg/ffprobe proxy and thumbnail generation, then falls back safely for invalid local test bytes.
- Managed mode still needs a durable post-upload queue; local processing is inline for deterministic tests.
- UI tests need the existing smoke flag for the full fixture path.
- Do not reintroduce a second AI editor in Exports.

## Verification Commands

```bash
cd /Users/hanfei/hc-workflow-first-ui
PYTHONPATH=ios/backend python3 -m unittest ios.backend.tests.test_upload_pipeline
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:HoopsClipsTests
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClipsUITests -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:HoopsClipsUITests/testWorkflowSectionsNavigateEndToEndWithSmokeFixture OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE'

cd services/control-plane
npm test
npm run typecheck
```

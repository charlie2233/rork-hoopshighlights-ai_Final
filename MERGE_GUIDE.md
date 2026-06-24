# Merge Guide: Workflow, Upload, Detection, And AI Edit

## Summary

This branch integrates Agent A's asset-first upload pipeline, the detection v2 accuracy pipeline, Agent B's AI Edit engine contracts, and the workflow-first iOS UI. The app shell becomes Uploads, Review, AI Edit, and Exports while upload, detection, review, edit, render, and export state continue to flow through canonical cloud/backend contracts.

## Key Files

- `CONTRACT.md`: integrated upload, workflow, detection, AI Edit, durability, and compatibility contract.
- `TODO_INTEGRATION.md`: remaining backend/UI/detection/edit-agent checklist.
- `docs/DETECTION_PIPELINE.md`, `docs/MODEL_REGISTRY.md`, `docs/MIGRATION_NOTES.md`: detection v2 architecture and migration notes.
- `ios/backend/app/models.py`: asset/upload, detection, and job response models.
- `ios/backend/app/upload_storage.py`: local disk and object-storage-compatible upload adapters.
- `ios/backend/app/asset_store.py`: in-memory and Firestore asset stores.
- `ios/backend/app/api.py`: upload init/complete/status routes, proxy-ready gates, detection v2 route, and asset-backed inference materialization.
- `ios/backend/app/detection_pipeline.py`: staged proposal, rerank, classify, merge, and taxonomy detection pipeline.
- `ios/backend/app/taxonomy.py`, `ios/backend/app/model_registry.py`, `ios/backend/app/data/basketball_taxonomy.json`: canonical label mapping and model metadata.
- `ios/backend/tests/test_upload_pipeline.py`, `ios/backend/tests/test_detection_pipeline.py`: backend upload and detection coverage.
- `scripts/benchmark_detection_pipeline.py`, `ios/backend/scripts/upload_benchmark.py`: timing, retry/resume, and detection benchmark CLIs.
- `ios/HoopsClips/HoopsClips/Models/CloudAnalysisTypes.swift`: asset upload/status/job contract models.
- `ios/HoopsClips/HoopsClips/Services/CloudAnalysisService.swift`: asset-first upload, proxy-ready wait, asset team scan, asset analysis start, and asset resume bridge.
- `ios/HoopsClips/HoopsClips/Models/WorkflowState.swift`: upload queue and workflow navigation projections.
- `ios/HoopsClips/HoopsClips/Views/UploadsWorkflowView.swift`: Uploads workflow surface.
- `ios/HoopsClips/HoopsClips/ContentView.swift`: primary workflow navigation and secondary History/Settings routes.
- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`: feedback tags, boundary nudges, and hardware-key shortcuts.
- `ios/HoopsClips/HoopsClips/Views/AIEditView.swift`: dedicated AI Edit workflow surface using cloud edit services.
- `ios/HoopsClips/HoopsClips/Views/ExportView.swift`: rendered/downloaded MP4 export surface.
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`: asset/edit candidate contract bridge and AI Edit input signature.
- `ios/HoopsClipsTests/WorkflowStateTests.swift`, `ios/HoopsClipsTests/HoopsClipsTests.swift`: workflow and edit contract tests.
- `ios/HoopsClipsUITests/HoopsClipsUITests.swift`: workflow UI navigation smoke.
- `services/control-plane/src/types.ts`: additive asset, storage, and detection fields.
- `services/control-plane/src/routes/public.ts`: Worker create/poll payloads, legacy aliases, and internal dispatch fields.
- `services/control-plane/src/queue/consumer.ts`: inference dispatch includes asset/storage identifiers.
- `services/editing/editing_app/main.py`: editing service detection/edit handoff.
- `services/editing/tests/test_editing_service.py`: editing service dispatch and detection v2 coverage.

## Integration Notes

- Review's existing `review.continueToExportButton` accessibility ID is preserved for compatibility, but it routes to the AI Edit tab.
- Uploads keeps History and Settings as utility sheet routes, not primary workflow tabs.
- `UploadQueueProjection.items(assets:)` consumes Agent A's asset queue fields and keeps `proxy_ready` as ready for analysis until clip review results arrive.
- `UploadQueueProjection` is display-only. Do not persist it or expose it as a backend DTO.
- `ExportView(viewModel:)` still defaults to embedding AI Edit for legacy callers. `ContentView` passes `showsAIEditAgentSection: false`.
- `CreateCloudEditJobRequest` carries additive `assetId` and `sourceClipIds` fields while preserving `sourceObjectKey` and full `clips` for the current editing backend.
- AI Edit mirrors latest cloud render status into `HighlightsViewModel.latestCloudEditRenderStatus`; Exports reads it but still only handles downloaded MP4 output.
- AI Edit state resets when asset identity, source object key, analysis job, team selection, or candidate clips change.
- Boundary nudges clamp clip timing and event center; they do not create local renders or local edit plans.
- Detection v2 keeps `/v2/detection/analyze` as an internal validation route. Mobile upload continues through asset upload and analysis job routes.
- Review and edit consumers should prefer `results.candidateClips ?? results.clips`.
- Candidate ordering should prefer `rankScore` or `scores.finalScore` when present while preserving quality gates for team attribution and native shot signals.
- Public Worker responses continue redacting object keys. Internal dispatch can carry `assetId/storageKey`.
- Legacy manual URL analysis remains compatibility-only.
- Do not make iOS perform local detection or rendering.

## Risk Areas

- `CloudAnalysisTypes.swift` is shared by upload models and workflow projections; keep field additions additive.
- Local post-upload processing attempts FFmpeg/ffprobe proxy and thumbnail generation, then falls back safely for invalid local test bytes.
- Managed mode still needs provider-side object-storage smoke proof.
- Detection v2 currently defines adapter contracts and deterministic fallbacks; real OpenCLIP/SigLIP and R2Plus1D runtime loading should stay behind the adapter interfaces without changing response shapes.
- UI tests need the existing smoke flag for the full fixture path.
- Do not reintroduce a second AI editor in Exports.

## Verification Commands

```bash
cd /Users/hanfei/hc-enhancement-integration

uv run --with-requirements ios/backend/requirements.txt --python 3.11 python -m py_compile \
  ios/backend/app/api.py ios/backend/app/models.py ios/backend/app/editing.py ios/backend/app/rendering.py \
  ios/backend/app/detection_pipeline.py ios/backend/app/model_registry.py ios/backend/app/taxonomy.py \
  services/editing/editing_app/main.py

uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend python -m unittest \
  ios.backend.tests.test_upload_pipeline ios.backend.tests.test_detection_pipeline -v

uv run --with-requirements ios/backend/requirements.txt --python 3.11 env PYTHONPATH=ios/backend:services/editing python -m unittest \
  services.editing.tests.test_editing_service -v

uv run --with-requirements ios/backend/requirements.txt --python 3.11 python scripts/benchmark_detection_pipeline.py --json

npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test

xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  -derivedDataPath ios/build/DerivedData \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditInputSignatureTracksSourceAssetAndCandidateChanges
```

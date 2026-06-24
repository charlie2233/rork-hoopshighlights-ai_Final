# Merge Guide: Multimodal Rerank Integration

## Summary

This branch starts from the workflow-first enhancement integration and adds Detection V2. It preserves asset-first upload, workflow-first iOS navigation, and AI Edit contracts while adding backend-owned multimodal/basketball-aware candidate reranking and evaluation.

## Key Files

- `CONTRACT.md`: integrated upload, workflow, AI Edit, detection, rerank, and compatibility contract.
- `TODO_INTEGRATION.md`: remaining backend/UI/edit-agent checklist.
- `docs/DETECTION_PIPELINE.md`: Detection V2 architecture.
- `docs/MIGRATION_NOTES.md`: compatibility and rollout notes.
- `docs/MODEL_REGISTRY.md`: model/provider registry notes.
- `ios/backend/app/api.py`: upload routes, analysis compatibility routes, and detection route registration.
- `ios/backend/app/detection_pipeline.py`: staged proposal, rerank, classifier, merge, taxonomy pipeline.
- `ios/backend/app/model_registry.py`: model/provider registry interfaces.
- `ios/backend/app/taxonomy.py`: basketball taxonomy mapper.
- `ios/backend/app/data/basketball_taxonomy.json`: product taxonomy and labels.
- `ios/backend/tests/test_detection_pipeline.py`: Detection V2 coverage.
- `scripts/benchmark_detection_pipeline.py`: benchmark/eval CLI.
- `ios/HoopsClips/HoopsClips/Models/CloudAnalysisTypes.swift`: asset upload/status/job contract models.
- `ios/HoopsClips/HoopsClips/Services/CloudAnalysisService.swift`: asset-first upload, proxy-ready wait, asset team scan, asset analysis start, and resume bridge.
- `ios/HoopsClips/HoopsClips/Models/WorkflowState.swift`: upload queue and workflow navigation projections.
- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`: feedback tags, boundary nudges, and hardware-key shortcuts.
- `ios/HoopsClips/HoopsClips/Views/AIEditView.swift`: dedicated AI Edit workflow surface using cloud edit services.
- `ios/HoopsClips/HoopsClips/Views/ExportView.swift`: rendered/downloaded MP4 export surface.
- `services/control-plane/src/types.ts`: additive asset and candidate fields.
- `services/control-plane/src/routes/public.ts`: Worker create/poll payloads and internal detection/edit dispatch.
- `services/editing/editing_app/main.py`: edit-service candidate ordering and compatibility.

## Integration Notes

- The public mobile upload path can remain `/v1/analysis/*`; Detection V2 is additive through `/v2/detection/analyze` and compatibility aliases.
- Review's existing `review.continueToExportButton` accessibility ID is preserved for compatibility, but routes to the AI Edit tab.
- Uploads keeps History and Settings as utility sheet routes, not primary workflow tabs.
- `UploadQueueProjection.items(assets:)` consumes Agent A's asset queue fields and keeps `proxy_ready` as ready for analysis until clip review results arrive.
- `UploadQueueProjection` is display-only. Do not persist it or expose it as a backend DTO.
- `ExportView(viewModel:)` still defaults to embedding AI Edit for legacy callers. `ContentView` passes `showsAIEditAgentSection: false`.
- `CreateCloudEditJobRequest` carries additive `assetId` and `sourceClipIds` fields while preserving `sourceObjectKey` and full `clips` for the current editing backend.
- AI Edit mirrors latest cloud render status into `HighlightsViewModel.latestCloudEditRenderStatus`; Exports reads it but still only handles downloaded MP4 output.
- Boundary nudges clamp clip timing and event center; they do not create local renders or local edit plans.
- Public Worker responses continue redacting object keys. Internal dispatch can carry `assetId/storageKey`.
- Legacy manual URL analysis remains compatibility-only.
- New clients should read `results.candidateClips ?? results.clips`.
- Edit planning should prefer `rankScore` or `scores.finalScore` when present and preserve existing team/native-shot/auto-keep gates.
- Rerank provenance belongs in diagnostics/reviewer tooling unless product intentionally promotes it.

## Risk Areas

- `CloudAnalysisTypes.swift` is shared by upload models and workflow projections; keep field additions additive.
- Local post-upload processing attempts FFmpeg/ffprobe proxy and thumbnail generation, then falls back safely for invalid local test bytes.
- Managed mode uses durable post-upload queue semantics; local processing can be inline for deterministic tests.
- Detection V2 must stay kill-switchable and fall back to heuristic + HoopCut/autohighlight behavior.
- Do not expose object keys, signed URLs, provider secrets, or full paths in iOS UI/Worker public responses.
- Do not reintroduce a second AI editor in Exports.

## Verification Commands

```bash
cd /Users/hanfei/hc-multimodal-rerank
PYTHONPATH=ios/backend python3 -m unittest ios.backend.tests.test_detection_pipeline
PYTHONPATH=ios/backend python3 -m unittest ios.backend.tests.test_upload_pipeline
PYTHONPATH=ios/backend python3 -m unittest ios.backend.tests.test_clip_accuracy_evaluation
PYTHONPATH=ios/backend:services/editing python3 -m unittest services.editing.tests.test_editing_service
python3 scripts/benchmark_detection_pipeline.py --json

cd /Users/hanfei/hc-multimodal-rerank/services/control-plane
npm test
npm run typecheck

cd /Users/hanfei/hc-multimodal-rerank
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:HoopsClipsTests
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClipsUITests -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:HoopsClipsUITests/testWorkflowSectionsNavigateEndToEndWithSmokeFixture OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE'
```

# Merge Guide: `feat/ui-edit-v2`

## Summary

This branch turns the app shell into Uploads, Review, AI Edit, and Exports. It keeps existing cloud-first services and review decisions intact while adding an asset-aware Uploads queue projection, Review keyboard shortcuts, Review boundary nudges, AI Edit schema compatibility, and output-focused Exports.

## Files To Review

- `ios/HoopsClips/HoopsClips/ContentView.swift`
- `ios/HoopsClips/HoopsClips/Models/WorkflowState.swift`
- `ios/HoopsClips/HoopsClips/Views/UploadsWorkflowView.swift`
- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`
- `ios/HoopsClips/HoopsClips/Views/ExportView.swift`
- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
- `ios/HoopsClipsTests/WorkflowStateTests.swift`
- `ios/HoopsClipsUITests/HoopsClipsUITests.swift`

## Integration Notes

- Review's existing `review.continueToExportButton` accessibility ID is preserved for compatibility, but it now routes to the AI Edit tab.
- Uploads keeps History and Settings as utility sheet routes, not primary workflow tabs.
- `UploadQueueProjection.items(assets:)` consumes the upload branch's asset queue fields and keeps `proxy_ready` as "ready for analysis" until clip review results arrive.
- `ExportView(viewModel:)` still defaults to embedding AI Edit for legacy callers. `ContentView` passes `showsAIEditAgentSection: false`.
- `CreateCloudEditJobRequest` carries additive `assetId` and `sourceClipIds` fields, while preserving `sourceObjectKey` and full `clips` for the current editing backend.
- AI Edit mirrors its latest cloud render status into `HighlightsViewModel.latestCloudEditRenderStatus`; Exports reads it but still only handles downloaded MP4 output.
- Boundary nudges clamp clip timing and event center; they do not create local renders.

## Verification

Run:

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:HoopsClipsTests
```

For UI smoke, build with the existing UI smoke flag:

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClipsUITests -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:HoopsClipsUITests/testWorkflowSectionsNavigateEndToEndWithSmokeFixture OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE'
```

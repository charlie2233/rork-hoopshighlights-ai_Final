# Phase Launch141: Simple AI Edit Guidance

## Goal

Tighten the internal launch build by making AI Edit easier to understand, improving the default GPT editing intent sent to the cloud, and replacing the shipped app mark with a cleaner sports-product logo.

## Changes

- Added `CloudEditUserPromptBuilder` so an empty Export side note still sends a compact, policy-safe editing intent to the backend.
- The default intent asks cloud GPT editing to keep visible outcomes, made shots, blocks, steals, defensive stops, fast breaks, and strong uncertain team clips for Review.
- Preserved explicit user notes exactly, with the existing 240-character cap.
- Added a visible AI Edit focus summary below the side-note field so users understand the default edit direction without needing to type.
- Made disabled AI Edit button copy more actionable: `Keep Clips First` or `Finish Cloud Analysis`.
- Replaced the app icon and in-app `BrandMark` assets with a simpler dark/orange/cream HC sports monogram and updated the generator script.

## Architecture Guardrails

- iOS still only sends structured export/edit intent and review context.
- GPT selection, planning, validation, rendering, storage, and final EditPlan behavior remain cloud-owned.
- No local video analysis, production rendering, composition, FFmpeg command generation, or backend simulation was added to iOS.
- The prompt builder never exposes secrets, presigned URLs, or renderer commands.

## Validation

- `swift scripts/generate_hoopclips_brand_assets.swift` succeeded and regenerated both app icon and brand mark assets in the app target catalog plus the mirrored catalog.
- `sips -g pixelWidth -g pixelHeight ...` confirmed app icons are 1024x1024 and brand marks are 512x512 in both catalogs.
- iOS Debug simulator build succeeded:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath .codex-build/derived \
  -skipPackagePluginValidation \
  COMPILER_INDEX_STORE_ENABLE=NO \
  build
```

Result: `** BUILD SUCCEEDED **`

- Focused iOS tests succeeded:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath .codex-build/derived \
  -skipPackagePluginValidation \
  COMPILER_INDEX_STORE_ENABLE=NO \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptAddsAccuracyGuidanceWhenUserLeavesNoteEmpty \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditDefaultPromptCarriesSelectedTeamFocus \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderPreservesUserInstruction \
  test
```

Result: `** TEST SUCCEEDED **`

Evidence: `.codex-build/derived/Logs/Test/Test-HoopsClips-2026.05.31_19-01-05--0700.xcresult`

## Notes

- A prior retry hit local disk pressure; generated derived-data folders from this phase were cleaned and the successful run reused `.codex-build/derived` with indexing disabled.
- The unrelated untracked root `HoopsClips.xcodeproj/` and `HoopsHighlightsAI.xcodeproj/` folders were left untouched.

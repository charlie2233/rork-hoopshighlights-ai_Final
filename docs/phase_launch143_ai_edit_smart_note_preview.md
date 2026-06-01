# Phase Launch143: AI Edit Smart Note Preview

## Goal

Make AI Edit feel simpler without reducing control. Users can type a plain note, and HoopClips now shows what style, shape, or length it understood before the user starts a cloud render.

## Changes

- Added a visible `Smart setup from note` summary below the AI Edit side-note box.
- The summary appears only when the note contains structured intent such as:
  - `NBA recap`
  - `vertical`
  - `4:30`
  - `coach review source`
- Free users who type a Pro style see the closest free style in the summary instead of a misleading Pro selection.
- Unsupported shape requests show the closest allowed shape for the intended template.
- Text uses multi-line limits and scaling so it stays readable on small iPhones and accessibility text sizes.
- Refreshed the shipped HoopClips app icon and in-app `BrandMark` with a cleaner sports-product badge:
  - bold `HC` lockup
  - flat orange basketball/speed-cut signal
  - finder-frame corners
  - less glossy/AI-rendered styling
- Regenerated both asset catalogs so the app target and root catalog stay in sync.

## Architecture Guardrails

- iOS still only maps user intent to structured cloud edit request fields.
- Cloud owns GPT clip selection, EditPlan validation, rendering, storage, and revisions.
- No local analysis, local rendering, raw FFmpeg, fake status, or full-video GPT upload was added.

## Validation

- `swift scripts/generate_hoopclips_brand_assets.swift` generated the app icon and in-app brand mark.
- Asset sync check passed:
  - `AppIcon.appiconset/icon.png` matches in both asset catalogs.
  - `BrandMark.imageset/brand_mark.png` matches in both asset catalogs.
  - Shipped app icon is `1024x1024`; in-app brand mark is `512x512`.
- `git diff --check` passed.
- Focused iOS tests passed:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserIntentParsesRecapShapeAndDuration -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserIntentParsesCoachReviewSourceAndLongDuration -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserIntentKeepsAspectRatioOutOfDuration -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote test`
  - Result bundle: `.codex-build/derived/Logs/Test/Test-HoopsClips-2026.05.31_19-21-02--0700.xcresult`
- iOS Debug `build-for-testing` passed:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO build-for-testing`

## Notes

- This phase should use `[skip ci]` when committing to avoid spending GitHub Actions budget.
- The unrelated untracked root Xcode folders remain untouched.
- No GitHub Actions were triggered for this local validation pass.

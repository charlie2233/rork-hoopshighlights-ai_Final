# Phase Launch112: Import Stability and Readability

Branch: `codex/phase-launch112-import-stability-readability`

## Goal

Reduce the real-device risk where a video finishes importing and is restored after relaunch, but the current session keeps showing the import/loading state. Also improve small-phone readability around imported filenames and the analysis quota/status banner.

## What Changed

- `VideoPlayerView` now clears import UI state as soon as `viewModel.isVideoLoaded` becomes true.
- The import completion path reuses the same helper, so late Photos import completion and normal task completion converge on one state reset.
- The view also reconciles already-loaded videos on entry and immediately after successful file/Photos load, preventing temp-file cleanup from leaving the current session on "Preparing video."
- Long imported filenames can wrap to two lines and scale before clipping.
- The analysis banner copy can wrap to three lines and scale before clipping when the free quota/Pro button is present.
- The shipped `AppIcon` and in-app `BrandMark` were refreshed in both iOS asset catalogs with an opaque sports-media monogram mark, and the app build number was bumped to `9` so device installs pick up the new icon.

## Architecture Check

This remains an iOS import/status/readability fix only. It does not add local production video analysis, edit planning, rendering, composition, GPT calls, FFmpeg command generation, or cloud cutover behavior.

## Validation

Passed:

- `git diff --check`
- `sips -g hasAlpha -g pixelWidth -g pixelHeight ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
  - App icon: 1024x1024, no alpha.
  - Brand mark: 512x512, no alpha.
- Focused iOS tests:
  - `testVideoImportPolicyUsesFileBackedVideoTypesOnly`
  - `testVideoImportPreflightAcceptsLongerFourMinuteThirtyEditSource`
  - `testVideoImportPreflightRejectsOversizedCloudUploadWithExactReason`
  - `testVideoImportPreflightRejectsInsufficientStorageWithExactReason`
  - `testCloudEditStatusCopyUsesRealCloudJobLanguageWithoutFakeThinking`
  - `testCloudAnalysisProgressStageSanitizesFakeThinkingEtaAndSensitiveText`
  - Result bundle: `/tmp/hoopclips-launch112-derived-data/Logs/Test/Test-HoopsClips-2026.05.31_14-29-25--0700.xcresult`
- iOS Debug simulator `build-for-testing`
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch112-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`

Observed existing warnings:

- `CloudAnalysisService.swift` still has existing no-async-operation `await` warnings.
- `VideoExportService.swift` still has existing iOS 18 AVAssetExportSession deprecation/sendability warnings from earlier local builds.

## Launch Status

This improves first-run and real-device import reliability, but internal TestFlight launch remains unproven until a real device smoke covers import, team scan, cloud analysis, Review, AI Edit render, preview, and share/open-in.

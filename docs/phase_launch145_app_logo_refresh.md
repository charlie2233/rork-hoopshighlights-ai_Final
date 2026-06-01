# Phase Launch145: App Logo Refresh

## Goal

Replace the older HoopClips badge with a cleaner sports-media logo that feels like a real basketball product instead of an AI demo.

## Changes

- Replaced `AppIcon.appiconset/icon.png` in both HoopClips asset catalogs with the new bold `HC` court-and-basketball mark.
- Replaced `BrandMark.imageset/brand_mark.png` in both HoopClips asset catalogs with the matching 512px mark.
- Kept the asset names and `Contents.json` files unchanged so existing SwiftUI references to `Image("BrandMark")` and the Xcode `AppIcon` setting continue to work.

## Evidence

- App icon assets are `1024x1024` PNGs.
- Brand mark assets are `512x512` PNGs.
- The actual iOS target uses `ios/HoopsClips/HoopsClips/Assets.xcassets`, and that catalog was updated.
- The root `ios/HoopsClips/Assets.xcassets` mirror was updated too, so old assets cannot accidentally be picked up by packaging or tooling.

## Validation

- `file ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
  - Result: both app icon assets are `1024 x 1024` PNGs; both brand mark assets are `512 x 512` PNGs.
- `shasum -a 256 ...`
  - Result: mirrored app icons match each other; mirrored brand marks match each other.
- `git diff --check`
- Focused iOS cloud edit request test:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve test`
  - Result: `** TEST SUCCEEDED **`
- iOS Debug build-for-testing:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`
- Reinstall the app on device after the build. iOS may keep an old launcher icon cache until the existing build is deleted or replaced.

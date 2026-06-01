# Phase Launch136: Real App Logo Refresh

## Goal

Replace the shipped HoopClips app icon and in-app brand mark with a simpler sports-product logo that reads clearly at iPhone icon size.

## Changes

- Updated `scripts/generate_hoopclips_brand_assets.swift` to generate a cleaner HC mark:
  - bold white HC monogram
  - black product-style outline/shadow
  - orange motion bands and hoop/rim accent
  - subtle court-line background
  - no tiny wordmark inside the icon
- Regenerated both tracked asset catalogs:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
  - `ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
- Bumped iOS build number from `12` to `13` for the next device/TestFlight build.

## Evidence

- Generated assets with:
  - `swift scripts/generate_hoopclips_brand_assets.swift`
- Confirmed both mirrored catalogs match:
  - app icon SHA-256: `bd9a9ad8e94c2fc73db9c3b91cb965e1c929be7a2a1d3b5aebcc0541e0a684d9`
  - brand mark SHA-256: `6b38b911336543653fd5233a8b6ace6a301c4bd45893c8ca2879a3b27ab515f0`
- Confirmed source image dimensions:
  - app icon: `1024 x 1024`
  - brand mark: `512 x 512`
- Confirmed compiled app asset catalog contains:
  - `AppIcon` / `icon.png`
  - `BrandMark` / `brand_mark.png`
- Debug simulator build succeeded through XcodeBuildMCP:
  - scheme: `HoopsClips`
  - configuration: `Debug`
  - simulator: `iPhone 17 Pro`
- Debug build-for-testing succeeded:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch136-derived-data -skipPackagePluginValidation build-for-testing`
  - Existing unrelated warning remains in `VideoExportService.swift` around `AVAssetExportSession` Sendable capture.

## Notes

- The app target uses `ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon`.
- The in-app logo view uses `Image("BrandMark")`.
- The root untracked Xcode folders were left untouched.

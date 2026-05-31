# Phase Launch97 App Logo Wiring

## Goal

Make the HoopClips app logo visibly match the current product direction in the actual iOS target.

## Change

- Regenerated the compiled iOS `AppIcon` asset with a flatter sports-product mark: black/cream/orange, bold HC monogram, basketball shape, and a clean speed slash.
- Regenerated the in-app `BrandMark` image used by the sign-in screen, opening screen, and Settings about section.
- Updated both asset catalogs kept in the repo:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/...`
  - `ios/HoopsClips/Assets.xcassets/...`
- Kept the generated asset script as the source of truth so future logo updates can be reproduced.

## Notes

- The app target uses `ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon`.
- The file-system synchronized Xcode target compiles `ios/HoopsClips/HoopsClips/Assets.xcassets`.
- The root mirror catalog is kept in sync so previews or scripts do not show the stale logo.

## Validation

```bash
swift scripts/generate_hoopclips_brand_assets.swift
sips -g pixelWidth -g pixelHeight ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png
sips -Z 180 ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png --out /tmp/hoopclips-icon-180.png
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch97-derived-data CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch97-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing
```

Result on 2026-05-31:

- Asset generation passed.
- App icon stayed 1024x1024 and brand mark stayed 512x512 in both catalogs.
- Small icon preview generated at `/tmp/hoopclips-icon-180.png`.
- `git diff --check`: passed.
- Debug simulator build passed.
- Debug simulator build-for-testing passed, including app, unit test, and UI test targets.
- Xcode compiled `ios/HoopsClips/HoopsClips/Assets.xcassets` and emitted `AppIcon60x60@2x.png`, `AppIcon76x76@2x~ipad.png`, and `Assets.car` into `HoopsClips.app`.

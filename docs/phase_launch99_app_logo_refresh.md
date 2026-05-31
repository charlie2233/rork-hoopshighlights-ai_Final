# Phase Launch99 App Logo Refresh

## Goal

Make the actual HoopClips iOS app icon and in-app brand mark visibly update in the compiled app target.

## Change

- Regenerated the real app-target `AppIcon` asset at `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`.
- Regenerated the in-app `BrandMark` image used by sign-in, launch/home branding, and Settings.
- Simplified the mark so it reads better on the iPhone Home Screen: larger `HC`, no tiny wordmark, orange ball, gold slash, and dark sports-product palette.
- Kept the root mirror assets in sync and added a root mirror `Contents.json` so the mirror app icon catalog is valid too.
- Updated `scripts/generate_hoopclips_brand_assets.swift` as the source of truth for future logo refreshes.

## Notes

- The app target still compiles `ios/HoopsClips/HoopsClips/Assets.xcassets`.
- `ASSETCATALOG_COMPILER_APPICON_NAME` remains `AppIcon`.
- No iOS video analysis, rendering, composition, export, or cloud policy behavior changed.

## Validation

```bash
swift scripts/generate_hoopclips_brand_assets.swift
sips -g pixelWidth -g pixelHeight ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png
sips -Z 180 ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png --out /tmp/hoopclips-launch99-icon-180.png
sips -Z 64 ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png --out /tmp/hoopclips-launch99-icon-64.png
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch99-derived-data CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch99-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing
```

Result on 2026-05-31:

- Asset generation passed.
- App icon stayed 1024x1024 and brand mark stayed 512x512 in both catalogs.
- Home Screen previews were generated at `/tmp/hoopclips-launch99-icon-180.png` and `/tmp/hoopclips-launch99-icon-64.png`.
- `git diff --check`: passed.
- Debug simulator build: passed.
- Debug simulator build-for-testing: passed, including app, unit test, and UI test targets.
- Compiled app bundle emitted `AppIcon60x60@2x.png`, `AppIcon76x76@2x~ipad.png`, and `Assets.car`.

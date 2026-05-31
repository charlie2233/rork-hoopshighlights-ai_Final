# Phase Launch119 Real Product Logo Wiring

Date: 2026-05-31
Branch: `codex/phase-launch119-real-product-logo-wiring`

## Goal

Replace the visible HoopClips app logo assets with a tougher, less AI-looking sports product mark and confirm the actual iOS target asset catalog is updated.

## Asset Catalog Findings

- The built iOS target is file-system synced from `ios/HoopsClips/HoopsClips`.
- The app loads `Image("BrandMark")` from `ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`.
- The app icon uses `ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon`, resolved from `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`.
- The older sibling catalog at `ios/HoopsClips/Assets.xcassets` is also tracked, so it was updated to keep repo assets consistent.

## Changes

- Replaced both AppIcon PNGs with a clean HC monogram sports mark.
- Replaced both BrandMark PNGs with the same mark for the sign-in, main shell, and Settings brand surfaces.
- Removed the split tiny `HOOP` / `CLIPS` label treatment from the prior mark.
- Kept the icon opaque with no alpha channel for iOS app icon safety.

## Evidence Commands

```bash
git status --short --branch
git pull --ff-only origin main
rg -n "ASSETCATALOG_COMPILER_APPICON_NAME|BrandMark|AppIcon" ios -S
sips -g pixelWidth -g pixelHeight -g hasAlpha ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png
```

## Validation Plan

- `git diff --check` passed.
- `xcrun actool` against the target nested catalog passed and produced:
  - `/tmp/hoopclips-launch119-actool/Assets.car`
  - `/tmp/hoopclips-launch119-actool/AppIcon60x60@2x.png`
  - `/tmp/hoopclips-launch119-actool/AppIcon76x76@2x~ipad.png`
- iOS Debug simulator `build-for-testing` reached asset compilation and app Swift compilation, then failed at link with `ld: write() failed, errno=28` because the machine had only about `366Mi` free before cleanup. This was a local disk-space failure, not a logo asset failure.

## Validation Commands Run

```bash
git diff --check
sips -g pixelWidth -g pixelHeight -g hasAlpha ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png
xcrun actool --compile /tmp/hoopclips-launch119-actool --platform iphonesimulator --minimum-deployment-target 18.0 --app-icon AppIcon --output-partial-info-plist /tmp/hoopclips-launch119-actool-info.plist --output-format human-readable-text ios/HoopsClips/HoopsClips/Assets.xcassets
```

## Notes

If an already-installed iPhone build still shows the old icon on the home screen, delete the old app from the device before reinstalling. iOS can cache SpringBoard app icons across regular reinstall-over-top cycles.

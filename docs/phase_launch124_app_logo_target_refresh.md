# Phase Launch124 App Logo Target Refresh

Date: 2026-05-31
Branch: `codex/phase-launch124-app-logo-target-refresh`

## Goal

Make the visible HoopClips app logo actually change in the compiled iOS app target.

## Findings

- The Xcode target is file-system synced from `ios/HoopsClips/HoopsClips`.
- The real app icon source is `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`.
- The in-app brand mark source is `ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`.
- The sibling catalog at `ios/HoopsClips/Assets.xcassets` is tracked as a mirror, so it was regenerated too.

## Change

- Regenerated the actual app-target AppIcon and BrandMark PNGs from `scripts/generate_hoopclips_brand_assets.swift`.
- Replaced the previous court/wordmark icon with a clearer sports-product HC mark:
  - large cream `HC`
  - orange basketball
  - gold speed slash
  - dark court-ready background
  - no tiny `HOOPCLIPS` wordmark
- Kept app icon PNGs opaque with no alpha.
- Did not touch iOS video analysis, rendering, composition, export logic, or cloud policy.

## Evidence

Generated assets:

```bash
swift scripts/generate_hoopclips_brand_assets.swift
```

Confirmed dimensions and opacity:

```bash
sips -g pixelWidth -g pixelHeight -g hasAlpha \
  ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png \
  ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png \
  ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png \
  ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png
```

Results:

- AppIcon: 1024 x 1024, `hasAlpha: no`.
- BrandMark: 512 x 512, `hasAlpha: no`.
- Same sizes confirmed in both the target catalog and mirror catalog.

Compiled asset catalog:

```bash
xcrun actool --compile /tmp/hoopclips-launch124-actool \
  --platform iphonesimulator \
  --minimum-deployment-target 18.0 \
  --app-icon AppIcon \
  --output-partial-info-plist /tmp/hoopclips-launch124-actool-info.plist \
  --output-format human-readable-text \
  ios/HoopsClips/HoopsClips/Assets.xcassets
```

Actool emitted:

- `/tmp/hoopclips-launch124-actool/AppIcon60x60@2x.png`
- `/tmp/hoopclips-launch124-actool/AppIcon76x76@2x~ipad.png`
- `/tmp/hoopclips-launch124-actool/Assets.car`

Compiled app bundle check:

```bash
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build
```

Result: `** BUILD SUCCEEDED **`

The built app bundle contains:

- `.codex-build/DerivedData/Build/Products/Debug-iphonesimulator/HoopsClips.app/AppIcon60x60@2x.png`
- `.codex-build/DerivedData/Build/Products/Debug-iphonesimulator/HoopsClips.app/AppIcon76x76@2x~ipad.png`
- `.codex-build/DerivedData/Build/Products/Debug-iphonesimulator/HoopsClips.app/Assets.car`

`Info.plist` points to `CFBundleIconName = AppIcon` and `CFBundleIconFiles = AppIcon60x60`.

## Device Note

If an already-installed iPhone still shows the previous icon, remove the old HoopClips app from the device before installing the new build. iOS can cache Home Screen icons across reinstall-over-top cycles.


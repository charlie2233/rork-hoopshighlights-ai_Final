# Phase Launch128: Logo Product Refresh

## Goal

Refresh the actual HoopClips iOS app icon and in-app brand mark so the installed app no longer shows the older HC logo. Keep the mark sports/product focused, not AI themed.

## Changes

- Updated `scripts/generate_hoopclips_brand_assets.swift` to render a flatter sports-media mark:
  - dark court badge
  - orange basketball panel
  - bold HC monogram
  - HoopClips word plate
- Regenerated both mirrored asset catalogs:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
  - `ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
- Bumped the app target build number from `10` to `11` so iOS/TestFlight has fresh bundle metadata for the icon.
- Updated the internal staging config check to expect build `11`.

## Evidence

Commands run:

```bash
git status --short --branch
git pull --ff-only origin main
swift scripts/generate_hoopclips_brand_assets.swift
sips -g pixelWidth -g pixelHeight -g hasAlpha \
  ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png \
  ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png \
  ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png \
  ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png
sips -Z 180 ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png --out /tmp/hoopclips-launch128-icon-180.png
sips -Z 64 ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png --out /tmp/hoopclips-launch128-icon-64.png
mkdir -p /tmp/hoopclips-launch128-actool
xcrun actool --compile /tmp/hoopclips-launch128-actool \
  --platform iphonesimulator \
  --minimum-deployment-target 18.0 \
  --app-icon AppIcon \
  --output-partial-info-plist /tmp/hoopclips-launch128-actool-info.plist \
  --output-format human-readable-text \
  ios/HoopsClips/HoopsClips/Assets.xcassets
ios/scripts/verify_internal_staging_config.sh
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build
```

Asset checks:

- AppIcon: `1024 x 1024`, `hasAlpha: no`.
- BrandMark: `512 x 512`, `hasAlpha: no`.
- Mirrored root iOS asset catalog matches the app-target catalog dimensions and opacity.
- `actool` emitted `AppIcon60x60@2x.png`, `AppIcon76x76@2x~ipad.png`, and `Assets.car`.
- Built simulator app reports `CFBundleVersion = 11` and `CFBundleShortVersionString = 1.0.0`.
- Debug simulator build passed. Existing Swift/iOS deprecation and Sendable warnings were observed outside the logo change.

Preview files:

- `/tmp/hoopclips-launch128-icon-180.png`
- `/tmp/hoopclips-launch128-icon-64.png`

## Notes

- No iOS rendering, analysis, or export behavior changed.
- Untracked root Xcode folders were preserved and not staged.

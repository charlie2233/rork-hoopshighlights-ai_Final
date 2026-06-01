# Phase Launch140: App Icon Target Fix

## Goal

Make the installed HoopClips iOS app logo visibly change on the next device/TestFlight build, not just inside screenshots or old cached installs.

## Changes

- Updated `scripts/generate_hoopclips_brand_assets.swift` with a more obvious sports-product mark:
  - bold `HC` monogram
  - orange clip-frame bars
  - basketball/play-cut accent
  - `CLIPS` lockup
  - no AI/sparkle styling
- Regenerated both tracked asset catalogs:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
  - `ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
- Bumped the app target build number from `13` to `14` so a fresh install/TestFlight upload has a new bundle version.

## Evidence

- Generated assets with:
  - `swift scripts/generate_hoopclips_brand_assets.swift`
- Confirmed both mirrored asset catalogs match:
  - app icon SHA-256: `846e09072c7565af1986e657293c69886bcef6edad80e3774cd6197bdcb1363f`
  - brand mark SHA-256: `e4eae88defcf4eb056af18a72c64aefc306d4fcbaf524b6a14d3c86a3d4e9f17`
- Confirmed source image dimensions and app-icon safety:
  - app icon: `1024 x 1024`, `hasAlpha: no`
  - brand mark: `512 x 512`, `hasAlpha: no`
- Confirmed Xcode asset compilation:
  - `xcrun actool --compile /tmp/hoopclips-launch140-actool --platform iphonesimulator --minimum-deployment-target 18.0 --app-icon AppIcon --output-partial-info-plist /tmp/hoopclips-launch140-actool-info.plist --output-format human-readable-text ios/HoopsClips/HoopsClips/Assets.xcassets`
  - emitted `AppIcon60x60@2x.png`, `AppIcon76x76@2x~ipad.png`, and `Assets.car`
- Confirmed built Debug app bundle:
  - `CFBundleVersion = 14`
  - `CFBundleIconName = AppIcon`
  - built app contains `AppIcon60x60@2x.png` and `AppIcon76x76@2x~ipad.png`
- Passed:
  - `git diff --check`
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/launch140-derived -skipPackagePluginValidation build`

## Launch Note

The app target is wired to `ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon`, resolved from `ios/HoopsClips/HoopsClips/Assets.xcassets`. If a device still shows the old home-screen icon after installing over an older build, delete the old app from the iPhone and reinstall build `14` or later because iOS can cache SpringBoard icons.

## Hygiene

The unrelated untracked root Xcode folders were left untouched.

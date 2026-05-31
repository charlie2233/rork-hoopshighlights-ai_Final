# Phase Launch114: Logo Assets

Branch: `codex/phase-launch114-ship-logo-assets`

## Goal

Make the shipped HoopClips iOS logo match the product direction: tougher, cleaner, sports-first, and not AI-looking.

## What Changed

- Replaced the nested iOS app catalog logo assets:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
- Replaced the sibling duplicate catalog assets too, so future Xcode/file references do not silently use the old mark:
  - `ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
- Bumped the iOS build number from `9` to `10` so the next install/TestFlight build can ship the refreshed icon.

## Brand Direction

The new mark is a bold `HC` sports monogram with cream/orange team colors, a court slash, and a subtle basketball detail. It avoids sparkles, gradients, AI motifs, and overly decorative tech styling.

## Validation

- `git diff --check`: passed.
- Logo asset sanity: passed.
  - App icon is `1024x1024`, RGB, no alpha.
  - Brand mark is `512x512`, RGB, no alpha.
- iOS Debug simulator build: passed.
  - Command used: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch114-derived-data CODE_SIGNING_ALLOWED=NO build`

## Launch Note

If a device still shows the old icon after installing a new build, delete the old app from the device first. iOS can keep home-screen icon caches across debug installs.

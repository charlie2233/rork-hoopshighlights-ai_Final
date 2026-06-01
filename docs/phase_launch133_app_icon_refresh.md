# Phase Launch133 App Icon Refresh

## Goal

Replace the old HoopClips logo assets with a cleaner product-style mark that reads better as an installed iOS app icon and in-app brand mark.

## Changes

- Replaced `AppIcon.appiconset/icon.png` with a simplified HC sports badge.
- Replaced `BrandMark.imageset/brand_mark.png` with the same product mark for auth/home/settings surfaces.
- Bumped the iOS build number to `12` so the logo change can ship in a fresh TestFlight build.
- Updated both asset catalogs:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets`
  - `ios/HoopsClips/Assets.xcassets`

The Xcode target uses the filesystem-synced `ios/HoopsClips/HoopsClips` source folder, so the inner catalog is the app-facing source of truth. The outer catalog remains aligned to avoid stale previews or tooling confusion.

## Visual Direction

- Big HC monogram, no tiny baked-in text.
- Dark court background with orange basketball/speed accents.
- Opaque PNG assets with no alpha channel for iOS/App Store compatibility.
- Less mockup-like, more like a youth basketball product badge.

## Evidence

Commands run:

```bash
git pull --ff-only origin main
sips -g pixelWidth -g pixelHeight -g hasAlpha ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png
cmp -s ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png
cmp -s ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png
```

Observed:

- App icon is `1024 x 1024`.
- Brand mark is `512 x 512`.
- All updated PNGs report `hasAlpha: no`.
- Inner and outer catalogs match byte-for-byte for both updated assets.

## Validation

- `git diff --check`
- Xcode Debug simulator build via XcodeBuildMCP:
  - Scheme: `HoopsClips`
  - Project: `ios/HoopsClips.xcodeproj`
  - Simulator: `iPhone 17 Pro`
  - Result: succeeded
- Build-for-testing:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch100-derived-data build-for-testing -quiet`
  - Result: succeeded
- Latest build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-01T00-33-47-695Z_pid49862_03ec8db4.log`

## Notes

- No iOS behavior changed.
- No local video analysis, rendering, export, or cloud policy behavior changed.

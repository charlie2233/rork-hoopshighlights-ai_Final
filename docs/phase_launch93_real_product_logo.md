# Phase Launch93 Real Product Logo

## Goal

Make the visible HoopClips brand feel like a real sports-media product instead of an AI demo.

## Change

- Replaced both tracked 1024x1024 app icon PNGs with a tougher `HC` monogram mark:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
- Added `BrandMark.imageset` to the app target asset catalog.
- Updated sign-in, post-sign-in transition, and Settings About to use the brand mark.
- Kept the design away from robot, sparkle, prompt-art, film-strip, and generic AI motifs.
- Generated opaque RGB PNGs so the app icon is safe for App Store/TestFlight validation.

## Visual Direction

- Matte black badge.
- Off-white athletic `HC` monogram.
- Orange basketball/court accent.
- Small gold speed cut for highlight energy.

## Validation

Run after changing assets:

```bash
swift scripts/generate_hoopclips_brand_assets.swift
file ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-logo-derived-data CODE_SIGNING_ALLOWED=NO build
```

Current validation:

- Asset generator passed.
- `file` confirmed app icon and brand mark PNGs are RGB.
- `git diff --check` passed.
- Debug simulator build passed. Existing AVFoundation/concurrency warnings remain in unrelated export/cloud files.

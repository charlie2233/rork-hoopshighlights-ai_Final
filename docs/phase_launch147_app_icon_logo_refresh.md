# Phase Launch147 App Icon Logo Refresh

## Goal

Replace the actual HoopClips iOS app icon and in-app brand mark with a cleaner sports-product logo that does not read like an AI tool badge.

## Changes

- Updated the real app target asset catalog at `ios/HoopsClips/HoopsClips/Assets.xcassets`.
- Mirrored the same logo into the duplicate `ios/HoopsClips/Assets.xcassets` catalog so local tools do not show stale artwork.
- Kept both app icon PNGs at `1024x1024`, RGB, no alpha.
- Kept both brand mark PNGs at `512x512`, RGB, no alpha.

## Visual Direction

- Black court base
- Orange speed bracket and ball accent
- Ivory `HC` sports monogram
- No AI wording, sparkle motifs, chatbot styling, or generic software gradient badge treatment

## Validation

- `file` and `sips` verified dimensions and no alpha channel for all changed PNGs.
- `git diff --check` passed.
- iOS Debug `build-for-testing` passed:

```sh
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath .codex-build/derived -skipPackagePluginValidation COMPILER_INDEX_STORE_ENABLE=NO build-for-testing
```

## Install Note

If a wired iPhone still shows the previous icon after reinstalling over an existing build, delete the old HoopClips app first. iOS sometimes keeps the home-screen icon cache until the app container is removed.

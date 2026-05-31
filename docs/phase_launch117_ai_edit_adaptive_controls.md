# Phase Launch117 AI Edit Adaptive Controls + Logo Refresh

## Goal

Improve TestFlight readiness by making AI Edit controls more compatible with small iPhones and larger Dynamic Type sizes while preserving the cloud-first video architecture. Also replace the shipped app logo with a tougher product-style basketball mark so the installed app, sign-in screen, transition screen, and Settings About surface all use the refreshed brand.

## Changes

- Replaced the fixed horizontal `Video Shape` picker with an adaptive grid.
- Added wrapping/scaling to shape subtitles like `9:16 social reel`, `16:9 game recap`, and `Use source framing`.
- Replaced the fixed horizontal My AI Edits action row with an adaptive grid.
- Added wrapping/scaling to Cloud Locker actions including `Preparing Share`, `Re-render`, and `Rendering`.
- Replaced both app icon catalogs with the refreshed `HOOP / HC / CLIPS` basketball mark:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
- Replaced both `BrandMark` assets so Auth, post-sign-in transition, and Settings About show the same updated logo:
  - `ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
  - `ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
- Confirmed the active Xcode target compiles from `ios/HoopsClips/HoopsClips/Assets.xcassets`; the duplicate catalog was kept in sync to avoid stale-logo confusion.

## Architecture Guardrails

- iOS still only configures cloud edits, previews, downloads, saves, and shares.
- No local analysis, edit planning, rendering, FFmpeg generation, Remotion, or Canva runtime was added.
- Cloud render status, download, re-render, and share behavior are unchanged.
- No secrets, R2 credentials, or presigned URLs are exposed.
- Logo work only changes local static assets used by the app shell and export branding.

## Validation

- `git diff --check` passed.
- Confirmed active and duplicate logo catalogs match:
  - `cmp -s ios/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png ios/HoopsClips/HoopsClips/Assets.xcassets/AppIcon.appiconset/icon.png`
  - `cmp -s ios/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png ios/HoopsClips/HoopsClips/Assets.xcassets/BrandMark.imageset/brand_mark.png`
- Confirmed asset sizes and RGB PNG format:
  - App icon: `1024 x 1024`, RGB PNG.
  - Brand mark: `512 x 512`, RGB PNG.
- Focused local iOS tests passed:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch117-derived-data CODE_SIGNING_ALLOWED=NO test ...`
  - Result bundle: `/tmp/hoopclips-launch117-derived-data/Logs/Test/Test-HoopsClips-2026.05.31_15-25-33--0700.xcresult`
  - Result: `** TEST SUCCEEDED **`
- Debug simulator build-for-testing passed:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch117-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`
  - Existing warnings remain in `VideoExportService.swift` for AVAssetExportSession iOS 18 deprecations/sendability; no new logo or AI Edit adaptive layout build errors.

## Remaining Launch Work

- Real device/TestFlight smoke still needs installed-app proof for import, cloud analysis, Review, AI Edit render, preview, revision, and share/open-in.
- Cloud deploy/version smoke should stay sparse because GitHub Actions budget is tight.

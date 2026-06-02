# Phase UX8: Share / Open In Compatibility

## Goal

Make the finished-video handoff simpler and clearer while keeping one quick system share action.

## Change

- Renamed visible finished-video share actions to `Share / Open In` in Export, AI Edit, and History.
- Updated accessibility hints/copy so users know the same button works for editors, Files, Photos, and social apps.
- Added a popover anchor to the shared `SystemShareSheet` wrapper for safer iPad-style presentations.

## Architecture

- iOS still only previews, saves, shares, and hands off finished cloud-rendered videos.
- No local iOS rendering, composition, analysis, or AI edit planning was added.

## Validation

Local commands run:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build-for-testing
```

Results:

- `git diff --check`: passed.
- iOS Debug build: passed.
- iOS build-for-testing: passed after rerunning sequentially. The first concurrent attempt failed only because Xcode's build database was locked by the Debug build.
- Only Xcode warning observed: metadata extraction skipped because no AppIntents framework dependency was found.

## Launch Recommendation

Keep the visible button simple. The system share sheet is the expected iOS way to send the reel to CapCut, iMovie, Files, Photos, Messages, TikTok, Instagram, and other installed apps.

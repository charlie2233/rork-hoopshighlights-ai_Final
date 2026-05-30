# Phase Launch46: No Fake Analysis ETA

## Goal

Remove synthetic analysis timing copy from the iOS control surface. HoopClips should show real cloud job/status progress and should not invent an estimated analysis duration.

## Change

- Removed the local duration-derived `Estimated: ~Ns analysis` card from `VideoPlayerView`.
- Removed the now-unused `estimated` localization key and translations.
- Kept the existing cloud analysis path/status surface for cloud-owned analysis.

## Architecture

This preserves the cloud-first rule. iOS does not claim backend timing or simulate queue/render estimates; it displays current status and progress values from the active analysis service.

## Validation

Commands:

```bash
rg -n "estimatedTimeView|\\.estimated|Estimated|预计|Estimado|Estimé|~[0-9]|~\\(" ios/HoopsClips/HoopsClips ios/HoopsClipsTests
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' CODE_SIGNING_ALLOWED=NO build
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests/AppLanguageStoreTests
```

Results:

- Search returned no fake ETA/localized estimate matches.
- Diff check passed.
- iOS Debug build passed on the available `iPhone 17` simulator.
- `AppLanguageStoreTests` passed: `exposesLaunchCopyForSupportedLanguages`, `defaultsToEnglish`, and `persistsSelectedLanguage`.

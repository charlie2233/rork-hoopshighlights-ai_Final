# Phase UX9 Simple Share Copy

## Goal

Make the finished-video share flow easier to scan on small iPhones and large Dynamic Type by using one short visible action label.

## Architecture Guardrails

- iOS still only previews, saves, downloads, and opens the system share sheet for a finished cloud/local export.
- No local analysis, edit planning, rendering, FFmpeg command generation, or storage credential handling was added.
- The share sheet still uses a local downloaded MP4 file, not a raw presigned URL.

## Changes

- Changed visible `Share / Open In` button text to `Share` in:
  - Export quick actions
  - AI Edit finished render actions
  - AI Edit Cloud Locker rows
  - History project detail actions
- Shortened transient share-prep copy from `Getting Video Ready` / `Preparing Share` to `Preparing`.
- Kept accessibility hints/labels describing that the system share sheet can open editors, Files, Photos, and social apps.
- Kept all existing accessibility identifiers, so UI smoke automation still targets the same buttons.

## Validation

- Passed: `git diff --check`
- Passed: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux9-dd CODE_SIGNING_ALLOWED=NO build`
  - Note: Xcode emitted the existing AppIntents metadata warning: `Metadata extraction skipped. No AppIntents.framework dependency found.`
- Passed: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux9-dd CODE_SIGNING_ALLOWED=NO build-for-testing`
  - Note: Xcode emitted the same AppIntents metadata warning for the app and UI test bundle.

## Launch Notes

- This is a readability/simplicity pass, not a launch signoff.
- Internal TestFlight readiness still needs real-device smoke: import/upload -> cloud analysis -> Review -> Export -> AI Edit render -> preview -> revision -> share/open-in.

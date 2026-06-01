# Phase Launch134 iOS 17 Compatibility And Tab Text Visibility

## Goal

Make HoopClips usable on more real iPhones while keeping the interface readable on smaller screens and large accessibility text.

## Changes

- Lowered the iOS app and test deployment target from `18.0` to `17.0`.
- Kept the iOS 18 `MeshGradient` background for newer devices, but added an iOS 17 `LinearGradient` fallback.
- Increased custom bottom tab bar label room at accessibility Dynamic Type sizes.
- Allowed bottom tab labels to wrap to two lines at accessibility sizes instead of clipping.

## Why This Helps

The previous `18.0` deployment target blocked users on iOS 17 even though most app code is compatible. This change lets the same cloud-first HoopClips client install on more phones without moving analysis, edit planning, or rendering onto-device.

The bottom tab bar is one of the most repeated navigation controls in the app. Giving labels more room at large text sizes reduces hidden or cramped words on smaller phones.

## Cloud Architecture Check

- No local video analysis added.
- No local production rendering added.
- No FFmpeg, Remotion, Canva, or edit-planning logic added to iOS.
- Cloud-first AI Edit behavior is unchanged.

## Validation

Commands:

```bash
git pull --ff-only origin main
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch100-derived-data build -quiet
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch100-derived-data build-for-testing -quiet
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch100-derived-data test-without-building -only-testing:HoopsClipsTests/AppLanguageStoreTests -only-testing:HoopsClipsTests/LaunchRuntimeConfigTests -quiet
```

Initial compatibility proof:

- The iOS 17 target build first failed on `MeshGradient`, confirming an actual iOS 18-only blocker.
- After the fallback was added, the Debug simulator build passed with deployment target `17.0`.
- Build-for-testing passed.
- Focused simulator tests passed:
  - `AppLanguageStoreTests`
  - `LaunchRuntimeConfigTests`
- Full simulator test run was attempted through XcodeBuildMCP, but the tool timed out after 120 seconds before producing pass/fail output. The lingering `xcodebuild` process was stopped and replaced with the focused local test run above.

XcodeBuildMCP build log:

```text
/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-01T00-40-40-854Z_pid49862_982f293d.log
```

## Notes

- This is not a launch-complete claim.
- Remaining full readiness still needs installed-device/TestFlight smoke and cloud render evidence.

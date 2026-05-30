# Phase Launch54 iOS Import Hang Fix

Branch: `codex/phase-launch54-ios-import-hang-fix`

## Goal

Reduce the chance that the iOS app gets stuck on "Preparing video..." immediately after a user picks a large Photos video.

## Cause

The Photos import path first tried a file transfer, then fell back to `Data.self`. For large iPhone basketball clips, that fallback can pull the entire movie into memory before the app has a local URL. That is slow, memory-heavy, and easy for the user to experience as an import hang before cloud upload even starts.

## Change

- Photos import now uses file-backed `Transferable` video representations only.
- The app no longer loads full selected videos into memory as `Data`.
- The import operation no longer runs as a `@MainActor` task. UI state updates are still isolated to the main actor, while file transfer/copy work can run off the main actor.
- The file-backed importer accepts common video content types: `video`, `movie`, `mpeg4Movie`, and `quickTimeMovie`.
- If Photos cannot provide a local video file, the app shows a direct fallback message asking the user to import from Files or choose a shorter downloaded clip.

## Architecture Notes

- This is not local analysis, rendering, composition, or export.
- The app still only obtains a local upload source URL, then cloud analysis/edit/render remains backend-owned.
- No cloud URLs, credentials, or presigned upload links are logged.

## Validation

- `Build iOS Apps` MCP `build_sim` for scheme `HoopsClips`, Debug simulator target, passed with `CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation`.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation` passed.
- `git diff --check` passed.

The build still reports pre-existing `CloudAnalysisService` warnings about `await` expressions that contain no async operations. They are not introduced by this branch and did not block the build.

## User Workaround Until New Build

If the current installed build is stuck on "Preparing video...", cancel the import or force quit Hoopclips. For large clips, save the video to Files and import from Files until the next build with this fix is installed.

# Phase UX21: File-Backed Video Import Compatibility

## Goal

Reduce real-device "Preparing video" failures during Photos/Files import, especially for large videos and provider-backed files.

## Current Import Architecture

- iOS import remains client-side import/playback handling only.
- No analysis, edit planning, rendering, or composition moved onto iOS.
- Photos import uses file-backed `Transferable` representations only.
- Supported file-backed content types are `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- There is no `Data.self` fallback path in the current Photos import code.

## Change

`VideoImportPolicy.fileSizeBytes(for:)` now falls back from `URLResourceValues.fileSize` to `FileManager.attributesOfItem(.size)`.

This helps when Photos, Files, iCloud-backed files, or other file providers expose a readable local file URL but do not populate `fileSizeKey` reliably. Missing size still fails with the existing user-facing "could not read file size" copy, but valid file-provider size metadata is accepted.

## Why This Helps

The import flow preflights size before copying/persisting. If file-provider resource values are incomplete, the app could fail import even though the video is actually available. The fallback keeps the flow file-backed and avoids loading the movie into memory.

## Validation

Passed:

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 16e' \
  -derivedDataPath /tmp/hoopclips-ux21-dd CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation -skipMacroValidation \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyUsesFileBackedVideoTypesOnly \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyNormalizesPhotosTransferFileExtensions \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyConsumesOnlyHoopClipsTemporaryPhotosTransfers \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyFallsBackToFileAttributesForSize \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportStatusCopyStaysVisibleAndRecoveryFocused
```

Result: `** TEST SUCCEEDED **`

Result bundle:

`/tmp/hoopclips-ux21-dd/Logs/Test/Test-HoopsClips-2026.06.01_22-10-35--0700.xcresult`

Also passed:

```bash
git diff --check
```

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 16e' \
  -derivedDataPath /tmp/hoopclips-ux21-dd CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation -skipMacroValidation
```

Result: `** TEST BUILD SUCCEEDED **`

## Launch Notes

- This does not replace real-device import smoke testing.
- Next real-device check should import one Photos video and one Files video, then verify the project opens without app relaunch.
- Keep commits marked `[skip ci]` unless a launch gate requires Actions.

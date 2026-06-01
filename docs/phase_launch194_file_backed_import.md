# Phase Launch194 - File-Backed Import Compatibility

## Goal

Reduce real-iPhone "Preparing video" import failures from Photos by keeping the import file-backed and making temporary Photos filenames more compatible with preflight.

## Change

- Preserved the existing file-backed-only Photos transfer path.
- Kept support for `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- Added import extension normalization:
  - valid video extensions like `mp4` and `mov` are preserved
  - missing or generic temporary extensions fall back to the transfer type
  - `.mpeg4Movie` falls back to `mp4`
  - `.video`, `.movie`, and `.quickTimeMovie` fall back to `mov`
- This avoids rejecting a valid Photos video only because the temporary imported file arrived as something like `.tmp`.

## Architecture

- iOS still only handles upload/import, preview/playback, and user control flow.
- No local video analysis, AI planning, rendering, composition, or export was added.
- Cloud remains responsible for analysis, GPT clip selection, edit planning, rendering, and storage.

## Validation

Commands:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyUsesFileBackedVideoTypesOnly -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyNormalizesPhotosTransferFileExtensions
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build-for-testing
```

Results:

- `git diff --check`: passed.
- Focused import policy tests: passed.
  - `testVideoImportPolicyUsesFileBackedVideoTypesOnly`
  - `testVideoImportPolicyNormalizesPhotosTransferFileExtensions`
- Debug `build-for-testing`: passed.

## Launch Note

This does not replace real-device import smoke. It removes one avoidable Photos temp-file compatibility failure before the TestFlight upload/import/cloud-analysis smoke.

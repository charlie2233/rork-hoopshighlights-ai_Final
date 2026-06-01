# Phase Launch206: Photos Import Reliability

## Goal

Reduce the real-iPhone "Preparing video" wait for large Photos imports by removing one avoidable local full-video copy.

## Finding

The current Photos path is already file-backed only and has no `Data.self` fallback. The remaining expensive path is:

1. Photos `Transferable` copies the selected video into a HoopClips temp file.
2. HoopClips copies that temp file again into the project library.

For large game clips, the second copy can make import feel stuck before analysis can start.

## Change

- Photos temp files created by HoopClips now move into the project library instead of being copied a second time.
- Files imports still copy normally, so external user files are not moved or deleted.
- The move path falls back to copy if move is not available.
- The safety gate only consumes temp URLs with HoopClips' `imported_video_` prefix.

## Architecture

- iOS still only imports, persists, previews, uploads, reviews, and shares.
- No local production analysis, GPT editing, FFmpeg command generation, rendering, or composition was added.
- No secrets, R2 credentials, or presigned URLs are logged.
- Import status remains real file transfer/project state; no fake thinking, ETA, or artificial delay was added.

## Validation

- Passed focused iOS import policy tests:
  - `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' -derivedDataPath /tmp/hoopclips-launch206-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyUsesFileBackedVideoTypesOnly -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyNormalizesPhotosTransferFileExtensions -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyConsumesOnlyHoopClipsTemporaryPhotosTransfers -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPreflightAcceptsLongerFourMinuteThirtyEditSource`
  - Result bundle: `/tmp/hoopclips-launch206-dd/Logs/Test/Test-HoopsClips-2026.06.01_16-04-58--0700.xcresult`
- Passed whitespace check:
  - `git diff --check`
- Passed iOS Debug simulator build:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch206-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build`

## Real-Device Smoke Needed

1. Fresh install or delete/reinstall.
2. Import the large Photos video that previously stayed on "Preparing video".
3. Confirm the project opens without closing/reopening the app.
4. Confirm History contains the project and source video.
5. Continue cloud smoke: team scan -> analysis -> Review -> AI Edit -> render -> preview -> revision -> share.

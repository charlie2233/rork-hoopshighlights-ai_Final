# Phase UX15 Import Status Clarity

## Goal

Make the real iPhone import path easier to understand while preserving the existing file-backed, off-main Photos transfer and cloud-first architecture.

## Changes

- Added `VideoImportStatusCopy` so import progress, recovery, and fallback copy is centralized and testable.
- Replaced confusing slow-import wording with copy that says HoopClips keeps checking automatically.
- Changed the recovery action from `Check History` to `Open History`, making History a clear fallback action instead of the main status.
- Kept the Photos import path file-backed only. No `Data.self` fallback, local analysis, rendering, composition, or fake progress was added.

## Safety

- iOS still only imports/copies the source video, shows status, and opens the saved project.
- Cloud still owns team scan, analysis, GPT edit planning, rendering, and storage.
- Import status text describes real copy/recovery work only.

## Validation

- Passed: `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-ux15-dd CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyUsesFileBackedVideoTypesOnly -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyNormalizesPhotosTransferFileExtensions -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportPolicyConsumesOnlyHoopClipsTemporaryPhotosTransfers -only-testing:HoopsClipsTests/HoopsClipsTests/testVideoImportStatusCopyStaysVisibleAndRecoveryFocused`
- Evidence: `/tmp/hoopclips-ux15-dd/Logs/Test/Test-HoopsClips-2026.06.01_21-06-13--0700.xcresult`
- Passed: `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-ux15-dd CODE_SIGNING_ALLOWED=NO`
- Passed: `git diff --check`.

## Launch Notes

This improves the tester-facing `Preparing video` experience, but real-device/TestFlight proof is still required for import -> team scan -> cloud analysis -> Review -> AI Edit render -> preview -> revision -> share/open-in.

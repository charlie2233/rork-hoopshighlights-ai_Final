# Phase Launch118 Preanalysis Controls Readability

## Goal

Make the first analysis setup screen simpler and more reliable on small iPhones and large Dynamic Type settings while preserving the cloud-first HoopClips architecture.

## Changes

- Kept the pre-analysis team targeting flow intact: cloud team scan first, then user chooses one team or `All teams`.
- Made the team targeting subtitle wrap more safely so scan instructions are not clipped.
- Shortened the post-scan summary when more than two teams are detected to avoid long `Team A vs Team B vs Team C` text hiding on narrow screens.
- Reworked the target highlight length header with `ViewThatFits` so the current duration badge can move under the copy when horizontal space is tight.
- Removed the three-line cap from the target highlight help copy.
- Widened target duration preset chips so values like `4:30` remain readable across phone sizes and Dynamic Type.

## Architecture Guardrails

- iOS still only collects setup choices and starts cloud analysis.
- No local video analysis, rendering, edit planning, GPT selection, or FFmpeg generation was added.
- Team filtering, uncertain clip retention, block/steal handling, and candidate generation remain backend/cloud-owned where configured.
- No secrets, storage credentials, or presigned URLs are touched.

## Validation

- `git diff --check` passed.
- Focused iOS tests passed:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch118-derived-data CODE_SIGNING_ALLOWED=NO test ...`
  - Covered highlight team selection encoding, detected-team choices, custom team names, opponent name sanitizing, and target highlight duration capping.
  - Result bundle: `/tmp/hoopclips-launch118-derived-data/Logs/Test/Test-HoopsClips-2026.05.31_15-34-58--0700.xcresult`
  - Result: `** TEST SUCCEEDED **`
- Debug simulator build-for-testing passed:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch118-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing`
  - Result: `** TEST BUILD SUCCEEDED **`
  - Existing warnings remain in `CloudAnalysisService.swift` for no-op `await` progress calls and in `VideoExportService.swift` for AVAssetExportSession iOS 18 deprecations/sendability. No new errors from the pre-analysis layout change.

## Remaining Launch Work

- Real device smoke should still verify: import, team scan, team selection, target duration selection up to `4:30`, cloud analysis, Review, AI Edit render, preview, revision, and share.
- Broader clipping accuracy still needs labeled sample review and GPT-led cloud selection evidence.

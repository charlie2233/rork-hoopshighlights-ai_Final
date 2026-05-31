# Phase Launch115: Priority Candidate Coverage

Branch: `codex/phase-launch115-priority-candidate-coverage`

## Goal

Improve highlight accuracy by making sure the cloud/GPT edit request still receives high-value defensive plays even when the iOS Review screen has not manually kept them.

## What Changed

- Expanded the cloud edit candidate reserve beyond `needsUserReview` clips.
- Unkept blocks, steals, forced turnovers, and defensive stops now stay eligible as `unreviewed` cloud edit candidates.
- Ordinary discarded clips still stay out of the cloud edit request.
- Added focused test coverage so this does not regress.

## Architecture Check

This is a cloud request candidate-selection change only. iOS still does not analyze, render, compose, export, generate FFmpeg commands, or replace backend/GPT editing. The backend remains responsible for final GPT selection, edit planning, validation, rendering, and storage.

## User Impact

- Better chance that blocks, steals, and defensive stops make it into GPT-led editing.
- Less manual work for users who miss a defensive play during Review.
- The cloud editor still receives compact clip metadata only, not full video.

## Validation

- `git diff --check`: passed.
- Focused iOS candidate tests: passed.
  - Command used: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch115-derived-data CODE_SIGNING_ALLOWED=NO test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesReviewOnlyUncertainCandidatesWithoutAutoKeepingThem -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditCandidateRankingReservesDefenseAndReviewClipsBeforeCap`
  - Result bundle: `/tmp/hoopclips-launch115-derived-data/Logs/Test/Test-HoopsClips-2026.05.31_14-55-33--0700.xcresult`
- iOS Debug simulator `build-for-testing`: passed.
  - Command used: `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch115-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing`

Existing warnings observed but not introduced here:

- `CloudAnalysisService.swift`: `await` expressions with no async work.
- `VideoExportService.swift`: iOS 18 `AVAssetExportSession` deprecation/sendability warnings.

# Phase Launch110: Visibility, Accuracy, and Usability Polish

Branch: `codex/phase-launch110-visibility-accuracy-usability`

## Goal

Make a small launch-readiness improvement that helps normal users understand the app, keeps words visible on smaller phones and larger text sizes, and preserves HoopClips' cloud-first video architecture.

## What Changed

- Settings now labels the active analysis path as `Cloud AI` when cloud analysis is enabled instead of always showing `On This iPhone`.
- The Account & Plan stat row now uses an adaptive grid so Free/Pro status and analysis path can wrap instead of clipping on narrow screens.
- Settings account names, detail lines, hub titles, subtitles, and stat cards now allow controlled wrapping and scaling.
- The Analyze button subtitle can wrap to two lines instead of hiding on smaller phones.
- Team setup fields no longer repeat the tiny trailing `optional` label because the placeholders already say optional; this gives the input more room.
- Added localized `Cloud AI` copy for English, Chinese, Spanish, and French.

## Architecture Check

This is iOS UI copy/layout only. It does not add on-device analysis, rendering, composition, FFmpeg generation, or GPT behavior. Cloud analysis, edit planning, rendering, and storage remain backend-owned.

## Validation

- Passed `git diff --check`.
- Passed iOS Debug simulator build-for-testing:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch110-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing`
- Passed focused iOS team-targeting unit tests:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch110-derived-data CODE_SIGNING_ALLOWED=NO test -only-testing:HoopsClipsTests/HoopsClipsTests/testTeamTargetChoicesRequireDetectedTeams -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudAnalysisRequestEncodesPreAnalysisTeamChoice -only-testing:HoopsClipsTests/HoopsClipsTests/testStartAnalysisRequiresConfirmedTeamChoiceAfterCloudScan -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudTeamScanPreparesJobThenStartSendsSelectedTeam`
- Existing warnings remain in `CloudAnalysisService.swift` about `await` expressions with no async operations; this phase did not touch that service.

## Launch Status

This improves clarity and phone compatibility, but it does not prove launch readiness by itself. Internal TestFlight still needs real-device smoke through import, team choice, cloud analysis, Review, AI Edit render, preview, and share/open-in.

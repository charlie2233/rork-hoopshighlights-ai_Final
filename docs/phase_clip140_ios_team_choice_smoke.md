# Phase Clip140: iOS Team Choice Smoke

## Goal

Add iOS-side smoke coverage for the pre-analysis team choice flow. Users should be able to import a video, let the cloud quick scan label jersey-color teams, choose a detected team or `All teams`, and only then start cloud analysis.

## What Changed

- Added an iOS test proving the prepared quick-scan job can be started with `teamSelection.mode = all` after detected teams are returned.
- Added an iOS view-model test proving analysis does not dispatch a cloud request while scanned teams exist and the user has not confirmed a team or `All teams`.

This stays within the cloud-first architecture. The iOS app uploads, shows scan choices, sends the selected intent, and waits for backend results. It does not perform local team analysis, rendering, composition, or FFmpeg work.

## Validation Evidence

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' -derivedDataPath /tmp/hoopclips-team-choice-derived CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudTeamScanAllTeamsChoiceStartsPreparedJobInAllTeamsMode -only-testing:HoopsClipsTests/HoopsClipsTests/testStartAnalysisRequiresConfirmedTeamChoiceAfterCloudScan` -> passed; `** TEST SUCCEEDED **`.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-team-choice-build-derived CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation` -> passed; `** TEST BUILD SUCCEEDED **`.
- `git diff --check` -> passed.

## Launch Recommendation

Keep this coverage in the no-secret iOS codecheck path before internal TestFlight. It guards the user-facing promise that selected-team highlights are explicitly chosen before analysis while still preserving `All teams` for users who want every good play.

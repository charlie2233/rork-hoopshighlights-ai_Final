# Phase Launch109: GPT Candidate Pool Accuracy

Branch: `codex/phase-launch109-gpt-candidate-pool`

## Goal

Give the cloud GPT editor a better, higher-recall candidate pool without moving analysis, rendering, or video processing into iOS. This supports the launch goal of better highlight quality while keeping HoopClips simple for users.

## What Changed

- Kept the iOS cloud edit request aligned to the backend `GPT_CANDIDATE_REVIEW_LIMIT` of 160 candidate clips.
- Reserved a larger slice of that request for uncertain review candidates: 20% of the pool, with an 8-clip minimum for normal-sized pools.
- Preserved the existing behavior that sends only clip metadata and user review decisions, never full videos.
- Updated AI Edit fallback timeline and receipt counts to show the actual cloud candidate pool count instead of only already-kept clips.
- Added a test proving the request keeps the strongest buried candidate and reserves uncertain block/steal candidates before the cap.
- Replaced both mirrored iOS app icon and in-app `BrandMark` assets with a tougher HoopClips sports-product mark.
- Changed the oversized-video import error copy from "Staging cloud analysis" to user-facing "HoopClips cloud analysis."

## Architecture Check

iOS still only sends existing candidate clip metadata to the cloud edit service. GPT selection, planning, validation, rendering, storage, and revisions remain backend-owned. No FFmpeg commands, local rendering, local composition, or full-video GPT payloads were added to iOS.

## Validation

- Passed `git diff --check`.
- Passed focused iOS candidate-pool tests:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch109-derived-data CODE_SIGNING_ALLOWED=NO test -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesReviewOnlyUncertainCandidatesWithoutAutoKeepingThem -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditCandidateRankingReservesDefenseAndReviewClipsBeforeCap`
- Passed final `git diff --check` after the asset/copy touch.
- Passed iOS Debug simulator build-for-testing:
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch109-derived-data CODE_SIGNING_ALLOWED=NO build-for-testing`

## Launch Status

This improves GPT-led edit quality and user-facing work receipts, but it does not by itself prove TestFlight launch readiness. Installed-device TestFlight smoke and staging cloud render/share verification remain required.

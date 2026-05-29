# Phase Clip114: iOS Cloud Edit Candidate Quality Gate

## Goal

Keep the iOS cloud-edit handoff aligned with the backend shot-context floor so GPT and cloud rendering receive complete basketball moments instead of tiny pre-basket or release-only shot clips. Defense, review-only uncertainty, blocks, and steals still stay eligible through the existing reserve paths.

## What Changed

- `HighlightsViewModel.rankedCloudEditCandidateClips` now filters out quality-ineligible clips before ranking and before reserve replacement.
- Shot-like clips must now meet the backend minimum context floor before iOS sends them to cloud edit:
  - minimum shot-like duration: `3.0s`
  - minimum lead-in before `eventCenter`: `1.2s`
  - minimum follow-through after `eventCenter`: `0.8s`
- The scoring boost for complete shot context now uses the same `1.2s` / `0.8s` floor.
- Regression tests cover both ranking and final `CreateEditJobRequest` encoding so high-score but badly anchored pre-basket shots do not leak into cloud edit.

This keeps the cloud-first boundary intact. iOS still only selects reviewed candidate metadata for the backend request; cloud analysis, GPT editing, EditPlan validation, rendering, and storage remain backend-owned.

## Validation

- Red check: `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17,OS=26.0.1' -only-testing:HoopsClipsTests/HoopsClipsTests` failed before the implementation on:
  - `testCloudEditCandidateRankingUsesBackendMinimumShotContext`
  - `testCloudEditRequestDoesNotSendLatePreBasketShotCandidate`
- Green check: `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17,OS=26.0.1' -only-testing:HoopsClipsTests/HoopsClipsTests` passed after the implementation.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 56 tests.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17,OS=26.0.1'` passed.
- `git diff --check` passed.

## Launch Notes

This is a quality hardening step, not final submission proof. Internal TestFlight readiness still needs real-device post-install smoke, live staging Worker/kill-switch proof, Cloudflare deploy credential proof, and a launch-grade labeled footage accuracy report proving selected-team, all-teams, blocks, steals, made/missed shots, and uncertain-review behavior.

# Phase Launch178: Team-Aware AI Accuracy

Branch: `codex/phase-launch178-team-aware-ai-accuracy`

## Goal

Improve selected-team highlight accuracy and recall before TestFlight by aligning the iOS cloud-edit request builder with the backend team-evidence contract.

## Problem

The backend already treats `quick_scan`, `gpt_frame_review`, `provider`, and `unknown` team attribution as uncertain unless it includes at least:

- 2 cited evidence frame refs
- 2 evidence role groups

iOS was still using confidence plus team/color match alone for cloud-edit candidate filtering and high-confidence auto-keep eligibility. That meant a weak high-confidence jersey-color guess could be treated as a confident selected-team match or a confident opponent, before GPT and backend validators had a chance to review it.

## Changes

- Added the same evidence gate to iOS selected-team confidence checks.
- High-confidence auto-keep now requires evidence-backed team attribution for quick-scan/GPT/provider/unknown sources.
- Weak high-confidence opponent attribution is no longer dropped as a confident opponent when `includeUncertain` is enabled.
- Strong but uncertain defensive plays such as steals and blocks can stay in the cloud-edit candidate request for user/GPT review instead of disappearing early.

## Architecture Check

- Cloud still owns analysis, GPT clip selection, edit planning, rendering, storage, and policy.
- iOS still only relays candidate metadata, team selection, status, review, preview, download, and share controls.
- No local rendering, GPT calls, analysis replacement, FFmpeg generation, or full-video transfer to GPT was added.
- This improves the candidate handoff to the existing cloud/GPT path; it does not loosen backend validators.

## Validation

Passed:

```bash
git diff --check
```

Passed:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-launch178-derived-data \
  CODE_SIGNING_ALLOWED=NO \
  build-for-testing \
  -quiet
```

Passed:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-launch178-derived-data \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/testCloudEditAutoKeepRequiresEvidenceBackedQuickScanTeamMatch \
  -only-testing:HoopsClipsTests/testCloudEditRequestKeepsWeakOpponentEvidenceReviewableWhenUncertainAllowed \
  -only-testing:HoopsClipsTests/testCloudEditRequestKeepsUncertainTeamCandidateForSelectedTeamReview \
  -quiet
```

Notes:

- An early parallel test attempt hit transient SPM resolution while the build was still resolving packages.
- One simulator test rerun used a mistyped simulator UUID and failed before launching tests; the corrected iPhone 17 Pro simulator run passed.

## Remaining Accuracy Proof

This improves runtime behavior, but it is not the final 85% accuracy proof. Internal launch still needs a real labeled-footage evaluation bundle covering:

- selected-team makes and misses
- blocks and steals
- forced turnovers and defensive stops
- uncertain review clips
- confident opponent clips
- bad-window negatives

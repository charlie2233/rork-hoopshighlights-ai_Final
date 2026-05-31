# Phase Launch126 Selected-Team Candidate Recall

Date: 2026-05-31
Branch: `codex/phase-launch126-selected-team-candidate-recall`

## Goal

Improve cloud AI Edit highlight accuracy when the user chooses a specific team before analysis.

## Problem

The cloud edit request already sent kept clips plus a reserve pool for uncertain and defensive candidates. A strong offensive clip confidently attributed to the selected team could still be left out when it was not auto-kept and did not have an uncertain-team badge. That reduced recall before GPT had a chance to judge the clip.

## Change

- `cloudEditCandidatePoolCount` now uses the active `highlightTeamSelection`.
- `createCloudEditRequest` builds the backend candidate pool with the active `highlightTeamSelection`.
- Strong selected-team clips that are not kept are now eligible for the reserve pool as `userReviewDecision = "unreviewed"` when:
  - the user selected a specific team,
  - team attribution confidently matches the selected team,
  - the clip passes existing cloud candidate quality rules,
  - combined score, confidence, and watchability meet reserve thresholds.
- Other-team clips and weak selected-team clips remain excluded.

## Architecture Boundary

This keeps the launch architecture intact:

- iOS still only packages clip metadata for the cloud request.
- No full video is sent to GPT from iOS.
- No iOS analysis, edit planning, FFmpeg, rendering, or export behavior was added.
- Backend GPT/edit planning and deterministic validators still decide final selection and rendering.

## Files Changed

- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
- `ios/HoopsClipsTests/HoopsClipsTests.swift`

## Validation

```bash
git diff --check
```

Result: passed.

```bash
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesStrongSelectedTeamReserveCandidate \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestIncludesReviewOnlyUncertainCandidatesWithoutAutoKeepingThem \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve
```

Result: passed with exit code `0`.

The run emitted the existing AVFoundation/local-export warnings from `VideoExportService.swift` and existing async warning noise from `CloudAnalysisService.swift`; no new warning class was introduced by this patch.

## Launch Notes

- This increases selected-team recall before GPT-led editing without increasing the iOS workload.
- GitHub Actions was not used to preserve the Actions budget.
- Local disk was low during validation, so the existing warmed `.codex-build/DerivedData` path was reused.
- The unrelated untracked root Xcode folders remain untouched.


# Phase Launch121: Review Team-Safe Keep Best

Date: 2026-05-31
Branch: `codex/phase-launch121-readable-edit-safety`

## Goal

Make Review simpler and safer for users who choose a target team before cloud analysis. The one-tap **Keep Best** shortcut should not silently include high-confidence clips from the other team.

## User Impact

- If the user chooses **All teams**, Keep Best behaves as before.
- If the user chooses one team, Keep Best only auto-keeps confident clips that match that team.
- Clips with no team match, low team confidence, or uncertain team evidence stay available for manual review instead of being auto-kept.
- The Review button subtitle now says `target clips` when a target team is selected, so the count matches the action.

## Architecture Boundary

- This is iOS review-control behavior only.
- No local video analysis, rendering, composition, or export was added.
- Cloud backend still owns final GPT clip selection, edit planning, validation, rendering, storage, and revisions.
- The app still sends candidate metadata to the cloud for the real edit decision.

## Files Changed

- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`
- `ios/HoopsClipsTests/HoopsClipsTests.swift`

## Validation

Commands run:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testKeepHighConfidenceDoesNotAutoKeepNeedsReviewClips \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testKeepHighConfidenceRespectsSelectedHighlightTeam \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testDiscardLowConfidencePreservesReviewAndDefensiveClips
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudAnalysisRequestEncodesPreAnalysisTeamChoice \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testHighlightTeamSelectionCodablePreservesPrimaryColorHex \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testTeamTargetChoicesRequireDetectedTeams \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testClipReviewEvidenceRowsShowConfidentTeamAndKeyMoments
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  test \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testKeepHighConfidenceRespectsSelectedHighlightTeam
```

Results:

- `git diff --check`: passed
- Keep Best/team-safety simulator tests: passed
- Keep Best/team-safety result bundle: `.codex-build/DerivedData/Logs/Test/Test-HoopsClips-2026.05.31_16-08-03--0700.xcresult`
- Team-selection/review evidence simulator tests: passed
- Team-selection/review evidence result bundle: `.codex-build/DerivedData/Logs/Test/Test-HoopsClips-2026.05.31_16-09-49--0700.xcresult`
- Re-run of edited team-safe Keep Best test: passed
- Re-run result bundle: `.codex-build/DerivedData/Logs/Test/Test-HoopsClips-2026.05.31_16-11-48--0700.xcresult`

## Budget Notes

The machine has about 1.8 GiB free on the Data volume, so this phase used targeted simulator tests instead of a broad clean build. GitHub Actions should stay skipped for this small iOS-only change.

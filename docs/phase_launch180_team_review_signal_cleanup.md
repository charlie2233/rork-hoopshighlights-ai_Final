# Phase Launch180 - Team Review Signal Cleanup

## Goal

Reduce Review screen noise while preserving selected-team accuracy and defensive highlight coverage.

## Finding

The iOS Review flow treated low-confidence team attribution as a review problem even when the user selected "All teams." That made otherwise good all-team clips show team warning badges and enter Priority/Check flows even though no team filter decision depended on that uncertainty.

## Change

- Added contextual review helpers in `HighlightsViewModel`:
  - `reviewBadges(for:teamSelection:)`
  - `needsUserReview(_:teamSelection:)`
- Team uncertainty is now surfaced as a review signal only when `HighlightTeamSelection.mode == .team`.
- Selected-team mode still keeps missing, uncertain, or low-confidence team attribution in review.
- All-team mode keeps team attribution as context instead of a warning.
- Defensive clips still stay priority review candidates, including blocks, steals, forced turnovers, and defensive stops.
- Review screen badge rendering and accessibility now use contextual review badges.
- Cloud Edit candidate reserve logic uses the same contextual user-review signal, so all-team candidate pools avoid spending review reserve slots on team-only uncertainty while still preserving defensive plays.

## Product Impact

- Less clutter in Review when users want highlights from both teams.
- Fewer confusing "Team?" warnings for parents/players who do not care which team was selected.
- Selected-team workflows remain conservative, keeping uncertain clips reviewable instead of silently dropping them.
- Blocks and steals remain protected highlight candidates.

## Architecture Notes

- No local video analysis, rendering, composition, or export was added to iOS.
- This is an iOS control-surface/readability and request-packaging change only.
- Cloud remains responsible for analysis, GPT clip selection, EditPlan, rendering, storage, and final output.

## Validation

- `git diff --check` passed.
- Focused iOS tests passed on iPhone 17 Pro simulator (`7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`):
  - `testAllTeamsModeSuppressesTeamOnlyReviewNoise`
  - `testSelectedTeamModeKeepsTeamReviewSignal`
  - `testAllTeamsStillPrioritizesDefensiveClipsWithoutTeamReviewBadge`
  - `testViewModelExposesNeedsReviewClipsForReviewFilter`
  - `testViewModelPriorityReviewClipsFocusTeamDefenseAndUncertainPlays`
- Full `HoopsClipsTests/HoopsClipsTests` unit target passed locally on the same simulator: 93 tests.
- iOS Debug `build-for-testing` passed with `CODE_SIGNING_ALLOWED=NO`.
- The first focused test attempt hit local Simulator launch server error `NSMachErrorDomain -308`; booting the same simulator and rerunning passed.

## Launch Status

This improves internal beta usability but does not complete launch readiness. Remaining blockers still include real-device post-install TestFlight smoke, cloud edit version reliability, and labeled highlight accuracy proof.

# Phase Clip70: Review Needs-Review Filter

## Goal

Make uncertain team/outcome/timing clips easy for users and internal testers to review after cloud analysis. The backend still owns team scan, attribution, clipping, and confidence decisions; iOS only surfaces the cloud-provided `needsUserReview` state in the Review screen.

## Changes

- Added `HighlightsViewModel.needsReviewClips`, derived from existing `Clip.needsUserReview`.
- Added a `Needs Review` filter to the Review screen so uncertain clips are not buried among all kept clips.
- Added a Review stat tile showing the count of clips that need user attention.
- Kept uncertain clips reviewable rather than hiding them, matching the launch rule that lower-confidence but potentially valuable team highlights should stay available for user review.
- Added a Swift Testing regression covering `needsReviewClips` with a clean made-shot clip and an uncertain steal clip.

## Architecture Notes

- No iOS local video analysis, team detection, rendering, composition, or export behavior was added.
- The filter is a control-surface change only: iOS reads cloud-derived clip metadata and lets the user inspect clips.
- Blocks and steals remain eligible because the filter uses `needsUserReview` metadata instead of action-type filtering.

## Validation

Commands run from:

`/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/hoopclips-clip45-dd -only-testing:HoopsClipsTests -quiet
```

Result: passed with exit code 0. The run included `HoopsClipsTests/testViewModelExposesNeedsReviewClipsForReviewFilter`, `testCloudAnalysisRequestEncodesPreAnalysisTeamChoice`, and `testCloudTeamScanPreparesJobThenStartSendsSelectedTeam`.

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/hoopclips-clip45-dd -quiet
```

Result: passed with exit code 0.

```bash
npm --prefix services/control-plane run typecheck
```

Result: passed with exit code 0.

```bash
npm --prefix services/control-plane test
```

Result: passed with exit code 0; 28 tests passed.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Result: passed with exit code 0; 53 tests passed.

```bash
git diff --check
```

Result: passed with exit code 0.

Attempted broader scheme test:

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/hoopclips-clip45-dd -quiet
```

Result: interrupted after 251.739 seconds due simulator UI-test runner cleanup/launch issues. Several UI tests passed or skipped before interruption, including `testExample`, `testLaunchPerformance`, `testSettingsLaunchStatusOpensForGuestSession`, and repeated launch tests. This is recorded as an environment/UI-runner blocker, not evidence against the needs-review filter.

## Remaining Launch Evidence Needed

- Real post-install TestFlight smoke on the wired iPhone.
- Real labeled-footage evaluation proving the selected-team/highlight target accuracy; this filter improves review ergonomics but does not itself prove the 85% quality target.
- GitHub Actions runner/account issue is still blocking authoritative CI evidence on the PR.

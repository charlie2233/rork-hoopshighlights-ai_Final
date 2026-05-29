# Phase Clip71: Explicit Team Choice Gate

## Goal

Make the pre-analysis team choice an explicit user action after cloud quick scan finds jersey-color teams. HoopClips should not silently keep `All teams` selected after a successful scan; the user should tap either `All teams` or a detected jersey-color team before analysis starts.

## Changes

- Added `hasConfirmedHighlightTeamSelection` and `requiresHighlightTeamSelectionConfirmation` to the iOS view model.
- Reset confirmation when cloud team scan starts and when a scan returns detected teams.
- Added `confirmHighlightTeamSelection(_:)` so tapping `All teams` or a jersey-color team explicitly confirms the target.
- Disabled/intercepted Analyze while scanned teams are available but unconfirmed.
- Updated the team target card copy/status so the user sees `Choose target team` until a choice is confirmed.
- Extended the existing team-target test to verify detected teams require explicit confirmation.

## Architecture Notes

- iOS remains the control surface only.
- No local team detection, video analysis, rendering, composition, or export logic was added.
- Cloud still owns quick scan, team attribution, selected-team analysis, uncertainty, edit planning, rendering, and storage.
- `All teams` remains available; it now requires an intentional tap after detected teams appear.

## Validation

Commands run from:

`/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/hoopclips-clip45-dd -only-testing:HoopsClipsTests -quiet
```

Result: passed with exit code 0. The run included `HoopsClipsTests/testTeamTargetChoicesRequireDetectedTeams`.

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/hoopclips-clip45-dd -quiet
```

Result: passed with exit code 0.

```bash
npm --prefix services/control-plane run deploy:staging:dry-run
```

Result: passed with exit code 0. Wrangler validated the staging Worker bundle and bindings locally.

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

## Remaining Blockers

- GitHub Actions still fails before assigning runners or recording steps for PR #32, so CI evidence remains blocked outside this patch.
- Real labeled footage is still required before claiming the 85% selected-team/highlight quality target.
- Wired-iPhone/TestFlight smoke is still required before submission.

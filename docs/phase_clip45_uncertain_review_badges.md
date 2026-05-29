# Phase Clip45: Uncertain Review Badges

## Goal

Make low-confidence team or outcome clips visibly reviewable in iOS without moving analysis, clipping, rendering, or edit planning onto the device.

## Change

- `Clip` now derives review badges from existing cloud metadata:
  - `Team?` for low-confidence team attribution.
  - `Outcome?` for uncertain shot outcome.
  - `Timing?` for shot-like clips whose timing window still needs review.
- Review cards and clip detail now show compact badges so users understand why uncertain clips are present.
- Accessibility copy includes the review flags.

## Why

The backend intentionally keeps uncertain selected-team plays in Review so the user can decide instead of losing possible blocks, steals, or ambiguous jersey-color moments. The UI now makes that state visible without pretending the model is certain.

## Architecture

- Cloud remains responsible for team attribution, shot/outcome signals, clip filtering, GPT editing, and rendering.
- iOS only displays existing metadata and lets the user keep or discard clips.
- No local video analysis, composition, or export behavior changed.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `mcp__xcodebuildmcp__.build_sim` for `ios/HoopsClips.xcodeproj`, scheme `HoopsClips`, Debug, iPhone 17 Pro simulator: passed.
- `mcp__xcodebuildmcp__.test_sim` started the full iOS suite but timed out at 120 seconds, so the result was not used as a passing signal.
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd CODE_SIGNING_ALLOWED=NO`: passed.
  - New coverage: `HoopsClipsTests/testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming`.
  - Existing cloud team flow coverage still passed: `HoopsClipsTests/testCloudTeamScanPreparesJobThenStartSendsSelectedTeam`.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`: passed, 40 tests.
- `git diff --check`: passed.

## Launch Recommendation

Keep badges enabled for internal beta. During labeled review, compare user changes on `Team?`, `Outcome?`, and `Timing?` clips against the evaluator so uncertainty retention improves recall without hiding precision mistakes.

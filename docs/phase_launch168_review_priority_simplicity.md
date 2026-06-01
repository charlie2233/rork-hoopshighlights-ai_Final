# Phase Launch168 Review Priority Simplicity

Date: 2026-06-01
Branch: `codex/phase-launch168-review-priority-simplicity`

## Goal

Move focus back from branding work to app accuracy and AI review flow. The user should not have to dig through a large candidate pool to find clips that matter for final GPT-led editing.

## Changes

- Added a shared `HighlightsViewModel.priorityReviewClips` classifier.
- Priority review now includes:
  - clips with uncertain team, timing, or outcome evidence
  - selected-team clips missing confident attribution
  - blocks
  - steals
  - forced turnovers
  - defensive stops and pressure/lockdown-style defense
- `ReviewView` now auto-focuses the first Review visit to `Priority` when priority clips exist.
- `ReviewView` uses the view-model classifier instead of duplicating team/defense rules locally.
- Review progress header now falls back to a stacked layout when horizontal text would crowd.
- Priority card copy is shorter: "Review these first."

## Architecture Guardrails

- No local iOS analysis, production rendering, composition, or export logic was added.
- iOS remains the review/control surface.
- Backend/cloud candidate generation and GPT edit planning remain the source of analysis/edit decisions.
- No secrets, R2 credentials, or presigned URLs were added or logged.
- No fake ETA/thinking/status language was added.

## Accuracy Impact

The app now treats uncertain team attribution and defensive actions as first-class Review material. This supports the GPT-led editing path because the clips most likely to need human confirmation are surfaced before Export/AI Edit, while still preserving uncertain-but-strong plays for review instead of silently dropping them.

## Validation

Commands run locally:

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:HoopsClipsTests/HoopsClipsTests/testViewModelPriorityReviewClipsFocusTeamDefenseAndUncertainPlays
```

Result: `** TEST SUCCEEDED **`

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:HoopsClipsTests/HoopsClipsTests
```

Result: `** TEST SUCCEEDED **`

```bash
git diff --check
```

Result: passed with no output.

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17'
```

Result: `** TEST BUILD SUCCEEDED **`

Evidence:

- Focused regression test: `testViewModelPriorityReviewClipsFocusTeamDefenseAndUncertainPlays`
- Broader unit suite included import policy, sign-out/reset account boundary, cloud edit prompts, team scan, candidate reserve, defensive clips, review evidence, and export timing tests.
- Xcode result bundle:
  - `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.01_00-14-55--0700.xcresult`

## Remaining Launch Blockers

- Needs real-footage selected-team/highlight accuracy labeling report.
- Needs fresh internal archive/IPA and installed TestFlight smoke on a physical iPhone.
- Live staging deploy verification should be deliberate because GitHub Actions budget is constrained.

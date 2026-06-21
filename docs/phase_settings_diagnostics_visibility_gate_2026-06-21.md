# Settings Diagnostics Visibility Gate

Date: 2026-06-21

## Goal

Reduce normal Settings clutter while keeping internal/TestFlight diagnostics available when they are actually useful.

## What changed

- The Settings smoke/proof diagnostics card no longer appears just because the build is internal.
- It now appears only when there is an active or recoverable reason:
  - import/upload is in progress
  - analysis or team scan is running
  - retry after cancel is available
  - crash/report delivery summary exists
  - saved/latest background upload proof exists
  - a pending background upload manifest exists
- This follows subagent review feedback: normal users should not see proof/debug tooling as a default Settings feature.

## Files changed

- `ios/HoopsClips/HoopsClips/Views/SettingsView.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for upload, app switching, Player proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Settings diagnostics still appears during active upload/analysis and after saved upload proof exists.
- Include current logo, upload UX, simplified diagnostics visibility, and proof changes in the next TestFlight build.

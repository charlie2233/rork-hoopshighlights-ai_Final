# Phase Launch162 Readability + Simplicity Pass

Branch: `codex/phase-launch162-readability-simplicity-pass`

## Goal

Move HoopClips closer to internal TestFlight readiness by making the Export surface easier to scan on small iPhones and with larger Dynamic Type. This pass keeps the cloud-first video boundary intact and does not add local production analysis, rendering, or composition.

## Changes

- `ios/HoopsClips/HoopsClips/Views/ExportView.swift`
  - Replaced the horizontal kept-clip chip scroller with an adaptive grid.
  - Limits the visible kept-clip labels and adds a `+N more` chip to avoid giant rows.
  - Replaced the fixed-width Save button with adaptive action buttons that wrap text.
  - Allows the export button subtitle to wrap to two lines instead of truncating.
  - Uses Dynamic Type-aware grid sizing for summary metrics, clip chips, and quick actions.

## Product Notes

- The main cloud Export path still keeps AI Edit as the render control.
- Share remains a simple system share-sheet button, without listing individual apps.
- The Summary card still shows the important kept-clip context, but it no longer forces users to horizontally scroll through every clip label.

## Validation

- `git diff --check` passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch162-derived-data build-for-testing CODE_SIGNING_ALLOWED=NO -quiet`
  - Passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch162-derived-data test -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -quiet`
  - Passed.

## Remaining Launch Gaps

- Real iPhone TestFlight smoke still needs to prove import -> team choice -> cloud analysis -> Review -> AI Edit -> render -> preview -> revision -> share/open-in.
- Labeled clip accuracy proof still needs a user or dataset-backed labeling pass.

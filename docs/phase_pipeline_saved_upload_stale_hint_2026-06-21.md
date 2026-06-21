# Pipeline Saved Upload Stale Hint

Date: 2026-06-21

## Goal

Make saved background uploads less confusing after the user leaves HoopClips for a while.

## What changed

- The existing upload banner detail now includes saved-state age when a pending upload manifest exists.
- Active background sessions can show `still uploading 2m ago`.
- Resume-needed manifests can show `tap resume 5m ago`.
- Fresh resume states can show `resume ready just now`.
- The wording remains in the existing compact detail row and does not add another section.

## Files changed

- `ios/HoopsClips/HoopsClips/ContentView.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for long upload, app switching, proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives Player upload-card proof with app-switch handoff events.
- Include all current upload UX and logo changes in the next TestFlight build.

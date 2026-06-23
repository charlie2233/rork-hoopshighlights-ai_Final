# Player Upload Proof Context

Date: 2026-06-21

## Goal

Make the Player upload-card proof useful on its own when sent through Formspree.

## What changed

- The Player upload proof now includes generated time, app version, build, environment, and cloud launch mode.
- The proof includes project ID plus redacted availability flags for analysis job and source object key.
- Full object keys, URLs, and local paths remain excluded.
- This improves debugging without adding another visible UI section.

## Files changed

- `ios/HoopsClips/HoopsClips/ContentView.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for long upload, app switching, Player proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives Player upload-card proof with app/build/project context.
- Include current logo, upload UX, smoke-proof copy, and proof context changes in the next TestFlight build.

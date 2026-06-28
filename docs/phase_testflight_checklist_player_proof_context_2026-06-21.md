# TestFlight Checklist Player Proof Context

Date: 2026-06-21

## Goal

Make the copied TestFlight checklist tell testers exactly what Player upload proof should contain.

## What changed

- The copied checklist now states that the Player upload proof button is available on the pipeline card.
- It records that Player upload proof includes app/build/environment/project/job context with sensitive IDs redacted.
- It records the Formspree manual upload-proof route as the expected send path.
- This is a copied-proof enhancement only; no new UI section was added.

## Files changed

- `ios/HoopsClips/HoopsClips/Models/TestFlightSmokeChecklistCopy.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for long upload, app switching, Player proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives Player upload-card proof with app/build/project context and app-switch handoff events.
- Include current logo, upload UX, smoke-proof copy, and proof checklist changes in the next TestFlight build.

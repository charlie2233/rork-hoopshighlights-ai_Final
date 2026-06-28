# Smoke Proof Copy Cleanup

Date: 2026-06-21

## Goal

Make launch testing feel less scary and more accurate.

## What changed

- Settings now says `Send smoke proof` instead of `Send crash proof`.
- Chinese copy now says `发送测试凭证` instead of crash-specific wording.
- Spanish/French send labels now reference smoke proof instead of crash proof.
- The TestFlight checklist now tells testers to send upload proof from the Player pipeline card.
- The checklist now calls out saved chunks, stale/resume hints, and app-switch handoff proof.

## Files changed

- `ios/HoopsClips/HoopsClips/Models/TestFlightSmokeChecklistCopy.swift`
- `ios/HoopsClips/HoopsClips/Services/AppLanguageStore.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for upload, app switching, proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives Player upload-card proof with app-switch handoff events.
- Include current logo and upload UX changes in the next TestFlight build.

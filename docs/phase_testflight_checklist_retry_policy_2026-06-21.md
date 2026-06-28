# TestFlight Checklist Retry Policy Proof

Date: 2026-06-21

## Goal

Make copied TestFlight smoke evidence reflect the richer Player upload proof without adding redundant checklist fields.

## What changed

- Long-video proof targets now include one concise multipart retry/backoff policy check.
- The duplicate boolean-style checklist field was intentionally avoided after subagent review.
- This keeps the launch tester focused on one copied packet instead of comparing Settings, Player, and Formspree manually.

## Files changed

- `ios/HoopsClips/HoopsClips/Models/TestFlightSmokeChecklistCopy.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for long upload, app switching, Player proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives Player upload-card proof with retry policy, app/build/project context, and app-switch handoff events.
- Include current logo, upload UX, smoke-proof copy, and proof checklist changes in the next TestFlight build.

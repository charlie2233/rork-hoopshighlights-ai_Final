# Settings Phone Smoke Status Strip

Date: 2026-06-21

## Goal

Make Settings launch proof easier to read without adding another stacked section.

## What changed

- The existing Smoke proof card now shows a compact status strip while collapsed.
- The strip summarizes phone smoke status: not run, passed, or issue.
- The strip summarizes upload proof status: pending, live, or ready.
- The full smoke proof text now includes `phoneSmokeResult` and `phoneSmokeIssueNote`.

## Files changed

- `ios/HoopsClips/HoopsClips/Views/SettingsView.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for upload, app switching, Player proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives Player upload-card proof with app/build/project context and app-switch handoff events.
- Include current logo, upload UX, smoke-proof copy, and Settings proof changes in the next TestFlight build.

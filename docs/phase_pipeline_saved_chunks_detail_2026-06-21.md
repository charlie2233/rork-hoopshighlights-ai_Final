# Pipeline Saved Chunks Detail

Date: 2026-06-21

## Goal

Reduce the "is this frozen?" feeling during long uploads by showing saved upload state in the existing top pipeline card.

## What changed

- The upload banner now reads the persisted pending background-upload manifest.
- If a saved upload exists, the banner detail can show compact progress such as:
  - `37% saved`
  - `4/9 chunks`
  - `still uploading`
  - `tap resume`
  - `upload done`
- This is added to the existing one-line detail row, not a new stacked section.
- The proof payload already includes the full pending manifest summary, so this UI copy stays short while proof remains diagnostic.

## Files changed

- `ios/HoopsClips/HoopsClips/ContentView.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for long upload, app switching, proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives the Player upload-card proof and includes the new app-switch handoff event.
- Include logo refresh, app-switch handoff, proof-send button, and saved-chunks detail in the next TestFlight build.

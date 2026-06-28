# Pipeline Upload Proof Send Button

Date: 2026-06-21

## Goal

Make long-upload debugging easier without sending users into Settings.

## What changed

- The top upload/analyzing pipeline card now includes a compact send-proof button beside the existing copy-proof button.
- The button uses the existing sanitized `pipelineUploadProofText`.
- The proof is sent through `LaunchTelemetry.shared.sendManualUploadProof(...)`, the same Formspree-backed route already used by Review/Settings proof tools.
- The button stays one icon wide and shows inline states: sending, sent, or failed.
- No URLs, object keys, or local file paths are included in the proof text.

## Files changed

- `ios/HoopsClips/HoopsClips/ContentView.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Run simulator smoke for the AI Analysis tap crash.
- Run real iPhone/TestFlight smoke for upload, app-switching, proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives the Player upload-card proof.
- Include the logo refresh and upload-proof button in the next TestFlight build.

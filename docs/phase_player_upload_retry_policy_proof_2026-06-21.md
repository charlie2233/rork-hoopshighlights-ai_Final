# Player Upload Retry Policy Proof

Date: 2026-06-21

## Goal

Make stuck-upload proof show whether retry/chunk behavior is configured, without adding more UI.

## What changed

- Player upload proof now includes `multipartUploadPolicy`.
- That proof includes retry-attempt count, retry backoff seconds, current lane limit, network constraint flags, and resume policy.
- This helps diagnose whether a long upload is truly stuck or waiting/retrying under the configured upload policy.
- No URLs, object keys, presigned links, or local file paths are included.

## Files changed

- `ios/HoopsClips/HoopsClips/ContentView.swift`

## Validation

Not run in this slice.

## Remaining blockers

- Simulator smoke for the AI Analysis tap crash.
- Real iPhone/TestFlight smoke for long upload, app switching, Player proof send, Review, Export, AI Edit, and share/open-in.
- Confirm Formspree receives Player upload-card proof with retry policy, app/build/project context, and app-switch handoff events.
- Include current logo, upload UX, smoke-proof copy, and proof changes in the next TestFlight build.

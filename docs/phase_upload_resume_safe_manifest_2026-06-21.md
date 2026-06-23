# Upload Resume Safe Manifest

## Goal

Make long-video upload recovery less confusing by letting the iOS service expose whether a saved upload is actually safe to resume.

## Change

- `CloudUploadResumeManifest` now stores optional `uploadExpiresAt` for both single-source and chunked uploads.
- `pendingBackgroundUploadManifestSummary()` now includes:
  - `uploadExpired=true/false`
  - `resumeSafe=true/false`
  - sanitized `expiresAt` timestamp
- Player now shows "Saved upload ready" only when `resumeSafe=true`.
- Expired or stale saved uploads tell the user that Start AI Analysis will create a fresh cloud upload instead of waiting on the old one.
- Foreground resume notices no longer say "Resuming saved upload" when the saved upload is expired.
- Resume flow clears expired manifests before inspecting sessions or upload parts, so old uploads do not sit in a fake waiting state.

## User impact

A normal user should not need to understand background sessions, chunks, or manifests. If the old upload can safely continue, HoopClips says resume. If it cannot, HoopClips gives one obvious next action.

## Tester / launch impact

`resumeSafe` and `uploadExpired` give smoke testers deterministic proof strings. They no longer have to infer state from source availability, age, active sessions, and completed chunk counts.

## Architecture note

This does not move analysis or rendering onto iOS. The app still only handles upload control, status, review, preview, and share surfaces. Backend/cloud remains responsible for analysis, edit planning, and rendering.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless explicitly requested.

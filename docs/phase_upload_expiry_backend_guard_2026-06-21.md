# Upload Expiry Backend Guard

## Goal

Make long-video resumable upload failures clear and deterministic when a saved upload has passed its cloud upload window.

## Change

- Multipart upload part and complete routes now share a backend expiry guard through `getUploadOwnedJob`.
- Expired open upload jobs return HTTP `410` with `errorCode=upload_expired`.
- Finalize returns the same `upload_expired` response when the upload object is missing and the open upload window has expired.
- The guard only applies to open upload statuses: `created` and `upload_pending`. Queued, processing, completed, failed, cancelled, succeeded, and expired jobs keep their existing idempotent/closed behavior.
- The response tells clients to start a fresh cloud analysis upload instead of retrying stale multipart calls.

## User impact

If a huge upload is too old to continue, HoopClips should not feel frozen or randomly broken. The app can now treat `upload_expired` as a clean recovery state and guide the user back to one obvious action.

## Tester / launch impact

Testers get a deterministic backend signal that matches the iOS `uploadExpired` / `resumeSafe` manifest state. This makes long-video app-switch proof easier to diagnose without exposing upload IDs, object keys, or signed URLs.

## Architecture note

This keeps cloud ownership intact. The backend remains the authority for upload validity, while iOS only displays recovery copy and starts a fresh upload when needed.

## Validation

Not run in this pass per instruction to avoid extra test/build work unless explicitly requested.

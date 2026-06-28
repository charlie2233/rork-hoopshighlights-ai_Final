# iOS Upload Expired Copy

## Goal

When the backend says a long-video upload expired, HoopClips should give one clear recovery action instead of a generic upload failure.

## Change

- `CloudAnalysisError.backend(code: "upload_expired")` now shows: `Upload expired. Tap AI Analysis again to start a fresh cloud upload.`
- HTTP `410 upload_expired` is normalized to the same code and copy before generic backend handling.
- Upload proof categorizes `upload_expired` directly so smoke reports are searchable.
- Cloud analysis treats `upload_expired` as a hard cloud failure, not a local-analysis fallback.
- In-flight resume failure handling now ends with the upload-expired message instead of saying cloud analysis is still running.
- Player has a top-priority expired-upload prompt with no proof-button detour; the existing AI Analysis button is the only action.
- Player suppresses the extra recovery card for this state so expired upload does not stack with resume/proof/recovery prompts.
- Upload proof includes `terminalUploadError=upload_expired`, `terminalUploadHTTPStatus=410`, and `terminalUploadNextAction=start_fresh_upload` when detected.

## User impact

A normal user sees one plain next action: start AI Analysis again. They do not need to understand signed URLs, multipart upload TTL, or stale background sessions.

## Tester / launch impact

Formspree and in-app proof can now show `kind=backend code=upload_expired category=upload_expired` plus the terminal upload fields, matching the backend `410 upload_expired` guard.

## Architecture note

This keeps the cloud-first boundary intact. iOS only displays recovery copy and restarts the upload; backend remains the authority for upload validity.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless explicitly requested.

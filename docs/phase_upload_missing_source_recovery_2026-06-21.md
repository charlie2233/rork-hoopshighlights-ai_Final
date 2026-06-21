# Upload Resume Recovery Copy

## Goal

Make long-video upload recovery less confusing when the user returns to HoopClips after a background upload was interrupted, cancelled, or no longer safely resumable.

## Change

- Player now only shows the "saved upload ready" resume copy when the pending upload manifest still has the original source available and is not marked stale without an active background upload session.
- If the original source file is missing, Player shows a direct recovery prompt: re-import the video and upload again.
- If the saved upload looks stale, Player explains that Start AI Analysis will create a fresh cloud upload instead of making the user wait on an old upload.
- The copy stays short and local to the analysis area so the main Player UI does not become stacked.

## Product reason

For huge videos, the scary failure mode is not only a failed upload. It is when the app looks like it can resume but the underlying background upload is no longer active. Normal users should see one clear next action instead of decoding technical state.

## Architecture note

This keeps the cloud-first boundary intact. iOS is still only the upload/review/status control surface. Analysis, selection, edit planning, and rendering stay backend-owned.

## Validation

Not run in this pass per instruction to avoid extra simulator/build/test work unless requested.

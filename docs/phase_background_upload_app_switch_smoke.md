# Phase Background Upload App-Switch Smoke

## Goal

Prove that HoopClips can upload a large video through iOS background `URLSession`, survive app switching, and reconnect with useful progress after relaunch.

This does not mark launch ready by itself. It is the focused proof needed for the background upload objective.

## Current implementation under test

- iOS uses background `URLSession` for source and chunk uploads.
- Chunked uploads persist a resume manifest with completed parts.
- Relaunch delegates record completed source or chunk uploads.
- Reopening the app resumes pending manifests and skips completed chunks.
- Player shows upload status, live progress, chunk/attempt context, recovered state, and copyable upload proof.
- Cancel cleanup clears pending background manifests so user-canceled uploads do not resurrect later.
- Failed source uploads and failed chunk attempts clear their active background session IDs so stale sessions do not keep showing as recoverable.
- Player proof includes cloud route fingerprints, server upload plan/capability summaries, recent proof trail, and manual Formspree delivery status.

## Required test video

Use a real long basketball source video large enough to trigger a meaningful upload.

Recommended:

- Troy vs El Dorado source video from Downloads, as long as it is no more than 75 minutes and 2 GB.
- Any 10+ minute local MP4 if the Troy source is unavailable.

Current client-side import limits are intentionally aligned with the staging backend defaults:

- Maximum cloud upload size: 2 GB.
- Maximum cloud analysis duration: 75 minutes.
- Import still requires enough local scratch space for the file-backed transfer.

## Simulator smoke checklist

1. Install a fresh debug build.
2. Import the large source video.
3. Start cloud analysis.
4. Confirm the Player upload card appears.
5. Confirm the upload card shows a compact upload metric row when progress is available:
   - transferred MB/GB
   - speed
   - ETA
6. Confirm the upload card shows at least one of:
   - `Safe to switch apps`
   - `Background upload`
   - `Resumable upload`
   - `Recovered upload`
7. Tap `Copy upload proof` while uploading.
8. Switch away from HoopClips for at least 30 seconds.
9. Return to HoopClips.
10. If upload is still active, confirm progress/status is not lost.
11. If the app relaunches or reconnects to a saved transfer, confirm it shows the recovered-upload proof prompt.
12. Tap `Copy upload proof` again.
13. Cancel the upload.
14. Relaunch HoopClips.
15. Confirm canceled upload does not recover as a stale pending upload.

## Real iPhone TestFlight smoke checklist

1. Install the latest TestFlight build containing the background-upload commits.
2. Import the large source video on device.
3. Start cloud analysis on Wi-Fi.
4. Copy upload proof from the Player card.
5. Switch to another app for 1-3 minutes.
6. Return to HoopClips.
7. Copy upload proof again.
8. Lock the phone for 1-3 minutes.
9. Unlock and reopen HoopClips.
10. Copy upload proof again.
11. If upload completes, confirm cloud analysis continues to Review-ready state.
12. If upload stalls, confirm status says it is paused or slow and will resume.
13. Cancel once and confirm a later relaunch does not recover the canceled upload.

## Proof fields to capture

Paste the copied proof into the launch notes or Formspree report.

Required fields:

- `source=HoopClips Player upload card`
- `proofGeneratedAt=...`
- `build=...`
- `scenePhase=...`
- `environment=...`
- `cloudLaunchMode=...`
- `cloudAnalysisBaseURLConfigured=...`
- `cloudEditBaseURLConfigured=...`
- `cloudAnalysisEndpoint=...`
- `cloudEditEndpoint=...`
- `progress=...`
- `status=...`
- `latestBackgroundUploadProof=...`
- `recentBackgroundUploadProofTrail=...`
- `latestUploadProgress=...`
- `uploadProofDeliveryStatus=...`
- `serverUploadPlan=...`
- `serverUploadCapability=...`
- `pendingBackgroundUploadManifest=...`
- `privacy=no_presigned_urls_no_object_keys_no_local_file_paths`

Helpful proof events:

- `source_session_started`
- `source_upload_failed`
- `chunked_upload_selected`
- `chunk_session_started`
- `upload_waiting_for_connectivity`
- `chunk_upload_attempt_failed`
- `chunk_upload_failed`
- `cloud_analysis_failed`
- `resume_manifest_part_completed`
- `resume_manifest_session_completed`
- `resume_manifest_relaunch_part_completed`
- `resume_manifest_relaunch_source_completed`
- `events_waiting_for_manifest_persistence`
- `manifest_persistence_finished`
- `reattached_session_empty_recheck_scheduled`
- `reattached_session_empty_rechecked`
- `relaunch_task_http_failed`
- `upload.resume.recovered`
- `background_upload_cancel_cleanup`
- `upload_proof_manual_send_queued`
- `upload_proof_manual_send_succeeded`

## Pass criteria

The smoke passes only if all are true:

- Upload status survives switching away from the app.
- Relaunch or foreground resume does not lose the pending upload.
- Completed chunks are preserved or skipped.
- Player proof can be copied during upload and, when network allows, sent through the manual proof button.
- Cancel clears pending upload state.
- No presigned URLs, object keys, or local file paths appear in copied proof.

## Fail criteria

The smoke fails if any are true:

- Upload restarts from zero after switching apps.
- Relaunch loses the upload and shows only a generic rerun state.
- Canceling upload later recovers a stale upload.
- Copied proof includes secrets, presigned URLs, object keys, or local file paths.
- The app crashes while switching away, reopening, or canceling.

## Remaining blockers before calling this goal complete

- Build has not been compiled from the latest checkout in this proof pass.
- Simulator app-switch smoke has not been run from the latest checkout.
- Real iPhone TestFlight app-switch smoke has not been run from the latest checkout.
- Backend multipart endpoints still need live environment confirmation if the backend chooses chunked upload.
- TestFlight signing/cert/profile state must be clean for latest build delivery.

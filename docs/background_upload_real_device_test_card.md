# Background Upload Real-Device Test Card

Use this card when testing a long HoopClips upload on a real iPhone/TestFlight build.

## What this test proves

```text
Switching apps while a large video is uploading does not lose progress, kill the project, or force a fresh import.
```

## Before starting

Confirm:

- The installed TestFlight build is from the current commit.
- The backend Worker/control-plane is deployed from the matching current commit.
- The phone is on Wi-Fi or stable 5G.
- Low Power Mode is off for the cleanest proof.
- The source video is large enough that upload takes time.

## Test steps

1. Open HoopClips.
2. Import a long real video.
3. Start AI analysis.
4. Wait until the top pipeline says `Uploading`.
5. Copy upload/background proof once.
6. Switch to another app for 30-60 seconds.
7. Return to HoopClips.
8. Confirm the pipeline still shows upload progress, resume, analyzing, or review-ready.
9. Copy upload/background proof again.
10. Switch away one more time while upload is still active if possible.
11. Return again.
12. Let the upload finish.
13. Confirm the app moves to `Analyzing` or `Review ready`.
14. Copy final upload/background proof.

## Proof to paste into a note

```text
appVersion:
buildVersion:
gitCommit:
deviceModel:
iOSVersion:
sourceVideoLength:
sourceVideoApproxSize:

beforeSwitch.pipelineStage:
beforeSwitch.uploadProgress:
beforeSwitch.nextAction:
beforeSwitch.uploadComplete:
beforeSwitch.activeUploadSessions:

afterSwitch.pipelineStage:
afterSwitch.uploadProgress:
afterSwitch.nextAction:
afterSwitch.uploadComplete:
afterSwitch.activeUploadSessions:
afterSwitch.staleWithoutActiveSession:
afterSwitch.completedWhileAway:
afterSwitch.wakeReceived:
afterSwitch.relaunchCompletion:
afterSwitch.inferredSourceCompletion:

final.pipelineStage:
final.uploadProgress:
final.analysisStatus:
final.nextAction:
final.uploadComplete:
final.activeUploadSessions:
final.reviewReady:

privacyNote:
```

## Check the proof locally

Save the pasted proof as a scratch text file, then run:

```bash
python3 scripts/verify_background_upload_phone_proof.py /path/to/background-upload-proof.txt
```

To create a sanitized markdown evidence packet without pasting raw proof into chat, run:

```bash
python3 scripts/build_background_upload_phone_packet.py /path/to/background-upload-proof.txt --commit <git-sha> --build <testflight-build> --out /path/to/background-upload-proof-packet.md
```

Passing proof should say:

```text
status: pass
backgroundUploadPhoneProofReady: true
privacyScanPassed: true
```

## What counts as a pass

- Upload survives at least one app switch.
- Returning to HoopClips does not lose the imported project.
- Upload either continues, resumes, completes while away, or moves into analysis.
- The app reaches `Analyzing` or `Review ready` without a fresh import.
- Proof copy is sanitized.

## What counts as a blocker

```text
staleWithoutActiveSession=true and uploadComplete=false
```

The app has an old upload handoff but no active background upload. This is the frozen-upload repair path.

```text
pipelineStage stays Uploading but uploadProgress never changes after returning
```

The app may not be reconnecting to the background session or retry state.

```text
project disappears or requires import again
```

The import/project persistence path is still not safe enough for background upload.

```text
Review opens with no clips while analysis is still active
```

Review should show a waiting state, not a rerun/dead-end state.

```text
proof contains URLs, local file paths, raw upload IDs, job IDs, object keys, or presigned fragments
```

The proof is not safe to paste into chat or a launch packet.

## Tester note

If upload feels slow, do not restart immediately. Copy proof first. Slow upload is not automatically a bug; losing the session, losing the project, or failing to continue after returning is the bug.

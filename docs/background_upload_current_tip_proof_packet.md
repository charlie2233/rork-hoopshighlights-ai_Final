# Background Upload Current-Tip Proof Packet

Date: 2026-06-20
Current code tip when this packet was created: `0dfeb0c2`

## Goal

Prove that HoopClips can keep or safely resume a large cloud upload when the user switches apps, backgrounds the app, or returns later.

This packet is intentionally evidence-focused. The goal is not just "upload works once"; the goal is:

```text
Large video upload survives app switching/backgrounding, resumes safely, and continues into cloud analysis without losing the project.
```

## Current code-side status

Code-side background upload work has already added the main pieces needed for proof:

- Background upload handoff state in the iOS cloud analysis path.
- Resumable/chunked upload support.
- Duplicate-safe multipart completion on the backend.
- Sanitized smoke evidence for resumable upload interruption/resume.
- In-app upload/background proof fields for support/debug copy.
- A runbook for real app-switch proof.

## Proof that still must be captured

### Optional local proof checker

After copying the real-device proof from the app, save it to a local scratch file and run:

```bash
python3 scripts/verify_background_upload_phone_proof.py /path/to/background-upload-proof.txt
```

For CI or handoff packets, use JSON output:

```bash
python3 scripts/verify_background_upload_phone_proof.py /path/to/background-upload-proof.txt --json
```

Expected pass shape:

```text
status: pass
backgroundUploadPhoneProofReady: true
privacyScanPassed: true
```

If the checker reports `blocked`, fix the listed evidence gap before calling background upload done.

To combine backend smoke evidence and phone proof into one sanitized end-to-end JSON bundle, run:

```bash
python3 scripts/assemble_background_upload_evidence_bundle.py --backend-evidence /path/to/backend-smoke-evidence.json --phone-proof /path/to/background-upload-proof.txt --commit <git-sha> --build <testflight-build> --out /path/to/background-upload-evidence-bundle.json
```

Expected ready shape:

```text
backgroundUploadEvidenceReady: true
privacyScanPassed: true
```

After capturing TestFlight run proof, combine it with the background-upload bundle:

```bash
python3 scripts/assemble_background_upload_launch_evidence.py --testflight-proof /path/to/testflight-run-proof.json --background-upload-bundle /path/to/background-upload-evidence-bundle.json --require-commit <git-sha> --require-build <testflight-build> --out /path/to/background-upload-launch-evidence.json
```

Expected final ready shape:

```text
backgroundUploadLaunchEvidenceReady: true
```

Safe sample fixtures exist only to rehearse the tooling contract:

```bash
python3 scripts/run_background_upload_evidence_workflow.py --commit sample-commit --build sample-build --out-dir /tmp/hoopclips-bg-upload-sample --phone-proof docs/fixtures/background_upload_phone_proof_pass_sample.txt --backend-evidence docs/fixtures/background_upload_backend_smoke_pass_sample.json
```

Do not use the sample fixture output as launch proof. Real proof must come from the current staging backend and a current TestFlight build on a real iPhone.

### 1. Staging backend proof

Capture one fresh current-tip backend proof after deploying the current Worker/control-plane changes:

```text
workerVersion:
controlPlaneCommit:
resumableSmokeEvidencePath:
startedFromFreshState:
uploadComplete:
duplicateCompleteOk:
sanitizedEvidencePrivacyCheck:
```

Expected result:

```text
resumable upload can interrupt, resume, finish, and tolerate duplicate complete without leaking private upload URLs, local paths, source object keys, upload IDs, or raw job IDs.
```

### 2. TestFlight build proof

Capture the exact iOS build that contains this current-tip code:

```text
appVersion:
buildVersion:
gitCommit:
testFlightBuildProcessedAt:
installedOnDevice:
deviceModel:
iOSVersion:
```

Expected result:

```text
The installed TestFlight build is not stale. It includes the background upload code being tested.
```

### 3. Real iPhone app-switch proof

Use a large source video, ideally the Troy/El Dorado footage or another long real clip.

Capture this sequence:

```text
1. Import video.
2. Start cloud analysis/upload.
3. Confirm the top pipeline says Uploading.
4. Switch to another app for at least 30-60 seconds.
5. Return to HoopClips.
6. Confirm upload progress resumes or continues.
7. Switch away again while upload is still active.
8. Return again.
9. Let upload complete.
10. Confirm Analyzing starts.
11. Confirm Review ready appears when analysis finishes.
```

Capture these values from the in-app proof/debug copy:

```text
pipelineStage:
uploadProgress:
analysisStatus:
pendingBackgroundUploadManifest:
backgroundUploadCompletionProof:
uploadComplete:
activeUploadSessions:
nextAction:
ageSeconds:
staleWithoutActiveSession:
completedWhileAway:
wakeReceived:
relaunchCompletion:
inferredSourceCompletion:
privacyNote:
```

Expected result:

```text
Switching apps does not kill the upload path. If iOS suspends the app, the app either receives background completion or restores enough state to resume/continue safely.
```

## Pass criteria

Mark the background upload goal done only when all of this is true:

- Current backend/staging code is deployed.
- Current iOS code is in the installed TestFlight build.
- A large upload survives at least one app switch while upload is active.
- The project remains available after returning to HoopClips.
- Upload reaches cloud analysis without requiring a fresh import.
- Review becomes ready, or the app shows a truthful waiting/retry state without crashing.
- The copied proof is sanitized and does not include secrets, presigned URLs, local file paths, R2 object keys, upload IDs, or raw job IDs.

## If proof fails

Use the proof fields to choose the next fix:

```text
wait_for_background_session:
The app thinks a background URLSession is still active. Wait, then copy proof again.

resume_upload:
The app has enough state to resume the upload. Retry/resume should be the next visible action.

start_cloud_analysis:
Upload is complete and the app should move into cloud analysis.

run_team_scan:
Upload/source is ready and the remaining step is team scan or analysis continuation.

staleWithoutActiveSession=true:
The saved upload handoff is old but there is no active background session. This is the most important repair path to inspect if the app feels frozen after switching apps.
```

## Remaining blocker summary

```text
Not done until real phone proof exists.
Code-side readiness is not the same as launch proof.
```

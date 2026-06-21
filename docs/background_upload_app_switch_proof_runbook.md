# Background Upload App-Switch Proof Runbook

This runbook proves the full HoopClips background-upload goal:

```text
Use iOS background upload so switching apps does not kill progress.
This pairs with resumable/chunked upload.
```

Do not mark this goal complete from code inspection alone. Completion needs current-tip build proof, TestFlight/real iPhone app-switch proof, and backend interrupted-upload proof.

## Current implementation signals

- iOS uses background `URLSession` for upload sessions.
- Large uploads use resumable/chunked upload when the Worker returns a resumable plan.
- Completed chunk state is persisted so resume can skip already-finished chunks.
- Player and Settings proof include upload progress, wake status, runtime policy, and sanitized proof trail.
- Settings includes a four-step background-upload timeline:
  - `iOS wake`
  - `Session reattach`
  - `Upload movement`
  - `Final callback`
- The top pipeline can show upload bytes, speed, ETA, retry/waiting context, and background-upload state.
- `scripts/resumable_upload_interrupt_smoke.py` can prove interrupted multipart upload resume behavior.

## Evidence rules

- Do not log secrets, presigned URLs, object keys, full source paths, or upload URLs.
- Use the app's proof copy buttons for sanitized phone evidence.
- Keep local code proof separate from TestFlight/phone proof.
- Keep backend interrupted-upload proof separate from iOS app-switch proof.
- The state file from `scripts/resumable_upload_interrupt_smoke.py` contains job/upload identifiers and a local source path. Do not publish it directly.

## Gate 1: current-tip iOS build proof

Required evidence:

- Branch and commit hash.
- Build command or Xcode/XcodeBuildMCP action used.
- Build result.
- Any warnings/errors that touch background upload, Settings, Player, `CloudAnalysisService`, or `ContentView`.

Expected result:

```text
iOS app builds from the exact commit intended for TestFlight.
```

## Gate 2: TestFlight upload proof

Required evidence:

- Workflow/run URL or local archive/upload proof.
- Build number.
- Commit hash included in the TestFlight build.
- App Store Connect/TestFlight upload result.

Expected result:

```text
The exact background-upload commit is available in TestFlight.
```

## Gate 3: real iPhone app-switch upload smoke

Use a video larger than the deployed `resumableUploadThresholdBytes` from `/v1/analysis/capabilities`. A full-game video is preferred.

Steps:

1. Install the current TestFlight build on a real iPhone.
2. Open HoopClips and import the large test video.
3. Start AI analysis from Player.
4. Wait for the top pipeline to show `Uploading` plus bytes/speed/ETA if available.
5. Switch to another app for at least 1 minute.
6. Optionally lock the phone briefly, then unlock.
7. Return to HoopClips.
8. Confirm the upload did not restart from zero unless the previous upload had no saved state.
9. Open Settings and inspect the background-upload timeline.
10. Copy/send upload proof from Player or Settings.

Required evidence:

- Build number and commit hash.
- Source video duration and approximate file size.
- Whether the app was backgrounded, locked, or both.
- Top pipeline status before app switch.
- Top pipeline status after returning.
- Settings timeline values:
  - `iOS wake`
  - `Session reattach`
  - `Upload movement`
  - `Final callback`
- Copied proof fields:
  - `backgroundUploadWakeReceived`
  - `backgroundUploadRuntimePolicy`
  - `pendingBackgroundUploadManifest`
  - `latestUploadProgress`
  - `latestBackgroundUploadProof`
  - `recentBackgroundUploadProofTrail`

Pass criteria:

```text
Upload continues or resumes from saved progress after app switching.
The app does not crash.
The app does not silently restart a completed chunk upload from zero.
Settings/Player proof shows upload progress and background lifecycle status.
```

Fail examples:

- App crashes during upload or when returning from background.
- Upload restarts from zero despite completed chunks in the manifest.
- Settings shows no upload movement after app switch.
- `Final callback` never completes and no retry/resume path is visible.

## Gate 4: backend interrupted-upload smoke

Use a safe test video or generated test file large enough to produce at least two multipart parts.

First interruption:

```bash
python3 scripts/resumable_upload_interrupt_smoke.py \
  --worker-url "$WORKER_BASE_URL" \
  --file /path/to/safe-test-video.mp4 \
  --state-path artifacts/resumable_upload_interrupt_state.json \
  --mode interrupt-after-first
```

Second interruption during resume:

```bash
python3 scripts/resumable_upload_interrupt_smoke.py \
  --worker-url "$WORKER_BASE_URL" \
  --state-path artifacts/resumable_upload_interrupt_state.json \
  --mode resume \
  --stop-after-new-parts 1
```

Final resume:

```bash
python3 scripts/resumable_upload_interrupt_smoke.py \
  --worker-url "$WORKER_BASE_URL" \
  --state-path artifacts/resumable_upload_interrupt_state.json \
  --mode resume
```

Required evidence:

- Sanitized JSON stdout from all three runs.
- `partCount`.
- `completedParts` after each run.
- `stateUpdated=true` during resume.
- Final `status=pass`.
- No presigned URLs, object keys, or secrets in shared output.

Pass criteria:

```text
Part 1 is uploaded and saved.
Resume uploads at least one more part and saves progress again.
Final resume skips completed parts and completes multipart upload.
Final output has status=pass and interruptionProven=true.
```

## Completion checklist

- [ ] Current-tip iOS build passes.
- [ ] Exact commit is uploaded to TestFlight.
- [ ] Real iPhone app-switch upload smoke passes.
- [ ] Player or Settings sanitized proof is captured.
- [ ] Backend interrupted-upload smoke passes.
- [ ] Remaining blocker report is updated with evidence links/IDs.

Until all boxes are checked, background upload remains not fully proven.

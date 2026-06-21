# Background Upload Real Proof Handoff

This is the final handoff for proving the background-upload goal:

```text
Use iOS background upload so switching apps does not kill progress. This pairs well with chunked upload.
```

## Rule

Do not call the background-upload goal complete from local code alone.

It is complete only when the same commit is proven across:

- deployed backend/staging resumable upload proof
- uploaded TestFlight build proof
- real iPhone app-switch upload proof
- final launch evidence packet

## Inputs needed

Collect these real files:

```text
backend-smoke-evidence.json
before-switch-proof.txt
after-switch-proof.txt
final-proof.txt
```

Also know:

```text
commit=<full git SHA that was uploaded to TestFlight>
build=<TestFlight build number installed on the phone>
fileSizeBytes=<source video file size, if known>
runId=<existing GitHub Actions TestFlight run id, if known>
```

## Step 1: backend proof

Use the staging backend resumable/chunked upload smoke proof generated from the current deployed backend.

The proof must show:

```text
startedFromFreshState=true
uploadComplete=true
duplicateCompleteOk=true
sanitizedEvidencePrivacyCheck=true
```

Do not include presigned URLs, object keys, upload IDs, job IDs, headers, or local paths.

If copied proof accidentally includes private values, create a redacted copy before sharing:

```bash
python3 scripts/redact_background_upload_phone_proof.py /path/to/raw-proof.txt --out /path/to/redacted-proof.txt --report /path/to/redaction-report.json
```

Then run the proof checker on the redacted file before using it as evidence.

For a one-step redaction plus verification prep:

```bash
python3 scripts/prepare_background_upload_phone_proof.py /path/to/raw-proof.txt --out-dir /path/to/proof
```

Use the generated `.redacted.txt` file in launch evidence commands, not the raw proof file.

## Step 2: TestFlight proof

Do not trigger a new workflow just for proof. Inspect an existing upload run.

If the run id is known:

```bash
python3 scripts/capture_testflight_run_proof.py --run-id <runId> --require-commit <commit> --require-build <build> --out /path/to/proof/testflight-run-proof.json
```

If the run id is unknown, inspect the latest existing run on `main`:

```bash
python3 scripts/capture_testflight_run_proof.py --require-commit <commit> --require-build <build> --out /path/to/proof/testflight-run-proof.json
```

Required result:

```text
testFlightRunProofReady=true
```

## Step 3: real iPhone app-switch proof

On the installed TestFlight build:

1. Import a large real video.
2. Start cloud analysis/upload.
3. When the pipeline says `Uploading`, tap `Copy upload proof`.
4. Save that as `before-switch-proof.txt`.
5. Switch to another app for 30-60 seconds.
6. Return to HoopClips.
7. Tap `Copy upload proof`.
8. Save that as `after-switch-proof.txt`.
9. Let upload continue into analysis/review.
10. Tap `Copy upload proof` again.
11. Save that as `final-proof.txt`.

Required proof signals:

```text
proofCapturedAt=<ISO timestamp>
uploadProgress=<number>
backgroundUploadCompletionProof=<sanitized summary>
pendingBackgroundUploadManifest=<sanitized summary>
backgroundUploadSurvivalHint=detected or progress/continuation proof
```

## Step 4: one-command launch proof workflow

Run this once the real backend and phone proof files exist:

```bash
python3 scripts/run_background_upload_launch_proof_workflow.py \
  --commit <commit> \
  --build <build> \
  --out-dir /path/to/proof \
  --phone-proof /path/to/proof/final-proof.txt \
  --backend-evidence /path/to/proof/backend-smoke-evidence.json \
  --before-proof /path/to/proof/before-switch-proof.txt \
  --after-proof /path/to/proof/after-switch-proof.txt \
  --final-proof /path/to/proof/final-proof.txt \
  --file-size-bytes <fileSizeBytes>
```

If you know the TestFlight GitHub Actions run id, add:

```text
--run-id <runId>
```

## Required final pass

The final file must be:

```text
/path/to/proof/background-upload-launch-evidence.json
```

And it must contain:

```text
backgroundUploadLaunchEvidenceReady=true
```

The background evidence must also show:

```text
backgroundUploadEvidenceReady=true
privacyScanPassed=true
phoneProofReady=true
appSwitchEvidence=true
continuationReady=true
backendUploadComplete=true
backendDuplicateCompleteOk=true
```

## Not acceptable as proof

These do not complete the goal:

- sample fixture output
- local script success without real phone proof
- old TestFlight build proof
- old crash breadcrumbs from a different build
- backend proof from a different commit
- proof containing URLs, local paths, object keys, upload IDs, job IDs, headers, or presigned fragments
- upload progress that never moves and never reaches analysis/review

## Current remaining blockers

```text
1. Deploy or verify current backend/staging code.
2. Upload/install current TestFlight build.
3. Run real iPhone app-switch upload proof.
4. Generate final launch evidence.
5. Confirm backgroundUploadLaunchEvidenceReady=true.
```

# Background Upload Phone Tester Checklist

Use this during the real iPhone/TestFlight background-upload proof run.

## Build identity

```text
Tester:
Date:
Device:
iOS version:
App version:
TestFlight build:
Git commit:
GitHub Actions run id:
Backend/staging version:
```

## Source video

```text
Video name:
Duration:
Approx file size:
Network used: Wi-Fi / 5G / other
Low Power Mode: off / on
```

## Test steps

- Install the TestFlight build that matches the commit above.
- Import the large source video.
- Start AI analysis.
- Wait until the top pipeline says `Uploading`.
- Tap `Copy upload proof`.
- Save as `before-switch-proof.txt`.
- Switch to another app for 30-60 seconds.
- Return to HoopClips.
- Confirm upload did not lose the project.
- Tap `Copy upload proof`.
- Save as `after-switch-proof.txt`.
- Let upload continue into analysis or Review ready.
- Tap `Copy upload proof`.
- Save as `final-proof.txt`.

## Pass/fail observations

```text
Project still present after app switch: yes / no
Upload progress moved after return: yes / no
Upload completed or continued into analysis: yes / no
Review ready reached: yes / no
Upload survived badge appeared, if applicable: yes / no / not applicable
No crash or force close: yes / no
No raw URLs/object keys/local paths in shared proof: yes / no
```

## Files to produce

```text
backend-smoke-evidence.json:
testflight-run-proof.json:
before-switch-proof.txt:
after-switch-proof.txt:
final-proof.txt:
background-upload-evidence-bundle.json:
background-upload-launch-evidence.json:
background-upload-handoff.md:
```

## Commands after files exist

Prepare any raw phone proof before sharing:

```bash
python3 scripts/prepare_background_upload_phone_proof.py /path/to/raw-proof.txt --out-dir /path/to/proof
```

Run the full proof workflow:

```bash
python3 scripts/run_background_upload_launch_proof_workflow.py \
  --commit <commit> \
  --build <testflight-build> \
  --out-dir /path/to/proof \
  --phone-proof /path/to/proof/final-proof.txt \
  --backend-evidence /path/to/proof/backend-smoke-evidence.json \
  --before-proof /path/to/proof/before-switch-proof.txt \
  --after-proof /path/to/proof/after-switch-proof.txt \
  --final-proof /path/to/proof/final-proof.txt \
  --file-size-bytes <bytes>
```

Create the shareable blocker/ready handoff:

```bash
python3 scripts/background_upload_blocker_handoff.py --proof-dir /path/to/proof --commit <commit> --build <testflight-build> --out /path/to/proof/background-upload-handoff.md
```

## Completion rule

The goal is complete only if:

```text
backgroundUploadLaunchEvidenceReady=true
```

Do not count sample fixtures, old builds, local-only checks, or proof from a different commit/build.

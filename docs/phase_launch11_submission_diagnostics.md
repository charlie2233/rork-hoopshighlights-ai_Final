# Phase Launch11: Submission Diagnostics

Date: 2026-05-23
Branch: `codex/phase-launch11-submission-diagnostics`

## Goal

Make the internal TestFlight/App Store readiness preflight capture the remaining launch blockers directly from current state:

- real connected iPhone availability for installed TestFlight smoke
- latest main-branch deploy/upload workflow status
- existing signing, artifact, staging Worker, GitHub input, blocker-doc, and upload automation checks

The script still avoids printing secret values, App Store Connect key contents, R2 credentials, or full presigned URLs.

## Changes

- Added `xcrun devicectl list devices` inspection to `scripts/submission_readiness_preflight.py`.
- Added parsing for physical device state and model without requiring a simulator.
- Added GitHub Actions main-branch status checks for:
  - `Cloud Edit Deploy Preflight`
  - `iOS Internal TestFlight Upload`
- Added unit coverage for unavailable wired iPhone detection, device parser behavior, and failed required workflow runs.

## Evidence

Commands run:

```bash
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py
PYTHONPATH=. /tmp/hoopclips-ios-backend-venv/bin/python -m unittest scripts.test_submission_readiness_preflight -v
xcrun xctrace list devices
xcrun devicectl list devices
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -showdestinations -allowProvisioningUpdates
python3 scripts/submission_readiness_preflight.py
```

Results before commit:

- Python compile passed.
- `scripts.test_submission_readiness_preflight`: 10 tests passed.
- `xcrun xctrace list devices`: `charlie的iPhone (26.4.2)` appeared under `Devices Offline`.
- `xcrun devicectl list devices`: `charlie的iPhone` was detected as `unavailable` (`iPhone 15 Pro`).
- `xcodebuild -showdestinations`: no physical iPhone destination was available; simulator destinations were available.
- Submission preflight with uncommitted changes: `17 pass`, `0 warn`, `13 fail`.
- Submission preflight after the diagnostics commit: `18 pass`, `0 warn`, `12 fail`.

## Current Launch Blockers

The new diagnostics prove the wired phone is not yet available for installed smoke testing. The remaining submission blockers after commit are:

- missing local `HOOPS_DEVELOPMENT_TEAM`
- no `.xcarchive` or `.ipa` upload artifact
- connected iPhone detected but unavailable/offline
- staging Worker `/v1/editing/version` returns HTTP 404
- missing Cloudflare/GCP deploy inputs
- latest main `Cloud Edit Deploy Preflight` run failed
- latest main `iOS Internal TestFlight Upload` run failed
- installed TestFlight smoke remains unproven
- live Worker-mediated kill-switch state remains unproven
- required iOS upload inputs are missing

## Launch Recommendation

Before submission, make the physical iPhone trusted/available in Xcode, add the required GitHub `staging` environment inputs, deploy the staging Worker, prove `/v1/editing/version`, create an archive/IPA, rerun the upload workflow, and then perform the installed TestFlight smoke path.

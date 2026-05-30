# Phase Launch53 iOS Upload Proof Path Scope

Branch: `codex/phase-launch53-ios-upload-proof-path-scope`

## Goal

Keep TestFlight upload proof accurate without forcing a new app archive when only backend code under `ios/backend/**` changes.

## Change

`scripts/submission_readiness_preflight.py` now treats these paths as iOS upload relevant:

- `.github/workflows/ios-testflight-upload.yml`
- `ios/HoopsClips/**`
- `ios/HoopsClips.xcodeproj/**`
- `ios/HoopsClipsTests/**`
- `ios/HoopsClipsUITests/**`
- `ios/exportOptions.testflight-internal*.plist`
- `ios/scripts/**`
- `ios/tools/**`

It intentionally does not treat `ios/backend/**` as app-upload relevant. That backend is cloud/runtime code and does not change the already-uploaded TestFlight binary.

## Validation

- `python3 -m unittest scripts.test_submission_readiness_preflight -v` passed: 33 tests.
- `git diff --check` passed.
- `python3 scripts/submission_readiness_preflight.py --skip-live` rechecked the upload-artifact gate and passed it using the prior successful TestFlight upload proof. The command still failed overall because this branch was intentionally dirty during the run, main checks were still in progress, the latest deploy preflight is still for `fd7313e`, launch-grade team/highlight accuracy remains missing, and installed TestFlight smoke remains unproven.

## Launch Impact

This removes a false positive in the readiness preflight. It does not prove the remaining installed TestFlight smoke or launch-grade team/highlight accuracy report.

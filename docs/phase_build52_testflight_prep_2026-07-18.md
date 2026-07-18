# Phase Build 52 TestFlight Prep

## Scope

Prepare current main after PR #85 for a new internal TestFlight upload. Build `51` remains the latest uploaded internal build, but it does not include PR #85 upload-status declutter, so current-main installed smoke must use build `52` after upload/status proof passes.

## Changes

- Bumped the HoopClips app build number from `51` to `52`.
- Updated the installed TestFlight build verifier default to require `1.0.0 (52)`.
- Updated the App Store Connect status workflow job, query, summary, and artifact names for build `52`.
- Updated readiness tests and active launch docs so the real-basketball smoke targets build `52`.

## Validation Needed

Before upload:

```bash
python3 -m unittest scripts.test_check_installed_testflight_build scripts.test_submission_readiness_preflight
git diff --check
```

After merge:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
gh workflow run ios-testflight-upload.yml --ref main -f operation=status
python3 scripts/check_installed_testflight_build.py --device E5786BB6-0095-5509-8B85-110C0B5CE6D3 --launch
```

The final command must prove the trusted iPhone has `atrak.charlie.hoopsclips` `1.0.0 (52)` installed from TestFlight before the real-basketball upload-through-export smoke starts.

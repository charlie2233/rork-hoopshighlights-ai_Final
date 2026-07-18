# Phase Build 52 TestFlight Prep

## Scope

Prepare current main after PR #85 for a new internal TestFlight upload. Build `51` remained the prior uploaded internal build, but it did not include PR #85 upload-status declutter, so current-main installed smoke must use build `52`.

## Changes

- Bumped the HoopClips app build number from `51` to `52`.
- Updated the installed TestFlight build verifier default to require `1.0.0 (52)`.
- Updated the App Store Connect status workflow job, query, summary, and artifact names for build `52`.
- Updated readiness tests and active launch docs so the real-basketball smoke targets build `52`.
- PR #87 corrected the upload workflow archive metadata guard to expect `CFBundleVersion` `52`.

## Upload And Status Proof

- PR #86 merged at `fdb482d334b0a063a508e3e52c843dfa32ecd906`.
- Initial upload run `29655548305`: signed archive passed, but archive metadata verification failed because the workflow still expected build `51`; no upload was attempted.
- PR #87 merged at `f46705959eb1d792e93d03999eb43c828de114f0`.
- Upload run `29656420482`: passed signed archive, metadata/privacy verification, App Store Connect upload, and runner-owned certificate cleanup for build `52`.
- Status run `29656700078`: App Store Connect reported build `1.0.0 (52)` as `VALID`, `IN_BETA_TESTING`, `INTERNAL_ONLY`, not expired, minimum iOS `17.0`, no non-exempt encryption, and ready for internal testing.

## Validation Needed

Before upload:

```bash
python3 -m unittest scripts.test_check_installed_testflight_build scripts.test_submission_readiness_preflight
git diff --check
```

After merge, already completed for build `52`:

```bash
gh workflow run ios-testflight-upload.yml --ref main -f operation=upload
gh workflow run ios-testflight-upload.yml --ref main -f operation=status
```

Remaining installed-device proof:

```bash
python3 scripts/check_installed_testflight_build.py --device E5786BB6-0095-5509-8B85-110C0B5CE6D3 --launch
```

The final command must prove the trusted iPhone has `atrak.charlie.hoopsclips` `1.0.0 (52)` installed from TestFlight before the real-basketball upload-through-export smoke starts. The latest local attempt was blocked by CoreDevice tunnel unavailability, not by App Store Connect or signing.

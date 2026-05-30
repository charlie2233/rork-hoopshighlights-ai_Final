# Phase Launch65 TestFlight Build 6 Upload

Date: 2026-05-30
Branch: `codex/phase-launch65-testflight-build6-upload`
Base: `origin/main` at `a8f5f6b`

## Scope

Prepare the next internal TestFlight upload after the latest cloud staging deploy. The previous manual TestFlight upload run used build `5` at commit `56f6f28`, so the current app needs a fresh bundle build number before App Store Connect can accept a new binary.

## Changes

- Bumped the iOS app, unit test, and UI test `CURRENT_PROJECT_VERSION` values from `5` to `6`.
- Updated the internal staging config verifier to expect build `6`.
- Updated the submission readiness preflight expected build number to `6`.
- Updated the internal TestFlight workflow archive metadata assertion to require `CFBundleVersion` `6`.

## Evidence

Known prior upload:

- iOS Internal TestFlight Upload run `26675828147`
- Commit `56f6f28`
- Step `Upload to internal TestFlight`: passed

Commands run before upload:

```bash
bash ios/scripts/verify_internal_staging_config.sh
plutil -lint ios/exportOptions.testflight-internal.plist
python3 -m unittest scripts.test_submission_readiness_preflight -v
```

Results:

- Internal staging config: passed with `CURRENT_PROJECT_VERSION=expected`.
- Export options plist: passed.
- Submission readiness tests: passed, 35 tests.
- Debug simulator build: passed via `xcodebuild build` on iPhone 17 simulator with existing Swift 6/deprecation warnings only.

Expected after this branch lands on `main`:

```bash
gh workflow run "iOS Internal TestFlight Upload" --ref main -f operation=upload
```

## Notes

- This branch does not change cloud rendering or GPT editing behavior.
- Latest staging cloud backend was already deployed and version-probed at `a8f5f6b` before this iOS build bump.
- Physical iPhone smoke remains blocked until the connected iPhone is available to Xcode instead of `unavailable/offline`.

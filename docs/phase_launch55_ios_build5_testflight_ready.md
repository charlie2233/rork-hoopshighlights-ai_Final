# Phase Launch55 iOS Build 5 TestFlight Ready

Branch: `codex/phase-launch55-ios-build5-testflight-ready`

## Goal

Prepare the next internal TestFlight binary after the iOS import hang fix. The connected phone already reports Hoopclips build `4`, so the fixed app needs a new bundle build number before App Store Connect can accept and testers can install it.

## Change

- Bumped the iOS app, unit test, and UI test `CURRENT_PROJECT_VERSION` values from `4` to `5`.
- Updated the internal staging config verifier to expect build `5`.
- Updated the submission readiness preflight expected build number to `5`.
- Updated the internal TestFlight workflow archive metadata assertion to require `CFBundleVersion` `5`.
- Updated preflight tests that fixture the project build setting.

## Validation

Validation run on this branch:

- `python3 -m unittest scripts.test_submission_readiness_preflight -v` passed: 33 tests.
- `bash ios/scripts/verify_internal_staging_config.sh` passed and reported `CURRENT_PROJECT_VERSION=expected`.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation` passed.
- `git diff --check` passed.

## Launch Impact

This does not by itself upload build `5`. It makes the repository and CI assertions ready for an internal TestFlight build `5` upload, which is required before deleting/replacing the current app on the real iPhone with the import-hang fix.

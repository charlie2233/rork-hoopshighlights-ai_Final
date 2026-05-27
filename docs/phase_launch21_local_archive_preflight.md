# Phase Launch21 Local Archive Preflight

## Goal

Reduce the local TestFlight readiness blockers after the selected-team scan fail-safe work by proving local signing and a signed internal-staging archive without uploading to App Store Connect.

## Local State

- `LocalSecrets.xcconfig` was materialized locally and remains gitignored.
- `HOOPS_DEVELOPMENT_TEAM` now resolves for local signing without committing the local config.
- A signed Release archive was built at `ios/build/HoopsClips-InternalStaging-fa99f8f.xcarchive`; `ios/build/` is ignored.
- No upload, TestFlight submission, App Store Connect export, or installed-device smoke was attempted.

## Commands

- `xcodebuild archive -quiet -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Release -destination 'generic/platform=iOS' -archivePath ios/build/HoopsClips-InternalStaging-fa99f8f.xcarchive -derivedDataPath /tmp/hoopclips-clip59-archive-dd -xcconfig ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig -allowProvisioningUpdates -authenticationKeyPath /Users/hanfei/Downloads/AuthKey_RX3Z6PJX7Q.p8 -authenticationKeyID RX3Z6PJX7Q -authenticationKeyIssuerID 62a3841f-c90c-4c6e-b6fd-48f9726f2ad2 -hideShellScriptEnvironment` -> succeeded.
- `python3 scripts/submission_readiness_preflight.py` -> 22 pass, 0 warn, 10 fail.

## Remaining Submission Blockers

- Physical iPhone is detected but unavailable; CoreDevice reports `tunnelState: unavailable`.
- Staging Worker `GET /v1/editing/version` still returns 404, so iOS kill-switch state is not proven through the Worker.
- Direct editing service `/version` is stale and missing GPT/live-render feature flags.
- GitHub Actions for Cloud Edit Deploy Preflight and iOS Internal TestFlight Upload fail before runner startup because the GitHub account billing/spending limit gate blocks jobs.
- GCP Secret Manager currently has editing/R2 secret names, but `HOOPS_OPENAI_API_KEY` is not present, so the GPT-enabled editing deploy cannot be safely run from local GCP state yet.
- Installed TestFlight smoke remains unproven.

## Notes

The local archive only proves that signing/archive is possible from this machine. It is not a substitute for the explicit GitHub `workflow_dispatch` archive/upload run, App Store Connect processing, or the installed TestFlight smoke path.

# Phase Launch59 - Device Smoke Proof

## Goal

Refresh internal launch evidence now that the wired iPhone is available, without spending unnecessary GitHub Actions minutes.

## Branch

`codex/phase-launch59-device-smoke-proof`

## Device State

Command:

```bash
xcrun devicectl list devices
```

Result:

- `charlie` iPhone is `available (paired)`.
- Model: iPhone 15 Pro.

## Physical Device Build, Install, And Launch

The first physical-device build attempt used the Xcode device UUID from `devicectl`, but Xcode expects its own destination identifier for this phone. After switching to the Xcode destination ID and passing the configured development team as an xcodebuild build setting, the Debug device build succeeded.

Build command shape:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=00008130-000A001A1178001C' \
  -derivedDataPath /tmp/hoopclips-phase59-device-build \
  -allowProvisioningUpdates \
  -skipPackagePluginValidation \
  HOOPS_DEVELOPMENT_TEAM=<configured-team-id> \
  build
```

Result:

- `** BUILD SUCCEEDED **`
- Bundle ID: `atrak.charlie.hoopsclips`
- Version: `1.0.0`
- Build: `5`
- Known existing warnings remain in `CloudAnalysisService.swift` for `await` expressions with no async work.

Install command:

```bash
xcrun devicectl device install app \
  --device E5786BB6-0095-5509-8B85-110C0B5CE6D3 \
  /tmp/hoopclips-phase59-device-build/Build/Products/Debug-iphoneos/HoopsClips.app
```

Result:

- App installed successfully.
- Installed bundle ID: `atrak.charlie.hoopsclips`

Launch command:

```bash
xcrun devicectl device process launch \
  --device E5786BB6-0095-5509-8B85-110C0B5CE6D3 \
  atrak.charlie.hoopsclips
```

Result:

- `Launched application with atrak.charlie.hoopsclips bundle identifier.`
- Device process list showed the app running from the installed `HoopsClips.app` bundle.
- Device app list showed `Hoopclips`, bundle `atrak.charlie.hoopsclips`, version `1.0.0`, build `5`.

## Internal Staging Archive

Created a local internal-staging iOS archive without dispatching another GitHub Actions run:

```bash
xcodebuild archive \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath ios/build/HoopsClips-Phase59-InternalStaging.xcarchive \
  -derivedDataPath /tmp/hoopclips-phase59-archive-derived \
  -allowProvisioningUpdates \
  -skipPackagePluginValidation \
  -xcconfig ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig \
  HOOPS_DEVELOPMENT_TEAM=<configured-team-id>
```

Result:

- `** ARCHIVE SUCCEEDED **`
- Archive path: `ios/build/HoopsClips-Phase59-InternalStaging.xcarchive`
- Bundle ID: `atrak.charlie.hoopsclips`
- Version: `1.0.0`
- Build: `5`
- `HOOPSAppEnvironment`: `internal_staging`
- `HOOPSCloudLaunchMode`: `internal_only`

This archive is a local signed internal-staging artifact, not a TestFlight-uploaded IPA.

## UI Smoke

Attempted the targeted physical-device UI smoke for the pre-analysis team picker:

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=00008130-000A001A1178001C' \
  -derivedDataPath /tmp/hoopclips-phase59-device-uitest \
  -allowProvisioningUpdates \
  -skipPackagePluginValidation \
  HOOPS_DEVELOPMENT_TEAM=<configured-team-id> \
  OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' \
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testPreanalysisTeamChoiceSmoke
```

Result:

- Blocked before running the test because Xcode could not find a development provisioning profile for `atrak.charlie.hoopsclips.uitests.xctrunner`.
- This is a local UITest-runner signing/profile blocker, not an app build/install blocker.
- Result bundle: `/tmp/hoopclips-phase59-device-uitest/Logs/Test/Test-HoopsClips-2026.05.30_00-05-02--0700.xcresult`

Simulator fallback using Build iOS Apps MCP:

```text
test_sim
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testPreanalysisTeamChoiceSmoke
  OTHER_SWIFT_FLAGS=$(inherited) -D HOOPS_ENABLE_UI_SMOKE
```

Result:

- The targeted `testPreanalysisTeamChoiceSmoke()` test case passed.
- XcodeBuildMCP still reported the overall test command as failed because Xcode emitted a simulator install-session assertion after the test run completed.
- MCP artifacts:
  - build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-05-30T07-05-13-825Z_pid52479_5cdc99a1.log`
  - result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-30T07-05-13-825Z_pid52479_e331f0b2.xcresult`

## Preflight Update

`scripts/submission_readiness_preflight.py` now treats stale deploy/check evidence as acceptable only when the commits after the proven SHA did not touch files relevant to that evidence.

This means:

- Docs-only `[skip ci]` evidence commits do not force a new GitHub Actions run.
- iOS workflow evidence still fails stale if iOS/upload-relevant files changed.
- Cloud deploy evidence still fails stale if Worker/editing/inference deploy-relevant files changed.
- Direct editing `/version` git SHA evidence still fails stale if editing-service deploy-relevant files changed.

This keeps launch gates strict while respecting the current GitHub Actions budget.

## Validation

Commands:

```bash
python3 -m unittest scripts.test_submission_readiness_preflight -v
python3 scripts/submission_readiness_preflight.py --archive-path ios/build/HoopsClips-Phase59-InternalStaging.xcarchive
```

Results:

- Submission preflight unit tests passed: 35 tests.
- Live submission readiness preflight with the local archive supplied: `31 pass`, `0 warn`, `3 fail`.
- The preflight now passes the docs-only stale checks for:
  - direct editing git SHA
  - main-branch `Cloud Edit Deploy Preflight`
  - main-branch `iOS Internal TestFlight Upload`
- The preflight now finds one local upload artifact candidate from the internal-staging archive.

Remaining preflight blockers:

- Missing launch-grade labeled footage report proving the selected-team/highlight quality target.
- Secret-gated manual deploy preflight is stale relative to current main.
- Installed TestFlight post-install smoke remains unproven.

## Launch Notes

- No secrets, API keys, R2 credentials, private keys, or full presigned URLs are included in this evidence.
- Physical iPhone local build/install/launch is now proven for current source.
- Full internal TestFlight smoke still needs the actual TestFlight-installed app flow: import/upload, team choice or all teams, cloud analysis, Review, Export, AI Edit render, preview, More Hype revision, revised preview, and share/open-in.

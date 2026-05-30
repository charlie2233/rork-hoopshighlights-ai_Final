# Phase Launch60 - File-Backed Photos Import

## Goal

Reduce the chance that large Photos imports hang on `Preparing video...` by keeping the Photos transfer path file-backed and moving the `PhotosPickerItem.loadTransferable` work off the main actor.

## Branch

`codex/phase-launch60-file-backed-photos-import`

## Issue

The reported device symptom was a long or stuck `Preparing video...` state after importing a real iPhone video. The current source already had the most dangerous fallback removed: there is no `Data.self` or `DataRepresentation` Photos path in `VideoPlayerView.swift`. The remaining launch-risk was that Photos transfer work could still inherit UI actor context from the SwiftUI view task.

## Changes

- Added `VideoImportPolicy` with the shared allowed import types:
  - `.video`
  - `.movie`
  - `.mpeg4Movie`
  - `.quickTimeMovie`
- Updated the Files picker to use the same supported content type policy as the Photos transfer path.
- Added `VideoImportTransfer.loadFileBackedVideo(from:)`, which runs `PhotosPickerItem.loadTransferable(type: ImportedVideoFile.self)` inside a user-initiated detached task.
- Kept UI state updates and error presentation on the main actor.
- Kept import file-backed only. No full-video `Data` loading path was added.

## Architecture Notes

- This does not add local video analysis, rendering, composition, or export.
- iOS still only imports the source file and hands cloud upload/analysis/editing to the backend flow.
- The Photos transfer copies a file-backed representation to a temporary local file, then the existing project library import persists it into app storage.

## Validation

Commands:

```bash
rg -n "DataRepresentation|loadTransferable\\(type:\\s*Data\\.self|Data\\.self|loadDataRepresentation|itemProvider" ios/HoopsClips/HoopsClips/Views/VideoPlayerView.swift ios/HoopsClips/HoopsClips -g '*.swift'
```

Result:

- No matches.

Build iOS Apps MCP:

```text
build_sim -skipPackagePluginValidation
test_sim -skipPackagePluginValidation -only-testing:HoopsClipsTests
```

Results:

- Simulator Debug build succeeded.
- HoopsClips unit tests passed: `93 passed`, `0 failed`.
- New test `testVideoImportPolicyUsesFileBackedVideoTypesOnly()` passed.

Physical iPhone:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=00008130-000A001A1178001C' \
  -derivedDataPath /tmp/hoopclips-phase60-device-build \
  -allowProvisioningUpdates \
  -skipPackagePluginValidation \
  HOOPS_DEVELOPMENT_TEAM=<configured-team-id> \
  build

xcrun devicectl device install app \
  --device E5786BB6-0095-5509-8B85-110C0B5CE6D3 \
  /tmp/hoopclips-phase60-device-build/Build/Products/Debug-iphoneos/HoopsClips.app

xcrun devicectl device process launch \
  --device E5786BB6-0095-5509-8B85-110C0B5CE6D3 \
  atrak.charlie.hoopsclips
```

Results:

- Physical-device Debug build succeeded.
- App installed on the wired iPhone.
- App launched with bundle ID `atrak.charlie.hoopsclips`.

Internal staging archive:

```bash
xcodebuild archive \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath ios/build/HoopsClips-Phase60-InternalStaging.xcarchive \
  -derivedDataPath /tmp/hoopclips-phase60-archive-derived \
  -allowProvisioningUpdates \
  -skipPackagePluginValidation \
  -xcconfig ios/HoopsClips/HoopsClips/Config/InternalStaging.xcconfig \
  HOOPS_DEVELOPMENT_TEAM=<configured-team-id>
```

Results:

- `** ARCHIVE SUCCEEDED **`
- Archive path: `ios/build/HoopsClips-Phase60-InternalStaging.xcarchive`
- Bundle ID: `atrak.charlie.hoopsclips`
- Version: `1.0.0`
- Build: `5`
- `HOOPSAppEnvironment`: `internal_staging`
- `HOOPSCloudLaunchMode`: `internal_only`

Main-branch GitHub checks for commit `66baa27`:

- iOS Internal TestFlight Upload push run `26677956763`: success.
- Cloud Edit Deploy Preflight push run `26677956739`: success.

Submission preflight:

```bash
python3 scripts/submission_readiness_preflight.py --archive-path ios/build/HoopsClips-Phase60-InternalStaging.xcarchive
```

Result:

- `31 pass`, `0 warn`, `3 fail`.
- Current main-branch Cloud and iOS workflow checks pass for `66baa27`.
- The local phase60 internal-staging archive is accepted as the upload artifact candidate.

## Remaining Smoke

- Real-device import from Photos still needs manual confirmation on the wired iPhone with a large source video.
- If the user still sees `Preparing video...` hang after this patch, the next suspect is the project persistence copy/thumbnail generation path, not the Photos transfer fallback.
- Launch readiness still needs the launch-grade team/highlight accuracy report, fresh secret-gated manual deploy preflight, and installed TestFlight post-install smoke.

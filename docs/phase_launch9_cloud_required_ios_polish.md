# Phase Launch9 Cloud Required iOS Polish

Date: 2026-05-23
Branch: `codex/phase-launch9-cloud-required-ios-polish`

## Scope

This branch tightens the iOS control surface for cloud-required internal builds. It does not add local video analysis, local rendering, local composition, Remotion, Canva, or backend simulation.

## Changes

- Replaced the synthetic analysis time estimate in cloud-required builds with copy that states analysis runs in the HoopClips backend.
- Updated the legacy local export button in cloud-required builds to present an AI Edit cloud render handoff instead of "Export Highlight Reel."
- Kept the existing ViewModel guard that blocks `VideoExportService.exportHighlights` when `AppConstants.requiresCloudVideoPipeline` is true.
- Preserved preview, download, share, and external-editor handoff behavior for completed cloud renders.

## Validation Results

- `git diff --check` passed.
- `python3 scripts/submission_readiness_preflight.py` completed with expected launch blockers still present: `pass=16 warn=1 fail=10` before this doc was staged.
- `bash ios/scripts/verify_internal_staging_config.sh` passed.
- Build iOS Apps simulator Debug build passed.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch9-cloud-required-polish-derived CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment` passed.

## Remaining Submission Blockers

Submission is still **NO-GO** until staging secrets, deploy proof, Worker version proof, a signed TestFlight archive, and installed iPhone smoke are complete.

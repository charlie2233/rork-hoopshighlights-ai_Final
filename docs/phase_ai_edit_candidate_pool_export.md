# Phase AI Edit Candidate Pool Export

## Goal

Make Export simpler by letting users start AI Edit after cloud analysis produces a candidate pool, even if they did not manually keep clips in Review.

## Change

- `HighlightsViewModel.canRequestCloudEdit` now requires a source upload and a non-empty cloud edit candidate pool instead of at least one manually kept clip.
- Export can show the AI Edit workspace when cloud candidates exist with zero kept clips.
- Export summary copy now explains that HoopClips can pick from AI candidates and that manual review is optional.
- AI Edit hero copy shows candidate count when there are no manually kept clips.
- The disabled primary button no longer tells users to keep clips first; it points them back to cloud analysis when candidates are missing.

## Architecture

This keeps the existing cloud-first boundary. iOS still does not analyze, plan, render, or compose video locally for AI Edit. It only lets the user request the cloud edit using candidate clips already produced by cloud analysis and validated by the request builder.

## Evidence Commands

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7B54F49A-3CB4-4A13-9E2F-9A333E61ABDC' -derivedDataPath /tmp/hoopclips-candidate-export-visible-bft CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation build-for-testing
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7B54F49A-3CB4-4A13-9E2F-9A333E61ABDC' -derivedDataPath /tmp/hoopclips-candidate-export-visible-bft CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -only-testing:HoopsClipsTests -quiet
```

## Evidence Result

Verified locally on 2026-06-01:

- `git diff --check` passed.
- Debug `build-for-testing` passed on iPhone 17 Pro Max simulator `7B54F49A-3CB4-4A13-9E2F-9A333E61ABDC`.
- `HoopsClipsTests` passed on iPhone 17 Pro Max simulator `7B54F49A-3CB4-4A13-9E2F-9A333E61ABDC`: 140 passed, 0 failed.
- An earlier run against iPhone 17 Pro simulator `7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2` was interrupted by CoreSimulator `Invalid device state`; no test result from that run was used as evidence.

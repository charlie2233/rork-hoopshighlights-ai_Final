# Phase Launch212 Analysis Team Copy Compact

Branch: `codex/phase-analysis-team-copy-compact`

## Goal

Keep cloud analysis progress copy readable when users rename a detected team with a long school, tournament, or jersey label.

## Change

- Compact long selected-team titles inside the analysis progress detail.
- Preserve the full team label in the actual app state and backend request payloads.
- Keep the visible progress card focused on user guidance: selected-team focus, uncertain plays for Review, and real cloud status.

## Architecture

- Cloud still owns analysis, team evidence, GPT selection, edit planning, rendering, and storage.
- iOS only displays the selected target and progress status.
- This change does not alter team IDs, selected-team payloads, candidate generation, GPT inputs, or render behavior.

## Validation

Local validation completed on June 2, 2026:

```bash
git diff --check
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudAnalysisBackgroundReminderIsHonestAndVisible
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47'
```

Results:

- `git diff --check`: passed.
- Focused `HoopsClipsTests/testCloudAnalysisBackgroundReminderIsHonestAndVisible`: passed.
- Debug `build-for-testing`: passed.
- Test result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.02_00-26-26--0700.xcresult`

## Remaining Evidence

This improves small-phone readability but does not prove internal TestFlight readiness. The remaining launch gates still include installed-device smoke, live staging cloud edit/version proof, and launch-grade labeled accuracy evidence.

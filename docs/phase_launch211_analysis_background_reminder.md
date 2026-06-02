# Phase Launch211 Analysis Background Reminder

Branch: `codex/phase-analysis-background-reminder`

## Goal

Make the cloud analysis progress screen easier for internal testers to trust during long uploads and analysis runs. The app now distinguishes upload from cloud handoff:

- During upload: tell the user to keep HoopClips open.
- After cloud analysis is queued/running: remind the user they can switch apps and reopen HoopClips for real job status.
- Keep status copy honest: no fake AI thinking, no fake ETA, no artificial waits, and no local iOS analysis/rendering changes.

## Changed Files

- `ios/HoopsClips/HoopsClips/Models/CloudAnalysisProgressCopy.swift`
- `ios/HoopsClips/HoopsClips/Views/VideoPlayerView.swift`
- `ios/HoopsClipsTests/HoopsClipsTests.swift`

## Architecture Notes

- Cloud still owns analysis and highlight candidate generation.
- iOS still only uploads/imports, starts analysis, shows real status, and displays Review.
- The reminder is UX copy only. It does not create fake progress, fake backend work, or local video processing.
- Upload remains special: users are told to keep the app open until handoff instead of being told they can safely leave too early.

## Validation

Local validation completed on June 2, 2026:

```bash
git diff --check
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' -only-testing:HoopsClipsTests
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47'
```

Results:

- `git diff --check`: passed.
- `HoopsClipsTests`: passed.
- Debug `build-for-testing`: passed.
- Test result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.02_00-18-22--0700.xcresult`

## Real-Device Smoke

When an iPhone is available:

1. Import a large video.
2. Confirm upload copy says to keep HoopClips open.
3. Start cloud analysis and wait until queued/finding/scoring status appears.
4. Confirm the progress card shows the cloud background reminder.
5. Switch to another app, return to HoopClips, and confirm the project refreshes from real job state.
6. Continue to Review, Export, AI Edit, render, preview, revision, and share/open-in.

## Remaining Launch Evidence

This phase improves tester clarity but does not prove internal launch readiness by itself. Remaining evidence still includes installed TestFlight smoke, live staging cloud version/render proof, and launch-grade selected-team/highlight accuracy results.

# Phase Launch208 Background Cloud Job Reminder

Date: 2026-06-02

## Goal

Make it clear to users that cloud analysis and cloud AI Edit can keep working after the backend job has started, while avoiding a false promise that local import or upload can finish if iOS suspends the app too early.

## What Changed

- Added a visible AI Edit status reminder when a cloud source exists:
  - before start: users can switch apps once AI Edit starts
  - plan ready: users can switch apps after render starts
  - queued/rendering: the cloud job keeps running and users can reopen HoopClips for latest status
- Added accessibility identifier `export.aiEdit.backgroundReminder`.
- Updated cloud analysis progress copy:
  - upload step tells users to keep HoopClips open until upload is done
  - queued/cloud-active steps say users can switch apps and reopen HoopClips for real status
  - local fallback scoring copy no longer says it is running in the cloud
- Added unit coverage for the AI Edit background reminder copy.

## Architecture Notes

- iOS still does not render, analyze, compose, or export production video locally.
- The reminder only appears for AI Edit when the project has a cloud-uploaded source object.
- The copy does not claim fake ETA, fake thinking, or artificial background work.
- Backend status remains authoritative; the app refreshes real job state when the user returns.

## Validation Evidence

Commands run locally:

```bash
git diff --check
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' -derivedDataPath /Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClipsCodex -resultBundlePath /Users/hanfei/rork-hoopshighlights-ai_Final/build/HoopsClipsBackgroundReminderTests.xcresult -only-testing:HoopsClipsTests
```

Result:

- `git diff --check`: passed.
- `HoopsClipsTests` on iPhone 17 simulator: passed.
- Result bundle generated during validation: `build/HoopsClipsBackgroundReminderTests.xcresult` (not committed).

## Real-Device Smoke

Still needs a wired iPhone/TestFlight smoke:

1. Import a video.
2. Start cloud upload/analysis.
3. Leave HoopClips after upload starts.
4. Reopen HoopClips and verify real analysis status/result.
5. Start AI Edit render.
6. Leave HoopClips while queued/rendering.
7. Reopen HoopClips and verify the latest real render status, preview, and share.

Do not record full presigned URLs, storage credentials, or private key material in smoke evidence.

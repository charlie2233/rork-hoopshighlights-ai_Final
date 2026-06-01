# Phase Launch199 - Readable Team Controls

## Goal

Make the pre-analysis team choice and AI Edit summary easier to read on small phones and large Dynamic Type, without changing the cloud-first video pipeline.

## Changes

- Shortened pre-analysis team setup copy so users see the action faster:
  - choose one team;
  - choose All teams if unsure;
  - rename the team if helpful.
- Avoided cramming long detected team names into the team scan status row.
  - The status now says `1 team found` or `2 teams found` instead of joining long team labels with `vs`.
  - The full team names still appear in the selectable team cards.
- Let key team labels and AI Edit summary chips wrap more naturally at accessibility text sizes.

## Architecture

- iOS remains a control surface for team choice, status, review, preview, download, and share.
- Cloud remains responsible for team quick scan, analysis, GPT clip selection, edit planning, rendering, and storage.
- No local iOS analysis/rendering/composition/export behavior was added.

## Validation

Local validation:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' test -only-testing:HoopsClipsTests/HoopsClipsTests/testDetectedTeamStatusCopyAvoidsCrammingLongTeamNames
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build-for-testing
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -sdk iphonesimulator -destination 'id=09C3102D-6824-4BA2-8CBE-F6348561F6E8' build
```

Results:

- `git diff --check`: passed.
- Focused iOS team-status copy test: passed on iPhone 16e simulator `09C3102D-6824-4BA2-8CBE-F6348561F6E8`.
- Test result bundle: `/Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClips-frohzqtyxvppxjaenxfpuutmamrz/Logs/Test/Test-HoopsClips-2026.06.01_14-10-14--0700.xcresult`.
- Debug `build-for-testing`: passed.
- Debug simulator `build`: passed.

## Remaining Launch Evidence Needed

- Real-device post-install TestFlight smoke is still required for the full launch gate.
- This branch did not run GitHub Actions; commit should use `[skip ci]` to protect the Actions budget.

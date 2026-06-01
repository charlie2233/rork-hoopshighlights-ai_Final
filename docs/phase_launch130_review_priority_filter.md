# Phase Launch130: Review Priority Filter

## Goal

Make Review easier and more accurate before Export by giving users one obvious queue for clips that deserve a closer look: uncertain team calls, outcome/timing checks, blocks, steals, and defensive plays.

## Changes

- Added a `Priority` Review filter.
- The existing `Check priority plays` card now opens the combined `Priority` queue instead of choosing only one narrower filter.
- The filter bar shows `Priority <count>` when there are clips that need attention.
- Existing detailed filters remain available for users who want to drill into team checks, defense, blocks, steals, kept, or skipped clips.

## Architecture

- No cloud contract changed.
- No local analysis, rendering, composition, or export logic changed.
- The filter only changes iOS review visibility so users can correct clips before the cloud AI Edit job.

## Validation

Commands to run:

```bash
git diff --check
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build-for-testing
```

Results:

- `git diff --check`: passed.
- Debug simulator build: passed.
- Debug simulator `build-for-testing`: passed.

## Notes

- Commit should use `[skip ci]` to preserve GitHub Actions budget.
- Preserve unrelated untracked root Xcode folders.

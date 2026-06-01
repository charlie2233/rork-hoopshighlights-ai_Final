# Phase Launch172 History Direct Resume

## Goal

Make History simpler and clearer for testers on small phones. Users should not have to open a detail sheet just to resume an old project, and button text should describe what it actually does.

## Change

- History row action `Open` is now `Details` because it opens the project detail sheet.
- Added a direct `Resume` action on each project row when the saved source video is available.
- Current projects show `Current` in that slot and stay disabled.
- Missing-source projects keep the action disabled instead of pretending they can reopen.
- Existing title-tap rename behavior stays intact.

## Architecture

This is iOS control-surface UX only. It does not add local analysis, rendering, composition, or export logic. Reopening a project only restores saved local project state for Player, Review, and Export.

## Validation

Run locally:

```bash
git diff --check
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17'
```

## Launch Note

This reduces tester confusion in History while preserving cloud-first AI Edit boundaries. It also keeps button labels short enough for the adaptive grid and accessibility-size layouts.

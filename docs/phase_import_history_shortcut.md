# Phase: Import History Shortcut

Branch: `codex/phase-import-history-shortcut`

## Goal

Make the large-video import recovery path easier for testers when Photos/File import appears stuck but the project may already be saved in History.

This is an iOS control-surface change only. It does not add local analysis, local rendering, local composition, or cloud backend work.

## Changes

- `VideoPlayerView` now accepts an `onOpenHistory` callback from the tab shell.
- Import recovery alerts that indicate a likely saved/background project now use the title `Check History`.
- Those recovery alerts now include an `Open History` button.
- The regular import failure alert stays as `Video Import Failed`.
- The alert copy is shorter so it fits better on small phones and larger Dynamic Type settings.
- The shortcut records a stability checkpoint without logging file paths, source URLs, secrets, or presigned URLs.

## Evidence

### Commands

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-import-history-bft CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation build-for-testing
```

### Results

- `git diff --check` passed.
- iOS Debug `build-for-testing` passed with derived data at `/tmp/hoopclips-import-history-bft`.

## Launch Notes

- This directly addresses the tester report where a video appears to sit on `Preparing video`, but closing and reopening shows it imported.
- It gives nontechnical users a direct recovery action instead of asking them to discover the History tab.
- No GitHub Actions should be needed for this phase.

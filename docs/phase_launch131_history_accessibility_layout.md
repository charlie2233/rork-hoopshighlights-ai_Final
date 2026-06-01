# Phase Launch131: History Accessibility Layout

## Goal

Keep History readable on smaller phones and larger iOS text sizes, especially after users rename projects with longer team/game names.

## Changes

- History project rows now switch to a vertical layout at accessibility Dynamic Type sizes.
- Project thumbnails expand above the text at larger text sizes instead of squeezing titles sideways.
- Project titles can show more lines in accessibility sizes.
- Inline project rename uses a taller multi-line text field with a visible focus border.
- Existing tap-to-rename behavior remains unchanged.

## Architecture

- This is an iOS layout/readability change only.
- No video analysis, edit planning, rendering, export, or cloud API behavior changed.
- No local rendering or local AI work was added.

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

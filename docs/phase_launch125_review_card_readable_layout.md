# Phase Launch125 Review Card Readable Layout

Date: 2026-05-31
Branch: `codex/phase-launch125-review-card-readable-layout`

## Goal

Improve the iOS Review screen so clip names, time ranges, team badges, and confidence are less likely to be hidden on small iPhones or larger Dynamic Type settings.

## User Impact

- Clip cards are easier to scan while deciding what to keep or skip.
- Confidence no longer competes horizontally with the clip title, timestamp, and badges.
- Clip detail metadata uses wrapping/adaptive layout instead of a single crowded row.
- This supports the launch requirement that visible words stay readable across phone sizes and accessibility settings.

## Architecture Boundary

This is an iOS presentation-only change. It does not change:

- cloud analysis
- GPT clip selection
- edit planning
- rendering
- exports
- storage
- launch gates or feature flags

## Changes

- Refactored the Review clip-card header into reusable helper views.
- Kept the action icon fixed at `44 x 44`.
- Moved the confidence badge below the clip title/time/badges inside the text column, removing the previous title-vs-confidence squeeze.
- Added a time-range fallback that can wrap the range and duration across two lines.
- Updated the clip detail sheet header to use the same readable stacking pattern.
- Changed clip detail timing metadata from one horizontal row to an adaptive grid.

## Files Changed

- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`

## Validation

```bash
git diff --check
```

Result: passed.

```bash
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build
```

Result: passed with exit code `0`.

```bash
xcodebuild -quiet \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath .codex-build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build-for-testing
```

Result: passed with exit code `0`.

## Notes

- GitHub Actions was not used for this small UI-only patch to preserve the remaining Actions budget.
- Local disk was low during validation, so the existing warmed `.codex-build/DerivedData` path was reused instead of creating another full DerivedData directory.
- The unrelated untracked root Xcode folders remain untouched.


# Phase Launch179: AI Edit Small-Phone Clarity

Branch: `codex/phase-launch179-ai-edit-small-phone-clarity`

## Goal

Keep moving HoopClips toward internal TestFlight readiness by reducing hidden-text risk in the AI Edit flow on smaller phones and accessibility text sizes.

## Finding

The AI Edit revision command grid used a fixed 132pt adaptive minimum and its command labels did not explicitly wrap or scale. On narrow devices or larger text sizes, commands such as More Slow-Mo, Original Audio, Vertical 9:16, and Widescreen 16:9 could compress or clip.

## Change

- Added a dynamic `revisionCommandGridColumns` layout.
- Revision commands now use wider cells for accessibility text sizes.
- Revision command labels now support multiline text, scale slightly, and keep their height stable.

## Architecture Check

- This is UI-only.
- No local analysis, local rendering, local composition, GPT calls, FFmpeg commands, storage paths, or cloud policy changes were added.
- Cloud remains responsible for AI edit planning, revisions, rendering, storage, and validation.

## Validation

Passed:

```bash
git diff --check
```

Passed:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/hoopclips-launch179-derived-data \
  CODE_SIGNING_ALLOWED=NO \
  build-for-testing \
  -quiet
```

## Remaining Smoke

Still needs real-device/TestFlight smoke across import, team scan, Review, AI Edit, render, preview, revision, and share/open-in.

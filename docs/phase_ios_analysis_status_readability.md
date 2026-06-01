# Phase iOS Analysis Status Readability

## Goal

Make the import and cloud-analysis status screen easier to read on small phones and accessibility text sizes while preserving the cloud-first analysis path.

## Changes

- Analysis progress header now uses a fallback layout so the title and percent do not fight for one line on narrow screens.
- Backend status and detail copy now wrap predictably instead of clipping.
- Analysis completion metrics now use an adaptive grid instead of a fixed row, so localized labels and large text sizes stay visible.
- Analysis quality summary rows allow more lines and still report real backend diagnostics only.

## Architecture Notes

- No local video analysis, rendering, composition, or export was added.
- No fake AI thinking, fake wait, or artificial ETA was added.
- The screen still shows real cloud/backend progress, status messages, and diagnostics.

## Validation

Run after this change:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=A46E2157-77ED-42CE-959D-65C068681A47' build
```

Recommended device smoke:

1. Import a video on a small iPhone.
2. Start cloud analysis.
3. Confirm progress title, percent, backend status, and detail text are visible.
4. Finish analysis and confirm Clips, Kept, Duration, and quality-summary rows wrap cleanly.

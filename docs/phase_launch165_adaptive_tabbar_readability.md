# Phase Launch165 Adaptive Tab Bar Readability

## Goal

Make the main app navigation easier to use on small phones and with larger text settings.

## Change

- The custom bottom tab bar now uses `ViewThatFits`.
- On wider layouts it keeps the full five-tab row.
- On smaller or larger-text layouts it falls back to a horizontal scroll row so labels are not forced into tiny hidden text.
- Tab labels can wrap to two lines by default and three lines for Accessibility Dynamic Type.
- The existing horizontal drag gesture for switching tabs remains in place.

## Guardrails

- No video analysis, rendering, export, or cloud behavior changed.
- No account, secret, storage, or presigned URL behavior changed.
- This is an iOS control-surface/readability fix only.

## Validation

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-launch165-derived-data \
  build-for-testing CODE_SIGNING_ALLOWED=NO -quiet

xcodebuild -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-launch165-derived-data \
  test -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -quiet
```

## Launch Notes

This does not prove launch readiness by itself. It reduces one visible UI risk from testing: navigation words getting cramped or hidden across phone sizes and Dynamic Type.

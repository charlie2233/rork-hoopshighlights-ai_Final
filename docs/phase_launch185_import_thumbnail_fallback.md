# Phase Launch185 Import Thumbnail Fallback

Date: 2026-06-01
Branch: `codex/phase-launch185-import-off-main-photo-transfer`

## Goal

Keep real iPhone video import from getting blocked by fragile preview thumbnail extraction. The current repo already uses file-backed Photos transfer only, supports `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`, and has no `Data.self` Photos fallback.

## Change

`ProjectHistoryStore` now treats imported-video thumbnail extraction as best effort:

- Tries multiple safe sample times instead of only frame zero.
- If AVAsset thumbnail extraction fails, writes a small HoopClips fallback thumbnail.
- Still persists the original imported video and project normally.
- Does not add local analysis, rendering, composition, or export logic.

This targets the tester symptom where import appears stuck before the project opens even though the video may be present after app restart.

## Validation

```bash
git diff --check
```

Result: passed.

```bash
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2 -derivedDataPath .codex-build/DerivedData build-for-testing
```

Result: passed.

## Remaining Risk

Real-device import smoke is still needed with the exact iPhone footage that hung:

1. Import from Photos.
2. Confirm the project opens without closing/reopening the app.
3. Confirm History shows the project and thumbnail.
4. Run cloud team scan and cloud analysis after import.

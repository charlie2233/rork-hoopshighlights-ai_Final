# Phase Launch208: Visible Text Compatibility

## Goal

Make Export options easier to read on smaller iPhones and with larger Dynamic Type settings.

## Change

- Export theme option cards now use the same Dynamic Type-aware adaptive grid behavior as other export option groups.
- Theme names can wrap to multiple lines instead of clipping inside compact tiles.
- Locked Pro chips keep stable sizing, and selected-theme helper copy wraps instead of disappearing.

## Architecture

- iOS UI only changed option presentation.
- No local video analysis, rendering, composition, or cloud policy behavior changed.
- Cloud remains the owner of analysis, GPT selection, EditPlan generation, rendering, and storage.

## Validation

Passed locally:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-launch208-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build
```

Result:

- `git diff --check`: passed.
- iOS Debug simulator build: passed with `** BUILD SUCCEEDED **`.

# Phase UX23: Simple Long Reel Length

## Goal

Make AI Edit easier to use while exposing the long 4:30 highlight length the backend already supports.

## Change

The default AI Edit length chips now show:

- `30s`
- `1m`
- `2m`
- `4:30`

Shorter/midpoint values such as `15s`, `45s`, `90s`, `3m`, and `4m` remain available through `More lengths`.

## Why This Helps

The previous quick choices stopped at `2m` unless a prompt selected `4:30` or the user opened all options. The backend policy, template packs, GPT prompt parser, and render validator already support `270` seconds, so this is a UI simplification rather than a policy change.

## Architecture

- iOS still only sends the selected `targetDurationSeconds` to cloud AI Edit.
- Cloud backend still owns clip selection, GPT planning, validation, rendering, and storage.
- No local video analysis, composition, or export was added.

## Validation

Passed:

```bash
git diff --check
```

Passed:

```bash
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 16e' \
  -derivedDataPath /tmp/hoopclips-ux23-dd CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation -skipMacroValidation
```

Result:

```text
** TEST BUILD SUCCEEDED **
```

Attempted, but the simulator install phase failed after compile/link with CoreSimulator invalid device state:

```bash
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 16e' \
  -derivedDataPath /tmp/hoopclips-ux23-dd CODE_SIGNING_ALLOWED=NO \
  -skipPackagePluginValidation -skipMacroValidation \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditLengthChoicesStartSimpleButKeepSelectedLongDurationVisible \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditLengthChoicesExposeFourThirtyByDefault \
  -only-testing:HoopsClipsTests/HoopsClipsTests/testAIEditLengthChoicesCanRevealAllAllowedDurations
```

Failure:

```text
com.apple.CoreSimulator.SimError Code=405: Invalid device state
NSMachErrorDomain Code=-308: server died
** BUILD INTERRUPTED **
```

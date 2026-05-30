# Phase Clip142: Defensive Diagnostics Parity

## Goal

Improve selected-team highlight review visibility for defensive plays. Backend analysis already emits block, steal, forced-turnover, and defensive-stop review counts; the control-plane and iOS diagnostic models now expose the same defensive families.

## Change

- Added `forcedTurnoverReviewSegments` and `defensiveStopReviewSegments` to the control-plane `CloudDiagnostics` type.
- Added the same fields to the iOS `CloudDiagnostics` model.
- Updated iOS analysis quality status copy so defensive review summaries can mention blocks, steals, forced turnovers, and defensive stops.
- Updated persistence/model tests so defensive diagnostic counts survive encode/decode.

## Architecture

This does not add iOS analysis or rendering. Cloud still owns detection, team attribution, GPT editing, EditPlan generation, rendering, and storage. iOS only displays the cloud-owned diagnostic counts.

## Validation

Commands:

```bash
git diff --check
npm --prefix services/control-plane ci
npm --prefix services/control-plane run typecheck
xcodebuild -list -project ios/HoopsClips.xcodeproj
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16' CODE_SIGNING_ALLOWED=NO build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' CODE_SIGNING_ALLOWED=NO build
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests
```

Results:

- `git diff --check` passed.
- Control-plane dependencies installed locally and `npm --prefix services/control-plane run typecheck` passed.
- `xcodebuild -list` resolved the `HoopsClips` scheme.
- The first iOS build attempt failed before compile because no `iPhone 16` simulator exists on this machine.
- The rerun on the available `iPhone 17` simulator passed: `** BUILD SUCCEEDED **`.
- `HoopsClipsTests` on the `iPhone 17` simulator passed: `** TEST SUCCEEDED **`.

## Launch Note

This is not the missing 85% accuracy proof. It improves operator/user visibility for defensive clips while the launch-grade labeled real-footage report remains required.

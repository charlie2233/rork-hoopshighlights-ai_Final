# Phase iOS Import History Polish

## Goal

Continue internal TestFlight readiness by checking the old long Photos import concern and making History project actions simpler to understand on small phones.

## Import Audit

The current import path already keeps iOS in the intended control-surface role:

- Photos import uses file-backed `Transferable` representations for `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- There is no `Data.self` Photos fallback in the current path.
- File copy/move and thumbnail work run away from the main actor.
- `recoverVisibleProjectFromStoreIfNeeded()` and `reconcileCurrentProjectLoadState()` recover saved visible projects when import finishes but the player state needs refreshing.

## Change

- Changed the History empty preview hint from `Choose Source or Export below.` to `Choose a saved video below.`
- Replaced internal workflow nouns like `Player, Review, Export` with user-facing action copy:
  - `Continue editing this project`
  - `Watch original video`
  - `Watch saved reel`
  - `Share saved reel`
- Tightened the focused History copy test so future text remains short and avoids those internal nouns.

## Architecture

- iOS still only imports, persists, previews, uploads, reviews, downloads, and shares.
- No local production analysis, GPT edit planning, rendering, composition, or export pipeline was added.
- No fake thinking, fake ETA, artificial waits, secrets, R2 credentials, or full presigned URLs were added.

## Validation

Planned local checks:

```bash
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-history-polish-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation -only-testing:HoopsClipsTests/HoopsClipsTests/testHistoryProjectActionsUseShortReadableCopy test
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16e' -derivedDataPath /tmp/hoopclips-history-polish-dd CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation build-for-testing
```

Results:

- `git diff --check`: passed.
- Focused `testHistoryProjectActionsUseShortReadableCopy`: passed on `iPhone 16e`.
  - Result bundle: `/tmp/hoopclips-history-polish-dd/Logs/Test/Test-HoopsClips-2026.06.02_18-28-47--0700.xcresult`
- Debug `build-for-testing`: passed on `iPhone 16e`.

## Launch Note

This improves History readability and confirms the import code path remains file-backed, but it does not close the full launch gate. Internal TestFlight still needs current cloud deploy evidence, installed-app smoke, and the human-reviewed accuracy report.

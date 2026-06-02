# Phase Review Filter Simplification

Branch: `codex/phase-review-filter-simplification`

## Goal

Make Review easier to use on small phones while keeping the important accuracy filters available. Review is where users rescue uncertain team calls, blocks, steals, sound-reaction clips, and unclear outcomes before AI Edit.

## Change

- Review now shows primary filters first:
  - All
  - Priority
  - selected team
  - team check
  - general check
- Secondary filters such as Defense, Blocks, Steals, Sound, Kept, and Skipped are behind one `More` chip.
- If a secondary filter is active, it stays visible even when the extra filters are collapsed.
- Added `ReviewFilterDisplayPolicy` so this behavior is deterministic and unit-tested.

## Architecture Notes

- This is an iOS display/control-surface change only.
- No local video analysis, GPT editing, render planning, rendering, composition, export, Remotion, Canva, or FFmpeg behavior was added.
- Defensive and sound-reaction filters remain available for accuracy review; they are just not all shown at once by default.

## Validation

Local validation completed on June 2, 2026 without using GitHub Actions:

```bash
xcodebuildmcp test_sim -only-testing:HoopsClipsTests
xcodebuildmcp build_sim
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' -derivedDataPath /Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClipsCodex build-for-testing CODE_SIGNING_ALLOWED=NO
git diff --check
```

Results:

- `HoopsClipsTests`: 177 passed, 0 failed, 0 skipped.
- Debug simulator build: passed.
- Debug build-for-testing: passed.
- `git diff --check`: passed.
- Test result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-02T08-19-40-769Z_pid26025_044c380d.xcresult`.
- Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-02T08-21-37-967Z_pid26025_bc777d8d.log`.

## Remaining Launch Notes

- Needs device/UI smoke on a small iPhone and a larger Dynamic Type setting to confirm the collapsed filter row does not hide selected state or clip counts.
- Real-device/TestFlight smoke still needs the full path: import, cloud team scan, team selection, cloud analysis, Review, AI Edit render, preview, revision, and share/open-in.

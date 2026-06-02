# Phase Review Priority Action Polish

Branch: `codex/phase-review-priority-action-polish`

## Goal

Make Review easier for players, parents, and coaches while improving selected-team/highlight accuracy. Priority clips should put team-risk, defensive plays, sound cues, and unclear outcomes in front of the user without adding more controls.

## What Changed

- `HighlightsViewModel.priorityReviewClips` now sorts priority clips by launch-relevant review risk:
  - blocks, steals, and defensive stops first
  - team attribution checks next
  - unclear outcome/timing and audio-reaction cues preserved for review
  - stronger scores break ties
- The Review priority card now uses compact reason copy such as `2 team checks / 2 defense / 1 sound cue`.
- The compact copy keeps the card readable on small phones and larger Dynamic Type.

## Architecture Notes

- iOS still does not analyze, plan, render, or decide final GPT keeps locally.
- This is a Review-surface ordering and copy improvement only.
- Cloud candidate generation, GPT selection, EditPlan validation, rendering, storage, and policy remain backend-owned.
- Priority/audio/defense clips are review aids; they do not become final rendered clips unless the backend validates the edit plan.

## Validation

Local validation completed on June 2, 2026 without using GitHub Actions:

```bash
xcodebuildmcp test_sim -only-testing:HoopsClipsTests
xcodebuildmcp build_sim
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' -derivedDataPath /Users/hanfei/Library/Developer/Xcode/DerivedData/HoopsClipsCodex build-for-testing CODE_SIGNING_ALLOWED=NO
git diff --check
```

Results:

- `HoopsClipsTests`: passed, 177 tests, 0 failures.
  - Result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-02T08-38-16-226Z_pid26025_984704a7.xcresult`
  - Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-06-02T08-38-16-226Z_pid26025_7162e4ec.log`
- Debug simulator build: passed.
  - Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-02T08-39-21-796Z_pid26025_4eb9c554.log`
- Debug build-for-testing: passed.
- `git diff --check`: passed.

## Remaining Launch Notes

- Needs installed TestFlight smoke on a wired iPhone.
- Needs real user review/eval evidence before claiming the 85% launch accuracy target.
- This phase helps users inspect risky/high-value clips sooner, but it does not replace the launch-grade labeled accuracy report.

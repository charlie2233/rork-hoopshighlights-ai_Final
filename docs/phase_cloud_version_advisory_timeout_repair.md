# Phase Cloud Version Advisory Timeout Repair

Branch: `codex/phase-cloud-version-advisory-timeout-repair`

## Goal

Repair a launch-friction regression where Export could feel stuck while waiting for the advisory `/v1/editing/version` check.

## What Changed

- Restored `CloudEditService.fetchVersion()` to a 6 second timeout.
- Updated `CloudEditServiceTests` so the advisory timeout cannot drift back to 15 seconds unnoticed.
- Tightened the cloud analysis and AI Edit status copy so users are reminded they can switch apps after upload/render handoff and reopen HoopClips for real job status.
- Updated the future plan to separate the local timeout repair from the remaining real-device/staging proof.

## Architecture Notes

- This only affects the advisory cloud status/version request.
- Edit job creation, GPT clip selection, EditPlan generation, rendering, storage, and render status remain cloud-owned.
- iOS still only shows status and starts real cloud requests.
- No local rendering, local analysis, fake ETA, fake thinking text, or simulated backend state was added.
- Transient version-check timeouts remain non-blocking; real config failures can still block rendering.
- Background/foreground behavior still relies on real cloud job state, persisted project IDs, and foreground refresh; iOS does not fake progress while the app is away.

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
  - Result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-02T08-28-15-571Z_pid26025_bab87bb8.xcresult`
  - Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-06-02T08-28-15-571Z_pid26025_1f8e63f2.log`
- Debug simulator build: passed.
  - Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-06-02T08-29-27-940Z_pid26025_6699c5b0.log`
- Debug build-for-testing: passed.
- `git diff --check`: passed.

## Remaining Launch Notes

- Needs real-device/TestFlight proof that Export no longer feels blocked by the cloud version check.
- Needs staging proof that real edit-job creation and render-status polling work after a slow or timed-out advisory version check.
- Real-device smoke should also verify: start upload/analysis, switch to another app after upload handoff, return to HoopClips, and confirm the real cloud status/results refresh.

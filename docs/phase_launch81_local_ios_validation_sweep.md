# Phase Launch81: Local iOS Validation Sweep

## Scope

This pass added fresh local iOS validation evidence for the current launch branch without spending GitHub Actions minutes. It did not change runtime behavior.

Branch under test: `codex/phase-launch70-editing-analysis-progress`.

## Device State

The wired iPhone remains unavailable to Xcode:

- `xcrun devicectl list devices`: `charlie的iPhone`, state `unavailable`, model `iPhone 15 Pro`.
- `xcrun xctrace list devices`: `charlie的iPhone (26.5)` listed under `Devices Offline`.

Installed TestFlight smoke therefore remains blocked on a physical reconnect/trust/device-availability cycle.

## Simulator Build

Tool: Build iOS Apps plugin, `build_sim`.

Configuration:

- Project: `ios/HoopsClips.xcodeproj`.
- Scheme: `HoopsClips`.
- Configuration: `Debug`.
- Simulator: `iPhone 17 Pro`, iOS Simulator `26.0.1`, id `7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2`.
- Derived data: `/tmp/hoopclips-derived-data-launch70`.

Result:

- Status: succeeded.
- Duration: 6.296 seconds.
- Diagnostics: no warnings, no errors.
- Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-31T00-50-57-166Z_pid49862_bac0c481.log`.

## Full iOS Test Run

Tool: Build iOS Apps plugin, `test_sim`.

The plugin call timed out at the tool layer after 120 seconds, but the underlying `xcodebuild` process continued. The `.xcresult` was parsed after completion.

Result bundle:

`/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-31T00-51-06-770Z_pid49862_6fa88d18.xcresult`

Parsed summary:

```bash
xcrun xcresulttool get test-results summary \
  --path /Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-31T00-51-06-770Z_pid49862_6fa88d18.xcresult \
  --format json
```

- Result: `Passed`.
- Total tests: 102.
- Passed tests: 98.
- Skipped tests: 4.
- Failed tests: 0.
- Expected failures: 0.
- Device/configuration summary: 101 passed, 4 skipped, 0 failed on iPhone 17 Pro simulator.
- Test execution log reported `** TEST EXECUTE SUCCEEDED **`.

Notable coverage in the passing test output included:

- File-backed Photos import policy.
- Cloud status copy avoiding fake thinking language.
- Cloud Edit request payloads, render history, locker rerender, revision render idempotency.
- Pre-analysis team choice payloads and selected-team scan/start behavior.
- Candidate ranking with 60-cap GPT handoff, defense reserve, uncertain review clips, and complete shot-context preference.
- Pro template visibility and locked non-payment UX.
- AI Work Timeline/receipt decoding.
- Launch/runtime config readiness checks.

The skipped UI tests were existing gated smoke/performance variants that require explicit fixture or live-flow conditions.

## Build For Testing

Command:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' \
  -derivedDataPath /tmp/hoopclips-derived-data-launch70 \
  -skipMacroValidation \
  COMPILER_INDEX_STORE_ENABLE=NO \
  ONLY_ACTIVE_ARCH=YES \
  build-for-testing
```

Result:

- `** TEST BUILD SUCCEEDED **`.

## Readiness State

Submission preflight is unchanged after this validation sweep:

- 28 pass.
- 6 fail.
- 0 warn.

Remaining blockers:

- Missing launch-grade `--team-accuracy-report`.
- Wired iPhone unavailable/offline for installed smoke.
- Latest main-branch Cloud Edit Deploy Preflight workflow run is stale.
- Latest main-branch iOS Internal TestFlight Upload workflow run is stale.
- Latest secret-gated deploy preflight workflow dispatch is stale.
- Installed TestFlight post-install smoke remains unproven.

The direct editing service and Worker still pass staging version proof at deployed code SHA `2ca029d`; the current `9568ae9` checkout only adds docs after that deploy, and submission preflight accepts the live SHA because no deploy-relevant editing-service files changed afterward.

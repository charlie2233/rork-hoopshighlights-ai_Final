# Phase Clip59 Selected-Team Scan Fail-Safe

## Goal

Prevent HoopClips from offering selected-team highlights unless cloud analysis has actually detected team options from jersey-color evidence. The product should still allow All teams, and uncertain clips remain in Review when a detected team is selected.

## Architecture

- Cloud analysis owns team quick scan, clip attribution, candidate recall, and selected-team filtering.
- iOS only shows the detected team options, sends the selected team/all-teams intent, and keeps the user in Review for uncertain clips.
- No iOS local team detection, video analysis, rendering, or composition was added.
- Full videos are still not sent to GPT. The backend uses sampled video/context frames and candidate clip frames.

## Behavior

- Before a scan returns detected teams, iOS exposes only `All teams`.
- The previous generic `Dark jerseys` / `Light jerseys` fallback is no longer used as a selectable team target.
- When cloud scan finds teams, iOS shows `All teams` plus scan-backed team choices with jersey color labels and swatches.
- Selected-team choices keep `confidenceThreshold = 0.85` and `includeUncertain = true`, so uncertain but review-worthy blocks, steals, and scoring clips stay visible for the user to decide.

## Deploy Guardrails

`scripts/launch_backend_config_preflight.py` now checks the analysis Cloud Run config for:

- `HOOPS_MAX_RETURNED_CLIPS=${_MAX_RETURNED_CLIPS}` with `_MAX_RETURNED_CLIPS: "40"`.
- `HOOPS_TEAM_QUICK_SCAN_ENABLED=${_TEAM_QUICK_SCAN_ENABLED}` with `_TEAM_QUICK_SCAN_ENABLED: "true"`.
- Rich per-candidate frame budget: 6 frames per rich clip, 40 rich candidates, 480 total candidate frames.
- Expanded selected-team recall cap: 120 candidate clips.
- Team quick-scan response budget: 6000 output tokens.
- GPT highlight editing response budget: 8000 output tokens with a 60 second request timeout.
- `HOOPS_OPENAI_API_KEY=HOOPS_OPENAI_API_KEY:latest` as a secret reference only.

## Validation

- `python3 -m py_compile scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py` -> passed.
- `python3 -m unittest scripts.test_launch_backend_config_preflight -v` -> 4 tests passed.
- `python3 scripts/launch_backend_config_preflight.py` -> 74 pass, 12 warn, 0 fail. Warnings are existing launch gates for production cutover, Statsig/Sentry/RevenueCat backend config, and unauthenticated staging ingress posture.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 43 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 146 tests passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip59-bft -skipMacroValidation build-for-testing` -> `** TEST BUILD SUCCEEDED **`.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip59-bft -skipMacroValidation -only-testing:HoopsClipsTests/HoopsClipsTests/testTeamTargetChoicesRequireDetectedTeams test-without-building` -> `** TEST EXECUTE SUCCEEDED **`.
- XcodeBuildMCP `build_sim` -> succeeded for `HoopsClips` Debug on iPhone 17 Pro simulator.
- `git diff --check` -> passed.

## Launch Notes

This improves selected-team launch safety but does not prove the 85% real-world accuracy target by itself. That needs labeled beta footage with team-selection evals. Until then, clips below confident attribution still belong in Review rather than being silently discarded.

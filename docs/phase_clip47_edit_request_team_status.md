# Phase Clip47: Edit Request Team Status

## Goal

Carry explicit selected-team uncertainty from Review into the cloud AI Edit/GPT request path.

## Change

- `EditCandidateClip` now accepts optional `teamAttributionStatus`.
- iOS forwards `Clip.teamAttributionStatus` in `CloudEditCandidateClip`.
- Backend team filtering and compact GPT context preserve explicit `uncertain` status.
- Backend does not allow client-supplied `matched` status to promote a clip without matching attribution evidence.

## Why

The analysis backend can keep a selected-team clip because it is plausible but uncertain. Review already shows `Team?`; GPT should receive the same uncertainty when building the edit so it treats the clip as reviewable selected-team evidence instead of overconfident proof.

## Architecture

- Cloud remains responsible for analysis, team attribution, GPT selection, edit planning, rendering, and validation.
- iOS only forwards cloud-owned metadata from the reviewed clip set.
- GPT still receives compact candidate metadata and sampled keyframes only, not full videos.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_explicit_uncertain_team_status_survives_edit_context -v`: passed, 1 test.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_preserves_explicit_uncertain_team_status -v`: passed, 1 test.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py`: passed.
- `mcp__xcodebuildmcp__.build_sim` for `ios/HoopsClips.xcodeproj`, scheme `HoopsClips`, Debug, iPhone 17 Pro simulator: passed.
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd CODE_SIGNING_ALLOWED=NO -only-testing:HoopsClipsTests`: passed.
  - Existing coverage still passed: `HoopsClipsTests/testCloudEditRequestEncodesOptionalUserPrompt`.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`: passed, 131 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`: passed, 86 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`: passed, 40 tests.

## Launch Recommendation

Keep forwarding `teamAttributionStatus` during internal beta and audit AI Work Receipts against user Review decisions. `uncertain` should preserve recall; it should never be counted as confident selected-team precision.

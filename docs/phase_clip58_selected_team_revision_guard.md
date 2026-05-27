# Phase Clip58 Selected-Team Revision Guard

## Scope

This phase tightens selected-team highlight quality for the cloud-owned HoopClips pipeline. It keeps iOS as the control surface and moves all filtering, GPT validation, EditPlan validation, revision validation, rendering safety, and storage behavior through backend-owned paths.

## Changes

- Selected-team revisions now build GPT revision context from the same team-filtered clip pool used by initial edit planning.
- Render requests for original edit jobs, stored edit jobs, and revisions validate against team-filtered source clips before rendering.
- GPT revision patch payloads include compact team targeting, team attribution status, native shot signals, and only filtered candidate clips.
- Team-id conflicts now win over jersey-color matches: if the selected team ID and attributed clip team ID both exist and differ, the clip is treated as an opponent even when color labels match.
- Defensive GPT decisions cannot cite unsampled shot/tracking frame roles. Blocks, steals, and other defensive highlights stay eligible, but GPT evidence must come from sampled frames.
- iOS resets stale selected-team state when a new video is loaded or a quick scan starts, and detected jersey swatches use the quick-scan primary color hex when available.

## Architecture

- Cloud backend owns analysis, selected-team filtering, GPT clip selection, EditPlan/revision validation, render requests, and storage policy.
- iOS uploads/imports video, runs the pre-analysis team chooser, sends selected `teamSelection`, displays status/review/export UI, previews rendered MP4s, downloads, and shares.
- GPT is allowed to guide semantic editing from compact clip/keyframe context only. It cannot see full videos, output FFmpeg commands, bypass validators, or render.

## Evidence

- Branch: `codex/phase-clip28-cloud-team-quick-scan`
- Focused tests:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_filter_rejects_conflicting_team_id_even_when_color_matches ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_defensive_decision_citing_unsampled_shot_role_is_rejected -v`
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_analysis_team_status_rejects_conflicting_team_id_even_when_color_matches -v`
- Full backend/editing tests:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 146 tests passed.
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 92 tests passed.
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 42 tests passed.
- iOS build gates:
  - Build iOS Apps `build_sim` for `HoopsClips` Debug on `iPhone 17 Pro` simulator -> succeeded in 15.148s. Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-27T08-15-02-126Z_pid97875_e8cd078c.log`.
  - `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip58-bft build-for-testing` -> `** TEST BUILD SUCCEEDED **`.
- Compile check:
  - `python3 -m py_compile ios/backend/app/editing.py ios/backend/app/pipeline.py ios/backend/tests/test_edit_plan_agent.py ios/backend/tests/test_pipeline_quality.py services/editing/editing_app/gpt_reranker.py services/editing/editing_app/main.py services/editing/tests/test_gpt_reranker.py`
- Diff hygiene:
  - `git diff --check` -> passed.

Known warnings from iOS builds are pre-existing: `CloudAnalysisService.swift` has several "no async operations occur within await expression" warnings and `VideoExportService.swift` uses deprecated `export()` on iOS 18.0.

## Launch Notes

- This improves selected-team precision and revision/render safety, but it is not the final TestFlight launch gate.
- Remaining launch blockers are still external/evidence based: CI must run on GitHub runners, staging deploy proof must succeed, and real-device TestFlight smoke still needs a full upload/import/analyze/review/export/revision/share run.
- Selected-team accuracy should still be measured against the labeled eval set before claiming the 85% target.

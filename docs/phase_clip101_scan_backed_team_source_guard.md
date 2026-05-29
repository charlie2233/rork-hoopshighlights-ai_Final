# Phase Clip101: Scan-Backed Team Source Guard

## Goal

Prevent high-confidence selected-team matches from being promoted when clip attribution came from a loose/default source with no frame evidence. This keeps the "choose team before analysis" flow scan-backed while still preserving uncertain clips for user review.

## Change

- `quick_scan`, `gpt_frame_review`, `provider`, and default `unknown` clip attribution sources now require evidence before becoming a confident selected-team match.
- Evidence must include at least two frame references and two role groups.
- `manual` attribution remains allowed without frame evidence because it represents explicit user/operator input.
- Weak or missing evidence becomes `uncertain`, not `matched`, so the clip can still appear in review when `includeUncertain` is true.

## Why

Older or loose payloads can omit `teamAttribution.source`, which defaults to `unknown`. Before this guard, a high-confidence unknown source could be treated as a selected-team match. For launch quality, selected-team highlights should be backed by quick-scan/GPT frame evidence or remain review-only.

## Validation Added

- Edit-plan tests cover unknown/provider attribution without evidence, provider with evidence, and manual attribution.
- Analysis pipeline tests cover the same runtime statuses before review trimming and GPT handoff.

## Commands

- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v` passed: 84 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v` passed: 43 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 55 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v` passed: 175 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v` passed: 97 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 71 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/app/pipeline.py ios/backend/tests/test_edit_plan_agent.py ios/backend/tests/test_pipeline_quality.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py` passed.
- `git diff --check` passed.
- `npm run typecheck` in `services/control-plane` passed.
- `npm test` in `services/control-plane` passed: 28 tests.
- Build iOS Apps `build_sim` passed for `HoopsClips` Debug on iPhone 17 Pro simulator with no warnings/errors. Log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-29T00-11-09-778Z_pid97875_22c98424.log`.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd -quiet build-for-testing` passed.
- Build iOS Apps `test_sim` did not produce a pass/fail result: the MCP call timed out at 120 seconds and the orphaned `xcodebuild test-without-building` process was terminated after remaining stuck for over three minutes with no test output.
- Clean `python3 scripts/submission_readiness_preflight.py --skip-live` returned `pass=22 warn=2 fail=8`.
- PR #32 checks on `b69ac55` failed before job steps started because GitHub Actions account billing/spending limit is blocking runners. GitHub annotation: "The job was not started because recent account payments have failed or your spending limit needs to be increased."

## Launch Notes

This does not reduce candidate recall. Uncertain selected-team clips are still kept for review when enabled, which is important for blocks, steals, and visually ambiguous defensive plays. The stricter guard only prevents weak team labels from being treated as automatic confident matches.

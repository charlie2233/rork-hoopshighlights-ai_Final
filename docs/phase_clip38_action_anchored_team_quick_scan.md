# Phase Clip38: Action-Anchored Team Quick Scan

## Goal

Make the pre-analysis jersey-color team picker more accurate by showing GPT frames from likely basketball action, not only evenly spaced video-context frames. The user should be able to choose `All teams` or a detected jersey-color team before full analysis starts.

## Change

- The `/v1/analysis/jobs/{job_id}/team-scan` endpoint now builds a cloud-owned native candidate pool before calling Team Quick Scan.
- Candidate generation runs in the backend only and is bounded by `team_quick_scan_max_candidate_clips`; Phase Clip63 raises the quality-beta cap to `160`.
- Team Quick Scan receives candidate clip metadata plus sampled keyframes from those candidate windows, improving jersey/color detection around makes, blocks, steals, and other real play moments.
- If action candidate generation fails, the endpoint can still fall back to video-context-only quick scan behavior.

## Safety

- iOS still only uploads, displays team choices, starts analysis, and shows Review.
- GPT still receives only compact metadata and sampled JPEG frames.
- The backend still does not send full videos, presigned URLs, storage keys, R2/GCS credentials, or FFmpeg commands to GPT.
- Rendering and edit planning behavior are unchanged.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_team_quick_scan_uses_action_anchored_candidate_pool ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_team_scan_endpoint_runs_before_start_and_start_accepts_selection -v` -> 2 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/api.py ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py ios/backend/tests/test_team_quick_scan.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 121 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 40 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 84 tests passed.
- `git diff --check` -> passed.

## Launch Recommendation

Use this in internal TestFlight once staging has the OpenAI secret mounted. Do not claim the 85% target until the labeled team/highlight eval passes on real footage with jersey-color ambiguity, opponent possessions, blocks, steals, forced turnovers, and normal makes/misses.

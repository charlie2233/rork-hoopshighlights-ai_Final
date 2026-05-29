# Phase Clip42: Team Scan Full Role Defaults

## Goal

Make the richer team quick-scan frame roles active by default during internal beta. Cost is not the main constraint for this phase; team attribution quality is.

## Change

- `HOOPS_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP` now defaults to `4`.
- The team quick-scan extraction fallback also uses `4` if a settings object does not define the field.
- Scoring clips can include all four ownership roles by default:
  - `ballHandlerSetup`
  - `release`
  - `rimResult`
  - `followThrough`
- Defensive clips can include the setup/action/result role set by default instead of stopping after three frames.
- The env override remains clamped to `1..4`, so staging can reduce the frame budget if needed without code changes.

## Safety

- GPT still receives sampled JPEG frames and compact metadata only.
- No full videos, presigned URLs, storage keys, file paths, or FFmpeg instructions are sent to GPT.
- iOS behavior is unchanged.

## Validation

Run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_thirty ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_scoring_quick_scan_samples_shooter_release_roles ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_defensive_quick_scan_samples_possession_change_roles -v` -> 3 tests passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/config.py ios/backend/app/team_quick_scan.py ios/backend/tests/test_pipeline_quality.py` -> passed.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` -> 126 tests passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` -> 85 tests passed.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` -> 40 tests passed.

## Launch Recommendation

Keep the four-frame default through internal beta so labeled footage exercises the same richer team attribution path users will see. Do not claim the 85% target until the labeled eval proves selected-team precision, selected-team recall with uncertain review clips, and defensive-event recall.

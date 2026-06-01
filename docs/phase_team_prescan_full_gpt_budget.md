# Phase: Team Prescan Full GPT Budget

Branch: `codex/phase-team-prescan-full-gpt-budget`

## Goal

Improve selected-team highlight accuracy before analysis starts by giving the cloud GPT team quick scan the full quality-beta candidate and frame budget.

The iOS app still only uploads the video, asks the backend for detected jersey-color teams, shows `All teams` plus detected choices, and sends the chosen team back to cloud analysis. Cloud owns team detection, clip attribution, filtering, GPT review, edit planning, rendering, and storage.

## Changes

- Interactive team prescan now inspects up to `320` candidate clips instead of `160`.
- All `320` prescan candidates can receive the rich `8` role-frame set when the frame budget allows.
- Prescan clip-frame budget is now `2,560`, enough for `320 * 8` candidate frames.
- Team quick-scan timeout default and clamp now allow `180s`.
- Team quick-scan structured-output budget now defaults to `24,000` tokens so a 320-clip attribution response has room.
- Cloud Build and launch config preflight now require the `180s` timeout and `24,000` token budget.

## Accuracy Notes

- GPT still receives sampled video frames and compact candidate metadata only.
- Full videos, source URLs, storage keys, presigned URLs, and FFmpeg commands are not sent to GPT.
- Blocks, steals, forced turnovers, and defensive stops remain valid selected-team highlight ownership events.
- Confidence below `0.85` remains uncertain; uncertain clips should stay reviewable instead of being used as confident selected-team proof.

## Evidence

### Commands

```bash
git diff --check
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_prescan_settings_use_full_quality_budget_for_interactive_team_scan ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_prescan_frame_budget_uses_rich_and_tail_candidates ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_default_backend_candidate_pool_feeds_gpt_internal_top_three_twenty scripts.test_launch_backend_config_preflight.LaunchBackendConfigPreflightTests.test_analysis_cloudbuild_requires_team_scan_quality_defaults -v
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m py_compile ios/backend/app/config.py ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py ios/backend/tests/test_pipeline_quality.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py
```

### Results

- Targeted prescan/config/preflight tests passed: 4 tests.
- Full backend quick-scan, pipeline quality, and launch preflight suite passed: 102 tests.
- Python compile check passed for the touched backend/preflight files.

## Launch Notes

- This spends more cloud vision budget in internal beta to improve selected-team accuracy before filtering.
- Do not claim the 85% real-footage target until the labeled scan-backed accuracy report passes on real footage.

# Phase Clip55: Rich Team Scan Frame Budget

## Goal

Improve selected-team highlight accuracy by giving GPT more visual evidence for team ownership during the pre-analysis team quick scan, especially for shots, blocks, and steals.

## Change

- `HOOPS_TEAM_QUICK_SCAN_CLIP_FRAMES_PER_CLIP` now defaults to `6` and is clamped to `1..6`.
- Top quick-scan candidates receive richer six-frame ownership sampling.
- Later candidates use a compact three-frame ownership set so the high-recall candidate pool can stay broad.
- Added configurable guards:
  - `HOOPS_TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS` default `40`
  - `HOOPS_TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES` default `480`
- Scoring clips can now sample `ballHandlerSetup`, `preRelease`, `release`, `rimApproach`, `rimResult`, and `followThrough`.
- Blocks can now sample `defenseSetup`, `preChallenge`, `challenge`, `defenseOutcome`, `recovery`, and `finishContext`.
- Steals/forced-turnover style clips can now sample `defenseSetup`, `prePossessionChange`, `possessionChange`, `recovery`, `defenseOutcome`, and `finishContext`.

## Why

The user chooses a target team before full analysis, so team ownership needs more than a single event frame. The richer frame budget gives GPT enough evidence to decide whether a shooter, defender, blocker, or thief belongs to the selected jersey-color team. The compact tail keeps uncertain lower-ranked candidates reviewable without silently dropping broad recall.

## Architecture

- Cloud backend owns frame extraction, GPT team quick scan, attribution, and uncertainty.
- GPT still receives sampled JPEG frames and compact metadata only.
- No full videos, source paths, presigned URLs, storage keys, or FFmpeg commands are sent to GPT.
- iOS behavior is unchanged.

## Validation

- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/config.py ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py ios/backend/tests/test_pipeline_quality.py` passed.
- Focused backend tests passed: 5 tests covering default frame budget config, rich scoring roles, rich defensive roles, rich/compact tail frame allocation, and the 600-frame beta ceiling.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed: 141 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` passed: 90 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 42 tests.
- `git diff --check` passed.

## Launch Recommendation

Keep the rich default enabled for internal beta. Labeled footage should include selected-team made shots, blocks, steals, forced turnovers, opponent highlights, and unclear jersey/possession cases to prove the 85% selected-team and defensive-event targets.

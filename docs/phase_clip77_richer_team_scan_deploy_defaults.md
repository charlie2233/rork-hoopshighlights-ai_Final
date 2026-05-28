# Phase Clip77: Richer Team Scan Deploy Defaults

## Goal

Make staging/internal backend deploys use the quality-first team quick-scan budget already supported by the Python backend. The user chooses a team before full analysis, so the scan should inspect enough candidate clips to identify jersey-color teams and preserve ownership evidence for blocks, steals, defensive stops, and lower-ranked selected-team plays.

## Changes

- Updated `ios/backend/cloudbuild.yaml` quality-beta substitutions:
  - `HOOPS_TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS=60`
  - `HOOPS_TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES=720`
  - `HOOPS_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS=160`
- Updated `scripts/launch_backend_config_preflight.py` so deploy preflight enforces the richer scan defaults.
- Updated `scripts/test_launch_backend_config_preflight.py`.
- Updated `ios/backend/README.md` to document the current defaults and the max-candidate clamp.

## Architecture Notes

- Cloud backend still owns frame extraction, GPT team quick scan, selected-team attribution, filtering, edit planning, rendering, and storage.
- iOS remains the control surface for upload/import, team choice, status, Review, Export, preview, download, and share.
- This increases cloud-side GPT/frame budget only. It does not add local iOS analysis, rendering, FFmpeg, Remotion, or Canva behavior.

## Validation

Commands run from:

`/Users/hanfei/.config/superpowers/worktrees/rork-hoopshighlights-ai_Final/codex-phase-clip5-hybrid-recall-quality`

```bash
python3 -m unittest scripts.test_launch_backend_config_preflight -v
```

Result: passed. 4 tests passed, 0 failed.

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan ios.backend.tests.test_pipeline_quality -v
```

Result: passed. 64 tests passed, 0 failed.

```bash
git diff --check
```

Result: passed with exit code 0.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Result: passed. 55 tests passed, 0 failed.

## Remaining Blockers

- This deploy-default alignment improves staging coverage, but it is still not a real-footage 85% proof.
- Internal launch still needs labeled-footage evaluation and installed TestFlight smoke.

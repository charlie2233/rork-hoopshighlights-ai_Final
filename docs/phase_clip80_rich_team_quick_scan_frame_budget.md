# Phase Clip80 Rich Team Quick Scan Frame Budget

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Improve selected-team highlight accuracy before analysis starts by giving the cloud team quick scan richer sampled-frame evidence. The user still chooses a detected team by jersey color, can choose all teams, and uncertain clips remain available for review instead of being silently dropped.

## Changes

- Raised rich team quick-scan ownership samples from 6 to 8 frames per candidate.
- Raised rich candidate coverage from 60 to 120 candidates.
- Raised total per-clip quick-scan frame budget from 720 to 1200 by default, capped at 1280.
- Raised team quick-scan structured-output budget from 6000 to 12000 tokens so 160 candidate attributions can fit.
- Added richer role frames:
  - scoring: `ballHandlerSetup`, `preRelease`, `release`, `shotArc`, `rimApproach`, `rimResult`, `followThrough`, `finishContext`
  - block: `defenseSetup`, `preChallenge`, `challenge`, `ballDeflection`, `defenseOutcome`, `recovery`, `finishContext`, `aftermath`
  - steal/forced turnover/defensive stop: `defenseSetup`, `prePossessionChange`, `possessionPressure`, `possessionChange`, `ballControlChange`, `recovery`, `defenseOutcome`, `finishContext`

## Architecture Guardrails

- GPT receives sampled frames only, never the full video.
- The scan still returns strict JSON for jersey-color team options and per-clip team attribution.
- Attribution confidence must be visually supported. Ambiguous or low-confidence team ownership is kept below the 0.85 confident threshold so the backend can keep the clip for review.
- Blocks, steals, forced turnovers, and defensive stops are assigned to the defending team that made the play.
- iOS remains the control surface; cloud analysis owns scan, attribution, filtering, and later edit planning.

## Validation

Completed locally:

```bash
python3 -m py_compile ios/backend/app/config.py ios/backend/app/team_quick_scan.py scripts/launch_backend_config_preflight.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan scripts.test_launch_backend_config_preflight -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Results:

- Python compile passed.
- Focused team quick-scan/config tests passed: 28 tests.
- iOS backend discovery passed: 165 tests.
- Scripts discovery passed: 57 tests.

## Remaining Proof

- This phase improves the team-selection evidence path but does not prove the 85% target alone.
- Readiness still needs real labeled-footage eval passing at or above 85%, live staging deploy/version proof, installed TestFlight smoke, and unblocked GitHub Actions.

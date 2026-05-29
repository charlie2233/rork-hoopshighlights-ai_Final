# Phase Clip104: Team Scan Ownership Evidence

## Goal

Improve selected-team highlight accuracy by preventing Team Quick Scan from treating shot-outcome-only frames as enough proof of team ownership.

## Change

- High-confidence scoring attribution now requires at least one shooter or ballhandler ownership frame role, such as `ballHandlerSetup`, `preRelease`, or `release`.
- High-confidence defensive attribution now requires at least one defender ownership/action role, such as `defenseSetup`, `challenge`, `possessionChange`, or `ballControlChange`.
- Shot-arc and rim-result frames can still support event outcome, but without a visible ownership role the attribution confidence is capped below the selected-team confidence threshold and remains review-safe.

## Why

The product flow asks users to choose a team before analysis and then generate highlights for that team only. A rim-result frame can prove a basket happened, but it may not prove which jersey owned the shot. This guard keeps uncertain ownership available for Review instead of letting GPT promote weak team evidence into a confident selected-team match.

## Validation

- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_high_confidence_scoring_attribution_requires_shooter_ownership_frame ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_high_confidence_clip_attribution_accepts_matching_sampled_frame_evidence ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_high_confidence_clip_attribution_requires_distinct_evidence_role_groups -v`
  - Result: `Ran 3 tests`, `OK`.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v`
  - Result: `Ran 178 tests in 5.131s`, `OK`.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v`
  - Result: `Ran 97 tests in 20.476s`, `OK`.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: `Ran 71 tests in 0.325s`, `OK`.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py`
  - Result: passed.
- `git diff --check`
  - Result: passed.
- `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Result: `pass=22 warn=2 fail=8`.
  - Expected launch blockers remain: missing launch-grade labeled team-highlight accuracy report, unavailable wired iPhone, skipped live Worker/editing probes, stale main-branch workflow proof, unproven TestFlight post-install smoke, unproven live Worker kill-switch state, and missing Cloudflare deploy credential proof.
- PR #32 GitHub Actions after commit `793ee1f`
  - `Cloud Edit Deploy Preflight / Worker typecheck and dry run`: failed before runner steps with the GitHub billing/spending-limit annotation.
  - `Cloud Edit Deploy Preflight / Editing backend Python tests`: failed before runner steps with the same annotation.
  - `iOS Internal TestFlight Upload / No-secret internal staging codecheck`: failed before runner steps with the same annotation.

## Remaining Launch Blockers

- This improves scan confidence gating, but does not prove the overall 85% launch target. Submission still needs a launch-grade labeled footage report, real iPhone/TestFlight smoke, live staging Worker checks, and green GitHub Actions after the billing/spending-limit blocker is cleared.

# Phase Clip82 Analysis Team Diagnostics

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make selected-team analysis quality auditable from each cloud analysis result. The backend already keeps selected-team matches and uncertain clips for Review; this phase records how many matched, uncertain, opponent-filtered, defensive, block, and steal clips survived so internal launch testing can verify the product behavior without reading logs or exposing video/storage details.

## Changes

- Added team-selection counters to `CloudDiagnostics`:
  - `usedTeamQuickScan`
  - `preTeamFilterSegments`
  - `teamMatchedCandidateSegments`
  - `teamUncertainCandidateSegments`
  - `teamOpponentFilteredSegments`
  - `teamMatchedReviewSegments`
  - `teamUncertainReviewSegments`
  - `defensiveReviewSegments`
  - `blockReviewSegments`
  - `stealReviewSegments`
- Added backend diagnostics generation after quick scan and after selected-team trim.
- Added regression coverage proving selected-team analysis reports:
  - matched candidate/review clips
  - uncertain review clips
  - opponent clips filtered before Review
  - block and steal review coverage

## Architecture Guardrails

- Cloud backend owns the counters because it owns quick scan, team attribution, filtering, and review trim.
- No iOS analysis, rendering, composition, or export behavior changed.
- No full videos, presigned URLs, object keys, or secrets are added to diagnostics.
- The counters are aggregate metadata only and are safe for user-facing Review/launch evidence.

## Validation

Completed locally:

```bash
python3 -m py_compile ios/backend/app/models.py ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- Python compile passed for touched backend/test modules.
- Focused pipeline quality tests passed: 41 tests.
- iOS backend discovery passed: 166 tests.
- Scripts discovery passed: 57 tests.
- `git diff --check` passed.

Remote CI after push to `b9cb45a`:

- Cloud Edit Deploy Preflight: run `26560094018`, failed before useful logs were available (`log not found` for failed job `78240736462`).
- iOS Internal TestFlight Upload: run `26560093945`, failed before useful logs were available (`log not found` for failed job `78240736617`).
- PR #32 remained `UNSTABLE` from those remote checks.

## Remaining Proof

- These counters make the proof easier to inspect, but they are not a substitute for the labeled-footage 85% eval.
- Internal launch still needs a real cloud run with manual labels covering selected-team makes, misses, blocks, steals, forced turnovers, uncertain review clips, opponent clips, and bad timing negatives.
- GitHub Actions still need the provider/account-side runner failure cleared before remote CI can prove this branch.

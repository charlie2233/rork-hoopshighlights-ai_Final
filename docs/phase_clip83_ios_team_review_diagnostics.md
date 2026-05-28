# Phase Clip83 iOS Team Review Diagnostics

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make the cloud selected-team diagnostics visible in the iOS control surface after analysis. The backend now reports whether the team quick scan ran, how many clips matched the selected team, how many uncertain clips remain in Review, how many opponent clips were filtered, and how many defensive/block/steal clips survived. iOS should decode those aggregate counters and show them without doing analysis locally.

## Changes

- Extended iOS `CloudDiagnostics` to decode the backend team/uncertain/defense counters.
- Stored the latest cloud diagnostics on `VideoAnalysisService` when cloud analysis completes.
- Cleared stale cloud diagnostics when a new external or local analysis starts, or when a project/live state is restored.
- Added a compact Analysis Complete summary:
  - team-scan candidate count
  - selected-team and uncertain Review clip counts
  - opponent clips filtered before Review
  - defensive clips, including block and steal counts
- Extended the control-plane `CloudDiagnostics` TypeScript contract with the optional counters.

## Architecture Guardrails

- iOS remains a display/control surface only. It does not analyze video pixels, rank highlights, render, compose, or export production video.
- Diagnostics are aggregate counts only. No videos, frames, full presigned URLs, object keys, or secrets are displayed.
- Cloud backend remains the source of truth for quick scan, team attribution, filtering, and review trim.

## Validation

Completed locally:

```bash
git diff --check
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
cd services/control-plane && npm run typecheck
# XcodeBuildMCP: session_show_defaults, then build_sim
```

Results:

- `git diff --check` passed.
- Focused pipeline quality tests passed: 41 tests.
- iOS backend discovery passed: 166 tests.
- Scripts discovery passed: 57 tests.
- Control-plane TypeScript typecheck passed.
- XcodeBuildMCP iOS Simulator Debug build passed for scheme `HoopsClips` on `iPhone 17 Pro`.
- Build warnings were pre-existing `CloudAnalysisService.swift` warnings about `await` expressions with no async operations; no build errors.

## Remaining Proof

- This improves launch/user observability but does not prove the 85% labeled-footage target.
- Internal launch still needs real labeled-footage eval, live staging proof, and installed TestFlight smoke.

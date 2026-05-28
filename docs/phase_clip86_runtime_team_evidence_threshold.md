# Phase Clip86 Runtime Team Evidence Threshold

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Align runtime team quick-scan validation with the launch evaluator: a confident selected-team ownership decision should not survive from one frame or from confidence text alone.

## Change

- Added `TEAM_QUICK_SCAN_MIN_CONFIDENT_EVIDENCE_FRAME_REFS = 2`.
- Updated the GPT team quick-scan prompt/context so high-confidence clip ownership requires at least two cited sampled frames.
- Runtime validation now caps attribution confidence below `0.85` when fewer than two valid sampled frame refs are cited.
- Preserves the valid evidence refs even when confidence is capped, so the clip can stay uncertain/reviewable with audit metadata.
- Added regression coverage for one valid frame ref: confidence is capped below `0.85`, while the single valid ref is retained.

## Guardrails

- GPT still receives sampled frames only, never full videos.
- The backend still owns validation and selected-team filtering.
- Capped clips are not thrown away by this check; they remain eligible as uncertain review clips when selected-team filtering allows uncertain clips.
- Evidence refs are IDs only, not URLs, file paths, storage keys, or images.

## Validation

Fresh local run on 2026-05-28:

```bash
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m py_compile ios/backend/app/team_quick_scan.py ios/backend/tests/test_team_quick_scan.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- `py_compile`: passed
- `ios.backend.tests.test_team_quick_scan`: 27 passed
- backend discovery suite: 169 passed
- scripts discovery suite: 58 passed
- `git diff --check`: passed

## Remaining Proof

This makes the runtime confidence gate stricter, but it is not the real-footage 85% proof by itself. Internal launch still needs labeled footage that includes selected-team makes, misses, blocks, steals, forced turnovers, uncertain review clips, opponent highlights, and bad-window negatives.

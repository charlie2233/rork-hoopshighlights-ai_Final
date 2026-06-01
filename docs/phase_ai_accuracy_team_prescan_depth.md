# Phase AI Accuracy - Team Prescan Depth

Date: 2026-06-01
Branch: codex/phase-ai-accuracy-team-events

## Goal

Improve the real cloud AI path for team-aware highlight accuracy by giving the interactive team quick scan more sampled candidate evidence before the user chooses a team.

This phase deliberately avoids logo work and avoids any local iOS analysis/rendering. The backend remains responsible for analysis, GPT/team attribution, edit planning, rendering, and storage.

## Change

- Raised the interactive team prescan candidate cap from 64 to 96 clips.
- Raised rich per-candidate sampling from 32 to 64 candidates.
- Raised rich sampled role frames from 6 to 8 frames per candidate.
- Raised the bounded interactive clip-frame budget from 288 to 768 frames.
- Kept the full cloud quick scan cap at 320 candidates and 2,560 default clip frames.

## Accuracy Impact

The prescan now gives GPT/team attribution more chances to see:

- early possession setup
- release/action frames
- shot arc and rim result
- follow-through and finish context
- defensive actions like blocks, deflections, steals, and forced turnovers

This should reduce missed selected-team ownership and make uncertain clips more honestly reviewable instead of over-confidently excluded.

## Safety

- No full videos are sent to GPT.
- No FFmpeg commands are accepted from GPT.
- No storage credentials or presigned URLs are exposed.
- The change only adjusts bounded backend sampling defaults for the interactive cloud prescan.
- iOS remains a control/status surface.

## Validation

Commands run:

```bash
git diff --check
```

Result: passed.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v
```

Result: passed, 42 tests.

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
```

Result: passed, 57 tests.

Earlier simple command forms considered:

```bash
python3 -m unittest ios/backend/tests/test_team_quick_scan.py
PYTHONPATH=ios/backend:services/editing python3 -m unittest services/editing/tests/test_editing_service.py
```

## Remaining Accuracy Work

This does not replace the launch accuracy gate. We still need a real labeled footage bundle covering selected-team, all-teams, makes, misses, blocks, steals, forced turnovers, bad windows, and uncertain review cases before claiming the real 85 percent target.

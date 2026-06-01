# Phase Launch169 - GPT Defense Team Context

Branch: `codex/phase-launch169-gpt-defense-team-context`

## Goal

Improve HoopClips highlight accuracy by giving the cloud GPT editor clearer selected-team and defensive-play context. The change stays inside the backend GPT candidate payload. iOS remains the control surface only.

## Architecture Guardrails

- Cloud owns candidate analysis, GPT clip selection, edit planning, render validation, and rendering.
- iOS only uploads, reviews, configures export, shows status/preview, downloads, and shares.
- GPT receives existing candidate clips plus sampled keyframes only, never full videos.
- GPT is not allowed to generate FFmpeg commands, shell commands, file paths, storage keys, or signed URLs.

## Implemented

- Added per-clip `teamDefenseContext` to the GPT highlight reranker payload.
- Added the same context to GPT revision patch candidate clips.
- Context includes:
  - `candidateLane`
  - `defensiveFamily`
  - `defensiveEventLike`
  - `teamAttributionStatus`
  - `teamEvidenceStatus`
  - `renderEligibleForSelectedTeam`
  - `reviewOnlyUncertain`
  - `selectedTeamDefensiveHighlight`
  - `selectionGuidance`
- GPT instructions now explicitly tell the model to use `teamDefenseContext` when separating selected-team render candidates from review-only uncertain clips and opponent clips.

## Why This Helps Accuracy

- Blocks, steals, forced turnovers, and defensive stops are surfaced as first-class highlight candidates instead of being treated like generic non-scoring clips.
- Selected-team clips are labeled as render-ready, user-kept uncertain, or review-only uncertain before GPT judges them.
- Confident opponent clips remain excluded from selected-team GPT payloads.
- Uncertain team clips can still be reviewed by the user, but GPT is told not to auto-promote them into selected-team final edits unless the user kept them.

## Tests

- `python -m pytest services/editing/tests/test_gpt_reranker.py` failed because local `python` is not installed.
- `python3 -m pytest services/editing/tests/test_gpt_reranker.py` failed because this local Python does not have `pytest`.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 65 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v` passed: 124 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py` passed.
- `git diff --check` passed.

## Launch Notes

- No mobile runtime rendering was added.
- No local video analysis was added to iOS.
- No secrets, R2 credentials, full presigned URLs, or source object keys are included in the GPT payload.

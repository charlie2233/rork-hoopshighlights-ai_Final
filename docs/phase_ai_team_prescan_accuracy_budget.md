# Phase AI Team Prescan Accuracy Budget

Date: 2026-06-01
Branch: codex/phase-ai-team-prescan-depth

## Goal

Improve the app's real AI team-selection flow before analysis. The user should be able to import a video, let the cloud do a jersey-color/team scan, choose a team or All teams, and then send only that selected-team intent into cloud analysis/editing.

## Change

- Raised the interactive team quick-scan candidate cap from 96 to 160 clips.
- Raised rich per-candidate ownership sampling from 64 to 128 candidates.
- Raised the interactive clip-frame budget from 768 to 1,280 frames.
- Raised the quick-scan timeout ceiling/floor to 120 seconds so the deeper GPT vision pass has enough time.
- Kept the full cloud quick scan at the existing 320-candidate maximum for final analysis/editing.

## Accuracy Notes

This gives GPT more real sampled frame evidence before the user chooses a team:

- scoring setup, release, shot arc, rim result, and follow-through
- block challenge, ball deflection, defensive outcome, and recovery
- steal or forced-turnover possession change and follow-through
- more tail candidates that may not be top-score plays but can matter for selected-team accuracy

Uncertain clips remain reviewable instead of auto-rendered. Confident opponent clips are still filtered by backend team evidence rules.

## Architecture Safety

- No full videos are sent to GPT.
- iOS still only shows status, team choices, review, preview, and share controls.
- GPT still returns structured team/clip attribution only.
- Backend validators still own candidate filtering, team evidence, edit planning, and rendering.
- No secrets, storage credentials, or signed URLs are logged or documented.

## Validation Plan

- `git diff --check` - passed.
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v` - passed, 42 tests.
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v` - passed, 57 tests.
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v` - passed, 51 tests.
- `PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -v` - passed, 137 tests.

No GitHub Actions were run for this phase, to protect the Actions budget.

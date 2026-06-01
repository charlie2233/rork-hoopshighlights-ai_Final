# Phase: GPT Review Signal Context

## Goal

Improve GPT-led highlight accuracy by making the backend explicit about whether a candidate clip is allowed in the final render, should remain review-only, or should be rejected for the current team/template context.

## Architecture

- Cloud backend owns candidate analysis, GPT highlight selection, edit planning, revision patches, validation, rendering, and storage.
- iOS remains the control surface for import/upload, review, export controls, job status, preview, download, and share.
- GPT receives compact candidate contexts and sampled keyframes only.
- GPT does not receive full videos, source object keys, presigned URLs, or FFmpeg/render commands.

## Change

`teamDefenseContext` now includes explicit action fields:

- `finalEditAllowed`: true only when the backend considers the clip safe for final EditPlan/render use.
- `manualReviewRequired`: true for uncertain team clips or quality-review clips that should not auto-render.
- `allowedFinalEditAction`: `render`, `review_only`, or `reject`.
- `renderEligibilityReason`: stable reason such as `selected_team_match`, `needs_manual_team_review`, `opponent_team`, or `quality_context_incomplete`.

These fields are added alongside the existing `candidateLane`, `renderEligibleForSelectedTeam`, `reviewOnlyUncertain`, and defensive-event signals.

## Expected Behavior

- Evidence-backed selected-team clips can render.
- Confident opponent clips stay excluded before GPT for selected-team jobs.
- Uncertain selected-team clips stay visible to GPT/user review but cannot satisfy final-edit duration floors unless the user keeps them.
- Blocks, steals, forced turnovers, and defensive stops remain valid highlight candidates when the selected team evidence supports them.
- GPT revision patches are instructed to use only clips whose `teamDefenseContext.allowedFinalEditAction` is `render`.

## Validation

Completed local commands:

```bash
ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -v
PYTHONPATH=ios/backend ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v
git diff --check
```

Result:

- GPT reranker suite: 78 tests passed.
- Editing service suite: 137 tests passed, including local edit/render/revision/download-history/sanitization paths.
- Team quick-scan backend suite: 42 tests passed.
- `pytest` was unavailable in the local Python environments, so the suite was run with the standard `unittest` runner.

Config note:

- The broad editing-service test sweep surfaced stale assertions expecting `HOOPS_TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS=160` and a `120s` timeout. Current config, Cloud Build defaults, and backend tests use `320` candidates and `180s` for the higher-recall internal beta scan, so the service test now matches those launch defaults.

## Notes

This branch intentionally does not change iOS rendering behavior, does not add local video analysis, and does not change cloud deploy/secrets.

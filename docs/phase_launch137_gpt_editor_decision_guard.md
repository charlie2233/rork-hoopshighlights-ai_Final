# Phase Launch137: GPT Editor Decision Guard

## Goal

Improve cloud highlight quality by making the compact GPT editing context harder to misuse. GPT should act like the final semantic editor, but it must still obey backend clip IDs, team targeting, review gates, and deterministic render validators.

## Backend Change

`build_agent_editing_context(...)` now includes `decisionGuidance`:

- `allowedClipIds`: exact candidate IDs GPT may reference.
- `selectionContract`: prefer render-ready, quality-eligible clips; reject generic filler unless needed; preserve clear blocks, steals, forced turnovers, and defensive stops.
- `renderEligibilityPolicy`: explains which clips may enter the final plan and which are review-only or blocked.
- `teamTargetingPolicy`: tells GPT that uncertain selected-team clips can be shown for review but should not auto-render until the user keeps them.
- `safetyContract`: forbids full-video inputs, renderer commands, storage links, and timestamp authority changes.
- `outputMustOmit`: generic private-output classes that must never appear in GPT JSON.

The renderer path did not change. The backend still validates and repairs `EditPlan` / `EditPlanPatch` output before rendering.

## User Impact

- Better highlight selection accuracy without adding more UI choices.
- Team-specific edits should keep clear defensive highlights while avoiding accidental opponent/uncertain-team renders.
- Uncertain clips can still be surfaced for review instead of being silently dropped.

## Architecture Guardrails

- Cloud backend owns GPT selection and edit planning.
- iOS remains the upload/review/status/preview/share client.
- GPT receives compact candidate context only, not full videos.
- GPT cannot emit renderer commands or storage/private URL fields.
- FFmpeg/timestamp/render authority remains deterministic backend logic.

## Validation

- Focused backend test:
  - `cd ios/backend && .venv/bin/python -m unittest tests.test_edit_plan_agent -v`
  - Result: `102 tests`, `OK`
- Full backend unittest sweep:
  - `cd ios/backend && .venv/bin/python -m unittest discover tests -v`
  - Result: `212 tests`, `OK`
- Diff hygiene:
  - `git diff --check`
  - Result: clean

## Notes

- This phase is intentionally small: it tightens the GPT editor contract without touching iOS UI or cloud rendering behavior.
- The existing root untracked Xcode folders were preserved.

# Phase Clip30 GPT Underfill Backfill

Date: 2026-05-29
Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Improve GPT-led highlight quality without changing the cloud-first architecture. GPT remains the semantic editor, FFmpeg/CV/timestamps remain deterministic backend responsibilities, and iOS remains a control surface only.

## Change

- Added an underfilled-result guard after the first GPT highlight rerank pass.
- If GPT keeps too few usable clips relative to the available validated candidate pool, the backend extracts keyframes from the next best existing render-eligible candidates and sends one additional compact GPT request.
- The backfill pass sends candidate metadata and sampled keyframes only; it does not send full videos and does not accept FFmpeg commands.
- Merged GPT decisions still go through `apply_gpt_highlight_rerank`, sampled-frame-role validation, EditPlan validation, team filtering, duplicate cleanup, watermark/outro policy, and render safety.
- Selected-team GPT sampling now prioritizes renderable matched-team candidates, with only a small bounded lane for unreviewed uncertain clips. Uncertain clips remain visible for review, but they no longer consume too many final-edit GPT slots.

## Validation

Commands run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend \
  uv run --isolated --python 3.13 --with-requirements ios/backend/requirements.txt \
  python -m unittest services.editing.tests.test_gpt_reranker -v

# Result: passed. 59 tests.

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend \
  uv run --isolated --python 3.13 --with-requirements ios/backend/requirements.txt \
  python -m unittest \
    services.editing.tests.test_gpt_reranker \
    services.editing.tests.test_editing_service \
    ios.backend.tests.test_edit_plan_agent \
    -v

# Result: passed. 203 tests.
```

`python3 -m unittest services/editing/tests/test_gpt_reranker.py -v` was attempted first, but the system Python lacked backend dependencies such as `pydantic`; the successful backend tests used `uv run --isolated` with `ios/backend/requirements.txt`.

## Launch Notes

This clears the repo-side quality gap found in the backend GPT audit: GPT partial keeps now get a real keyframe-only backfill chance, and selected-team edits spend most GPT review capacity on renderable same-team clips. It does not clear provider/account blockers for internal TestFlight.

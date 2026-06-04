# Phase Clip2: temporal merge, longer source limits, GPT accuracy feed

Date: 2026-06-04
Branch: `codex/phase-clip1-gpt-led-highlight-editor`

## Goal

Remove redundant clips from similar timeframes before review/export, allow longer real-game source videos, and give the GPT highlight editor a cleaner candidate pool for better basketball judgment.

## What changed

- Raised default cloud analysis upload size from 500 MB to 2 GB.
- Raised default cloud analysis source duration from 30 minutes to 75 minutes.
- Raised the staging Worker `MAX_DURATION_SECONDS` override from 30 minutes to 75 minutes.
- Raised AI Edit plan source-window policy:
  - Free: 10 minutes to 30 minutes.
  - Pro: 30 minutes to 75 minutes.
  - Internal: 60 minutes to 75 minutes.
  - Dev remains 120 minutes.
- Added temporal duplicate merging in the backend analysis pipeline.
- Updated backend rejection messages to match the new defaults.
- Kept GPT as the semantic editor/director, but now it receives fewer repeated clips and stronger merged scores.

## Temporal merge behavior

The backend now collapses near-identical clips when either condition is true:

- The two windows overlap more than the existing hybrid dedupe threshold.
- The clip centers are within 1.25 seconds and the windows overlap at least 25%.

Instead of just dropping one duplicate, the backend now merges duplicate evidence:

- The merged clip keeps the best-quality label/action metadata.
- The merged window covers the shared play but stays inside the configured maximum clip duration.
- Scores are combined with a capped boost:

```text
merged_score = min(1.0, stronger_score + weaker_score * 0.22)
```

This means two detectors agreeing on the same play should make one stronger candidate, not two or three redundant review rows.

## GPT accuracy impact

The GPT highlight editor still works as the final basketball editor/director:

- CV/runtime creates the high-recall candidate pool.
- The temporal merge collapses duplicate timeframe evidence.
- GPT ranks and rejects from the cleaner candidate list.
- Backend validation still enforces timing, outcome sanity, team filtering, and render-safe limits.
- FFmpeg remains deterministic renderer only.

This should directly help the Troy-style failure mode where repeated nearby clips inflated review volume and made GPT/human review look worse than the actual unique-play count.

## Remaining evidence needed

- Rerun Troy white-team analysis with the new source video.
- Confirm repeated similar-timeframe clips collapse before the review page.
- Re-run the human accuracy check and preserve the labels.
- Collect one additional real-game case before claiming 85% launch-grade precision.

## Validation

Commands run:

```bash
git diff --check
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_pipeline_quality.py -v
npm --prefix services/control-plane test
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_edit_plan_agent.py -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios/backend/tests/test_launch_guardrails.py -v
```

Results:

- `git diff --check`: passed.
- `test_pipeline_quality.py`: passed, 84 tests.
- `services/control-plane` tests: passed, 33 tests.
- `test_edit_plan_agent.py`: passed, 111 tests.
- `test_launch_guardrails.py`: passed, 3 tests.

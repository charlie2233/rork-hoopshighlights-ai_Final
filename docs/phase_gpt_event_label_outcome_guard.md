# Phase GPT Event Label Outcome Guard

Branch: `codex/phase-gpt-event-label-outcome-guard`

## Goal

Keep GPT-led highlight editing accurate in the user-facing Review, AI Work Receipt, and EditPlan surfaces by making visible event labels obey the validated outcome. GPT can still propose semantic basketball events, but once the backend validator accepts an outcome like `steal`, `blocked`, or `missed`, the final label cannot contradict that outcome.

## Change

- Added outcome-safe default labels for validated GPT outcomes:
  - `made` -> `Made Shot`
  - `missed` -> `Missed Shot`
  - `blocked` -> `Block`
  - `steal` -> `Steal`
  - `forced_turnover` -> `Forced Turnover`
  - `defensive_stop` -> `Defensive Stop`
- Replaced the old raw suffix style such as `Steal (steal)` and `Made Shot (made)` with clean product labels.
- Added event-label conflict detection so a validated steal cannot surface as `Made Shot`.
- Kept non-conflicting defensive phrasing such as `Made him miss`.

## Architecture

- Cloud/backend still owns GPT selection, outcome validation, edit planning, and render safety.
- iOS behavior is unchanged; it only displays backend labels/status/preview/share controls.
- GPT still cannot generate FFmpeg commands, replace deterministic render logic, or bypass validators.
- This does not send any new data to GPT and does not change keyframe extraction, CV analysis, storage, or rendering.

## Tests

Focused coverage added for:

- GPT event label conflicts with validated outcome.
- Clean made-shot labels without raw outcome suffixes.
- Defensive labels that include safe natural phrasing.
- Existing defensive outcome test updated from raw suffix copy to clean label copy.

## Validation

Local validation completed on June 2, 2026, without using GitHub Actions:

```bash
uv venv /tmp/hoopclips-codex-venv --python /Users/hanfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
uv pip install --python /tmp/hoopclips-codex-venv/bin/python -r ios/backend/requirements.txt pytest
/tmp/hoopclips-codex-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_event_label_sanitizer_replaces_label_that_conflicts_with_outcome services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_event_label_sanitizer_does_not_append_raw_outcome_suffix services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_event_label_sanitizer_keeps_non_conflicting_defensive_label services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_caption_sanitizer_replaces_plan_caption_that_conflicts_with_outcome services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_caption_sanitizer_keeps_non_conflicting_defensive_caption -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-codex-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_keeps_mixed_steal_finish_as_defensive_outcome -v
/tmp/hoopclips-codex-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-codex-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-codex-venv/bin/python -m unittest services.editing.tests.test_editing_service -v
/tmp/hoopclips-codex-venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py
git diff --check
```

Results:

- Focused event/caption guard tests: 5 passed.
- Focused mixed steal defensive outcome test: passed.
- `services.editing.tests.test_gpt_reranker`: 104 passed.
- `ios.backend.tests.test_edit_plan_agent`: 110 passed.
- `services.editing.tests.test_editing_service`: 57 passed.
- `py_compile`: passed.
- `git diff --check`: passed.

## Launch Notes

This is a product-quality guard, not a full launch proof. Internal TestFlight still needs the installed-device smoke across import/upload, team choice, cloud analysis, Review, AI Edit render, preview, revision, and share/open-in.

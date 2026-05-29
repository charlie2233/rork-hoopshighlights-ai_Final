# Phase Clip79 Native Outcome Evidence Source

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Improve GPT-led highlight editing accuracy by making shot-outcome evidence explicit. Plain labels such as `Made Shot` or `Bucket` are now carried as useful but lower-reliability `label_only` hints, while defensive clips such as blocks and steals carry `defensive_event` evidence. This helps GPT and deterministic fallback logic avoid overclaiming makes while still preserving uncertain highlights for user review.

## Architecture

- Cloud analysis attaches compact native shot metadata to candidate clips.
- Cloud edit planning re-derives timing/context bounds and only treats incoming outcome metadata as hints.
- GPT receives compact candidate metadata and sampled keyframes only; no full videos, storage keys, presigned URLs, local paths, or FFmpeg commands are sent.
- iOS only decodes and forwards optional cloud metadata for review/edit requests. It does not analyze, compose, render, or export video locally.

## Schema Additions

`nativeShotSignals` now includes:

```json
{
  "outcomeEvidenceSource": "label_only",
  "outcomeReliabilityScore": 0.57
}
```

Allowed `outcomeEvidenceSource` values:

- `label_only`
- `native_shot_signals`
- `defensive_event`
- `gpt_shot_tracking`
- `gpt_defensive_tracking`
- `non_shot`
- `uncertain`
- `not_shot`

`outcomeReliabilityScore` is clamped from `0.0` to `1.0`.

## Behavior

- Explicit scoring labels (`Made Shot`, `Bucket`, `Basket`, `Dunk`) stay eligible, but are marked `label_only` with reliability capped at `0.68`.
- Ambiguous labels (`Layup`, `Finish`, `Attempt`) stay `uncertain` with reliability `0.35`.
- Blocks are marked `blocked` with `defensive_event` evidence when the defensive context is present.
- Steals and other non-shot defensive clips are marked `not_shot` with `defensive_event` evidence and high reliability.
- Accepted GPT decisions now stamp retained clips with `gpt_shot_tracking` or `gpt_defensive_tracking` evidence after the structured output passes deterministic validation.
- The AI Work Receipt counts selected clips with trusted shot/rim evidence, selected shot outcomes that still need review, and selected label-only shot outcomes.
- Control-plane callbacks preserve the new metadata without exposing storage internals.
- Swift cloud-analysis types decode the new optional fields without changing iOS ownership of the pipeline.

## Validation

Completed locally:

```bash
python3 -m py_compile ios/backend/app/models.py ios/backend/app/pipeline.py ios/backend/app/editing.py services/editing/editing_app/models.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_uses_existing_clip_ids_only services.editing.tests.test_editing_service.EditingServiceTests.test_ai_work_receipt_summarizes_validated_shot_outcome_evidence services.editing.tests.test_editing_service.EditingServiceTests.test_ai_work_receipt_flags_selected_timing_context_issues -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
npm --prefix services/control-plane test -- --runInBand
npm --prefix services/control-plane run typecheck
# Build iOS Apps MCP:
# session_show_defaults
# build_sim -skipPackagePluginValidation -skipMacroValidation
```

Results:

- Python compile passed.
- Focused GPT evidence/receipt tests passed: 3 tests.
- Focused backend/GPT suite passed: 173 tests.
- iOS backend discovery passed: 165 tests.
- Editing-service discovery passed: 94 tests, including local render exercises.
- Scripts discovery passed: 57 tests.
- Control-plane suite passed: 28 tests.
- Control-plane typecheck passed.
- iOS Debug simulator build passed. Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-28T06-41-08-453Z_pid97875_5518f45e.log`.

## Launch Notes

- This improves GPT/editor inputs and fallback ranking, but it does not claim launch readiness by itself.
- Remaining launch proof still requires live staging deploy, real labeled-footage accuracy evaluation, installed TestFlight smoke, and App Store/TestFlight submission checks.
- Post-push GitHub checks for commit `c267fbc` did not start any runner steps. The check-run annotations report: `The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings`.

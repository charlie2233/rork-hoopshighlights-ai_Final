# Phase Clip25 Ambiguous Shot Outcome Hints

## Goal

Improve HoopClips highlight quality by reducing native/GPT outcome overclaims for ambiguous basketball labels.

Generic labels such as `Layup` and `Tough Finish` should remain shot-like highlight candidates, but they should not be treated as made baskets unless the label or later validated evidence explicitly supports a make. This keeps GPT-led editing closer to a shot-tracker model: visible setup, release, ball path, rim/result, and follow-through matter more than optimistic labels.

## Architecture

- Cloud backend owns analysis, outcome hints, GPT clip selection, edit planning, validation, rendering, and storage.
- iOS behavior is unchanged.
- No full videos are sent to GPT.
- GPT still receives compact candidate metadata and sampled keyframes only.
- GPT cannot generate FFmpeg commands or bypass validators.

## Change

Updated the duplicated native outcome hint logic in:

- `ios/backend/app/pipeline.py`
- `ios/backend/app/editing.py`

Outcome hint behavior:

- `Made Shot`, `Bucket`, `Basket`, and `Dunk` still produce `outcome=made`.
- `Miss` / `Missed` still produce `outcome=missed`.
- `Block` / `Blocked` still produce `outcome=blocked`.
- Ambiguous `Layup` and `Finish` labels now produce `outcome=uncertain`.

The clip can still be selected if it has complete context and strong visual/story quality. The change only prevents the backend from claiming the ball went in before explicit evidence exists.

## Red Evidence

```text
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_outcome_hints_do_not_treat_ambiguous_finishes_as_makes ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_outcome_hints_keep_explicit_made_labels -v

FAIL: 'made' != 'uncertain'
```

```text
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_native_shot_signals_do_not_treat_ambiguous_finish_labels_as_made services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_does_not_treat_ambiguous_layup_label_as_made -v

FAIL: 'made' != 'uncertain'
```

## Green Focused Evidence

```text
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_outcome_hints_do_not_treat_ambiguous_finishes_as_makes ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_outcome_hints_keep_explicit_made_labels -v

Ran 2 tests in 0.000s
OK
```

```text
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_native_shot_signals_do_not_treat_ambiguous_finish_labels_as_made services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_does_not_treat_ambiguous_layup_label_as_made -v

Ran 2 tests in 0.002s
OK
```

## Broad Validation

```text
python3 -m py_compile ios/backend/app/pipeline.py ios/backend/app/editing.py ios/backend/tests/test_pipeline_quality.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py
OK

PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
Ran 101 tests in 6.080s
OK

PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
Ran 76 tests in 22.153s
OK

python3 -m unittest discover -s scripts -p 'test_*.py' -v
Ran 34 tests in 0.196s
OK

git diff --check
OK
```

## Launch Notes

This is backend-only quality work. It does not change iOS local behavior, live render execution, storage, secrets, Worker routing, or policy gates.

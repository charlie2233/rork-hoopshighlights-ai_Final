# Phase Clip24 Result-Anchored Keyframes

## Goal

Improve GPT-led highlight selection by aligning sampled shot-tracking keyframes with the native analysis meaning of `eventCenter`.

Native analysis now prefers the rim/result moment over the release spike for shot events. GPT sampling must therefore treat `eventCenter` as the rim/result anchor, so it sees release and shot-arc frames before `eventCenter`, rim approach at or just before `eventCenter`, and rim entry/follow-through immediately after `eventCenter`.

## Architecture

- Cloud backend owns analysis, GPT clip selection, edit planning, validation, rendering, and storage.
- iOS behavior is unchanged.
- No full videos are sent to GPT.
- GPT still receives sampled candidate keyframes only.
- GPT still cannot generate FFmpeg commands or bypass validators.
- Renderer behavior is unchanged and deterministic.

## Change

`services/editing/editing_app/gpt_reranker.py` now samples shot-context frames relative to `eventCenter` as a rim/result anchor:

- `preEvent`, `release`, `shotArcEarly`, and `shotArcLate` are before `eventCenter`.
- `rimApproach` is at or just before `eventCenter`.
- `rimEntry` is within roughly 0.2 seconds after `eventCenter`.
- `belowRim` and `postOutcome` are follow-through frames after rim entry.

This prevents GPT from receiving late aftermath frames labeled as rim-entry evidence when native analysis already centered the clip on the basket result.

## Tests

Added and updated GPT reranker tests:

- `test_pro_sampling_adds_shot_setup_and_rim_entry_path_roles`
- `test_shot_sampling_treats_event_center_as_rim_result_anchor`

Red test evidence:

```text
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_pro_sampling_adds_shot_setup_and_rim_entry_path_roles -v

FAIL: 3.2 not less than 3.0
```

Green focused evidence:

```text
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_pro_sampling_adds_shot_setup_and_rim_entry_path_roles services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_shot_sampling_treats_event_center_as_rim_result_anchor -v

Ran 2 tests in 0.002s
OK
```

Broad validation:

```text
python3 -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py

PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
Ran 75 tests in 21.879s
OK

PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
Ran 98 tests in 5.858s
OK

python3 -m unittest discover -s scripts -p 'test_*.py' -v
Ran 34 tests in 0.191s
OK

git diff --check
OK
```

## Launch Notes

This is backend-only GPT handoff quality work. It improves the semantic quality of keyframes GPT uses for shot validation without changing live render paths, iOS export behavior, secrets, storage, or Worker deployment config.

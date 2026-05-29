# Phase Clip123: Receipt Defensive Classifier Parity

## Goal

Keep the AI Work Receipt honest about defensive highlights. The receipt should not count ordinary offensive clips as defense just because the label contains a word like `stop`.

## What Changed

- Receipt defensive counts now use the same defensive-event classifier as edit planning.
- GPT defensive outcomes still count as defensive when GPT validated `blocked`, `steal`, `forced_turnover`, or `defensive_stop`.
- A `Stop and Pop Jumper` selected clip no longer increments `defensiveSelectedClipCount`.

## Why This Matters

The launch goal asks for blocks and steals to be real highlights, not inflated audit rows. Internal testers and the iOS AI Work Receipt need accurate proof of what the cloud editor selected. False defensive counts can hide a scoring-only reel or make a non-defensive shot look like defensive recall.

## Validation

- Red check before implementation:
  - `test_ai_work_receipt_does_not_count_stop_and_pop_jumper_as_defense` failed with `defensiveSelectedClipCount == 1`.
- Green focused checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_ai_work_receipt_does_not_count_stop_and_pop_jumper_as_defense services.editing.tests.test_editing_service.EditingServiceTests.test_gpt_highlight_rerank_summary_feeds_render_receipt ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_defensive_event_classifier_ignores_stop_and_pop_shot_label -v`
- Broader backend checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/models.py services/editing/tests/test_editing_service.py ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py`
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker -v`
  - Result: 194 tests passed.
- Script checks:
  - `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Result: 78 tests passed.
- Whitespace:
  - `git diff --check`
  - Result: passed.

## Launch Notes

This improves receipt accuracy only. It does not prove the 85% target. Internal launch still needs a real cloud-path labeled accuracy report, live staging proof, installed TestFlight smoke, and current CI proof.

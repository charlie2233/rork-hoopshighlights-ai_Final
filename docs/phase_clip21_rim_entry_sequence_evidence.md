# Phase Clip21 Rim Entry Sequence Evidence

## Goal

Make GPT-led highlight selection stricter about made baskets. A made-shot clip should not pass because GPT sees a late rim frame, a net reaction, or a label. It must describe a visible rim-entry sequence: ball approach, ball at/entering the rim, and ball below the rim or visible net/rim aftermath.

## Change

- Added rim-entry sequence fields to `shotResultEvidence`:
  - `rimEntrySequence`
  - `ballApproachFrameRole`
  - `rimEntryFrameRole`
  - `ballBelowRimOrNetFrameRole`
  - `rimEntrySequenceConfidence`
- Updated the strict GPT Structured Outputs schema so the fields are required.
- Added prompt/context rules telling GPT that made shots require `rimEntrySequence=visible_entry`.
- Backend validation now rejects made-shot decisions when:
  - rim entry is not visible
  - rim-entry confidence is too low
  - approach, rim-entry, or follow-through frame roles are missing or unsupported
  - cited rim-entry roles were not actually sampled
  - richer sampled result frames are available but GPT cites only generic proof

## Architecture

- Cloud backend owns GPT selection, validation, EditPlan generation, rendering, storage, and policy.
- GPT receives only existing candidate clip metadata plus sampled JPEG keyframes.
- GPT does not receive full videos, source URLs, storage keys, presigned URLs, local paths, FFmpeg commands, or exact timestamp authority.
- iOS remains a control/status/preview/share surface and is unchanged in this phase.

## Quality Rationale

This moves HoopClips closer to a real basketball shot tracker. The model must now describe the actual made-basket sequence instead of using broad outcome language. That directly targets bad outputs such as:

- 0.1 second or tiny clips
- clips that start right before the basket
- late-rim aftermath clips
- labels that claim a make without the ball visibly entering
- generic `finish` evidence when richer rim/result frames exist

Cost is intentionally secondary for internal quality: the expensive GPT path should use the available visual evidence to make better editing decisions.

## Validation Evidence

- Syntax and whitespace:
  - `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py services/editing/tests/test_editing_service.py`
  - `git diff --check`
  - Result: passed.
- Focused rim-entry sequence tests:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_made_shot_without_rim_entry_sequence services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_decision_without_rim_entry_sequence_is_rejected services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment -v`
  - Result: 3 tests passed.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 33 tests passed.
- Backend edit-plan agent suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 57 tests passed.
- Backend discovery:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 95 tests passed.
- Editing-service discovery:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 73 tests passed.

## Launch Notes

- Existing GPT/editor kill switches and deterministic fallbacks still apply.
- This is backend-only quality hardening and does not enable public cloud cutover.
- Live staging proof still depends on deploy credentials, current Worker deployment, and installed TestFlight smoke evidence.

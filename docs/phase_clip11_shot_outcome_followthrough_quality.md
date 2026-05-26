# Phase Clip11 Shot Outcome Follow-Through Quality

## Goal

Improve HoopClips cloud clip selection when provider labels and native shot signals disagree. The backend should avoid turning uncertain or non-shot moments into made-basket edits, while still allowing GPT to judge complete, visible shot attempts from sampled keyframes.

## Change

- Preserved incoming native `uncertain` and `not_shot` outcomes instead of letting a provider `Made Shot` label overwrite them.
- Rejected shot-like candidates from fallback planning and GPT sampling when native signals classify the moment as `not_shot`.
- Kept uncertain but otherwise valid shot candidates eligible, while captioning provider-overclaimed made shots as `GOOD LOOK` instead of `BUCKET`.
- Fixed deterministic fallback captions for `Blocked Shot`, which now use `LOCKDOWN` instead of being caught by the generic `shot -> BUCKET` rule.

## Quality Rationale

The product goal is not just to find motion near a basket; HoopClips should behave more like a strong basketball editor. A provider can overlabel a moment as `Made Shot`, but if the native analysis says the outcome is uncertain or not actually a shot, the cloud edit planner should not promote that clip as a bucket. GPT can still review sampled keyframes for uncertain complete attempts, but the compact context must truthfully represent the native outcome.

## Validation Evidence

- Red tests before implementation:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_trusts_native_uncertain_outcome_over_provider_made_label ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_captions_blocked_shot_as_lockdown_not_bucket -v`
  - Result before code change: failed because native `uncertain` became `made`, and `Blocked Shot` captioned as `BUCKET`.
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_preserves_native_uncertain_outcome_over_provider_made_label -v`
  - Result before code change: failed because GPT payload advertised the provider-overclaimed clip as native `made`.
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_deterministic_plan_rejects_provider_shot_when_native_says_not_shot -v`
  - Result before code change: failed because native `not_shot` provider-overclaimed clips were still plan-quality eligible.
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_quality_filter_excludes_native_not_shot_overclaimed_provider_clip -v`
  - Result before code change: failed because GPT sampling still included the native `not_shot` provider-overclaimed clip.
- Green focused tests after implementation:
  - Same commands.
  - Result: passed.
- Focused suites:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 54 tests passed.
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 28 tests passed.
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Result: 17 tests passed.
- Full backend and editing service suites:
  - `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -v`
  - Result: 91 tests passed.
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 68 tests passed.
- Hygiene:
  - `python3 -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py`
  - `git diff --check`
  - Result: passed.

## Launch Notes

- No iOS code changed.
- No video rendering, FFmpeg command generation, storage, or presigned URL behavior changed.
- This strengthens both the non-GPT fallback planner and the GPT-led editor input payload without sending full videos to GPT.

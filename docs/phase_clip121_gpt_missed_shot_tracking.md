# Phase Clip121: GPT Missed Shot Tracking

## Goal

Tighten GPT-led highlight selection for missed shots so HoopClips behaves more like a shot tracker. A kept missed-shot clip must prove a visible miss sequence, not only claim `clear_miss`.

## What Changed

- GPT validator now rejects kept missed shots unless:
  - `rimResultEvidence` is `clear_miss`
  - `rimEntrySequence` is `visible_miss`
  - miss-sequence confidence is at least `0.65`
  - ball approach and rim/result frame roles are valid sampled shot roles
- GPT payload instructions now include explicit missed-shot tracking rules.
- A valid visible miss does not require `ballEntersRimFrameRole`; that remains made-shot-specific.

## Why This Matters

Made and missed outcomes are different failure modes. A late rim-only clip or label-only "miss" can still look plausible to GPT while being useless for the user. This phase makes the final GPT editor prove release-to-rim-to-result evidence for misses and keeps weaker outcomes out of final renders.

## Validation

- Red check before implementation:
  - `test_gpt_highlight_rerank_rejects_missed_shot_without_visible_miss_sequence` failed because the clip was kept even with `rimEntrySequence=unclear`.
- Green focused checks:
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_missed_shot_without_visible_miss_sequence ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_accepts_visible_miss_without_ball_entry_frame ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_missed_shot_without_ball_path ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_outcome_conflicting_with_native_shot_signal -v`
  - `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment -v`

## Launch Notes

This improves GPT edit validation and prompt guidance only. It does not claim the 85% target by itself. Submission still needs the real labeled-footage accuracy report and TestFlight/cloud smoke evidence.

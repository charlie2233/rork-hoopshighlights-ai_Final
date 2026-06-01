# Phase Clip2 - Crowd Pop Audio Salience

## Goal

Use loud crowd/audio pops as a high-recall highlight signal without letting audio alone become proof of a basketball highlight.

## Architecture

- Cloud/backend owns audio salience, candidate recall, GPT review context, edit planning, rendering, and storage.
- iOS remains a control surface for import/upload, team choice, Review, Export status, preview, download, and share.
- Full videos are not sent to GPT. Audio-pop candidates only affect candidate selection and compact GPT context.
- GPT still must validate sampled keyframes and cannot generate FFmpeg commands or bypass EditPlan validators.

## Changes

- Added unlabeled loud-audio-pop recognition for generic candidate labels such as `Highlight`.
- Reserved those unlabeled loud-pop candidates in the analysis Review pool when ordinary scoring clips would fill the cap.
- Passed an explicit `audioReactionSource` into GPT quality hints and agent candidate context.
- Kept the existing guardrail: weak generic audio-only filler is not an audio reaction candidate and does not become render-eligible by sound alone.
- Preserved existing explicit `Crowd Reaction` and `Audio Pop` behavior.

## Accuracy Notes

- Loud crowd pops are treated as recall hints near likely highlights.
- Audio-only confidence is not final outcome proof.
- GPT receives before/after reaction keyframes and must confirm visible basketball action, clear outcome, and watchability.
- If the visual evidence is weak, the candidate remains rejectable or review-only instead of being auto-rendered.

## Validation

Initial command attempt:

```bash
python3 -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_review_trim_reserves_unlabeled_loud_crowd_pop_candidate ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_unlabeled_audio_only_filler_is_not_audio_reaction_candidate services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_sampling_reserves_unlabeled_loud_audio_pop_for_review services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_audio_reaction_detection_ignores_weak_audio_only_filler
```

Result: failed before test execution because system Python lacked repo path/dependencies (`app`, `pydantic`).

Successful focused validation:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_review_trim_reserves_unlabeled_loud_crowd_pop_candidate ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_unlabeled_audio_only_filler_is_not_audio_reaction_candidate services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_sampling_reserves_unlabeled_loud_audio_pop_for_review services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_audio_reaction_detection_ignores_weak_audio_only_filler -v
```

Result: passed, 4 tests.

Successful affected-suite validation:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality services.editing.tests.test_gpt_reranker -v
```

Result: passed, 149 tests.

Successful validator guardrail validation:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_generic_audio_only_scoring_claim ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_crowd_reaction_outcome_claims_without_sampled_visual_support -v
```

Result: passed, 2 tests.

Successful broader edit-plan validation:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v
```

Result: passed, 108 tests.

Successful syntax and whitespace validation:

```bash
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py
git diff --check
```

Result: passed.

## Launch Recommendation

Keep this enabled for internal beta. It improves recall for loud gyms and crowd reactions while preserving the validator rule that visual evidence decides final highlight quality.

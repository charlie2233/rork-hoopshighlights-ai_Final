# Phase Clip102 Audio Team Accuracy Polish

## Goal

Improve highlight recall for moments where a super-loud crowd/audio reaction points to nearby basketball action, especially when the first-pass label or confidence is weak.

## Architecture Guardrails

- Cloud backend owns audio cue interpretation, GPT candidate review, edit planning, and render validation.
- iOS remains a control surface for upload, review, status, preview, download, and share.
- Full videos are not sent to GPT. GPT receives compact clip metadata plus sampled keyframes only.
- GPT cannot generate renderer commands or bypass deterministic EditPlan validators.

## Changes

- Added a bounded GPT review-only lane for audio reaction candidates that are not normal plan-quality eligible but have:
  - strong audio-reaction salience,
  - real motion/watchability/excitement context,
  - a valid timing window around the reaction,
  - no steady-noise cue classification.
- Added `planQualityEligible` and `gptReviewOnlyAudioReactionCandidate` to GPT quality hints so receipts and prompts distinguish final-plan candidates from recall-only audio clues.
- Extended selected-team sampling so uncertain selected-team audio reaction clips can still reach GPT/user review when `includeUncertain` is enabled.
- Kept final render safety unchanged: non-quality clips still cannot render unless validators accept the visual evidence and normal planning constraints.

## Validation

- Passed: targeted GPT reranker tests for:
  - super-loud audio review candidate below normal plan quality,
  - selected-team uncertain audio review candidate.
- Passed: `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - 95 tests passed.
- Passed: `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py ios/backend/app/editing.py ios/backend/app/pipeline.py`
- Passed: `git diff --check`.

## Launch Notes

- This helps recall for crowd-pop moments without claiming audio alone is a highlight.
- It does not prove the 85% selected-team target by itself; that still needs labeled real-footage evaluation with makes, misses, blocks, steals, uncertain team clips, and opponent negatives.

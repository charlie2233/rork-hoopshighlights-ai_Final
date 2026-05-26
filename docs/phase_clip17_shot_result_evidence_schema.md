# Phase Clip17 Shot Result Evidence Schema

## Goal

Make GPT-led highlight editing stricter about shot outcomes. A kept made, missed, or blocked clip now needs explicit result evidence from the sampled keyframes instead of relying on labels, motion spikes, or a late view of the rim.

## Change

- Added `shotResultEvidence` to every GPT highlight decision:
  - `releaseToRimContinuity`: `continuous`, `partial`, or `missing`
  - `rimResultEvidence`: `made_visible`, `clear_miss`, `blocked`, or `unclear`
  - `outcomeConfidence`: `0.0...1.0`
  - `reason`: compact natural-language evidence note
- Updated the strict OpenAI Structured Outputs schema so `shotResultEvidence` is required for every decision.
- Added prompt rules that tell GPT a made outcome requires `rimResultEvidence=made_visible` with confident rim/net proof.
- Added backend fail-closed validation:
  - made clips require visible made result evidence and confidence >= `0.72`
  - missed clips require clear miss evidence and confidence >= `0.65`
  - blocked clips require blocked evidence and confidence >= `0.65`
  - made/missed clips cannot have missing release-to-rim continuity
- Preserved deterministic rendering and exact timestamp ownership in the backend.

## Architecture

- GPT still receives only sampled JPEG keyframes from existing candidate clip windows.
- GPT does not receive full videos, source URLs, storage keys, presigned URLs, or FFmpeg commands.
- GPT can judge visible shot evidence, captions, story role, ordering, crop focus, and slow-motion suggestions.
- The backend validates GPT output before it can affect the deterministic EditPlan.
- Missing `shotResultEvidence` defaults to unclear/missing evidence in backend models so legacy or malformed responses fail closed for kept shot outcomes.
- Renderer behavior is unchanged.

## Quality Rationale

The previous schema asked GPT for broad quality booleans such as visible setup, event, arc, ball path, and rim/result. That helped, but a model could still keep a clip as `made` while describing weak or guessed outcome evidence. This phase forces the model to separately state whether the release-to-rim sequence is continuous and what kind of rim result it actually sees.

This moves GPT closer to a semantic shot tracker plus editor:

- reject late basket-only aftermath
- reject unclear rim outcomes
- reject guessed made-shot labels
- keep clips where the shot story is visible from setup through result
- preserve backend/CV ownership of exact timestamps and render execution

## Validation Evidence

- Focused GPT schema tests:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_requires_shot_quality_signals_and_context_judgment services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_schema_matches_highlight_decision_contract -v`
  - Result: 2 tests passed.
- Focused backend validation test:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_kept_clips_without_full_shot_context -v`
  - Result: 1 test passed.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 30 tests passed.
- Backend edit-plan agent suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 54 tests passed.
- Backend suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 92 tests passed.
- Editing service suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 70 tests passed.

## Launch Notes

- This is a quality hardening change for the GPT-led editing path, not a public launch gate flip.
- Existing GPT kill switches and deterministic fallback still apply.
- This branch does not prove live TestFlight, Cloudflare deploy-token creation, or staging render readiness.
- When Cloudflare token setup resumes, use a scoped token with account/zone selection and explicit TTL dates; do not paste or log token values in docs, tests, or chat.

# Phase Clip19 Validate GPT Cited Frame Roles

## Goal

Close the loophole where GPT could keep a made or missed shot by citing semantic frame roles that were not actually sampled for that clip. GPT should behave like a cautious final highlight editor: it can judge sampled visual evidence, but it cannot invent release, arc, rim, or result frames that the backend never sent.

## Change

- The editing service now passes sampled frame roles per clip into the backend GPT rerank validator.
- `apply_gpt_highlight_rerank` accepts `sampled_frame_roles_by_clip`.
- The backend rejects kept made/missed decisions when `shotTrackingEvidence` cites any unsampled role in:
  - `ballVisibleFrameRoles`
  - `rimVisibleFrameRoles`
  - `releaseFrameRole`
  - `resultFrameRole`
  - `ballEntersRimFrameRole`
- The validator reports `gpt_cited_unsampled_frame_role` in the AI work receipt summary.
- Test helpers now default to base-frame-safe tracking roles so tests only claim the richer arc/rim roles when those roles are explicitly sampled.

## Architecture

- GPT still receives only existing candidate clips and sampled JPEG keyframes.
- GPT does not receive full videos, source URLs, storage keys, presigned URLs, local paths, or FFmpeg commands.
- GPT can describe shot tracking evidence, captions, story roles, crop focus, and slow-motion suggestions.
- Backend validation decides whether GPT decisions can feed deterministic `EditPlan` generation.
- FFmpeg extraction, CV/runtime candidate generation, exact timestamps, deterministic rendering, storage, and policy checks remain cloud-backend owned.

## Quality Rationale

Earlier phases made GPT prove release, ball path, rim result, entry/reaction, and outcome. This phase binds that proof to the actual sampled frame sequence. If Free sampling only includes `start`, `eventCenter`, and `finish`, GPT can no longer cite `shotArcEarly`, `rim`, or `postOutcome` unless those frame roles were truly included in the payload.

That makes false makes less likely and prevents a model from using template knowledge or basketball priors as a substitute for visible sampled evidence.

## Validation Evidence

- Focused frame-role validation tests:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_tracking_roles_that_were_not_sampled services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_gpt_decision_citing_unsampled_frame_roles_is_rejected services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_incomplete_keyframes_drop_bad_candidate_without_losing_complete_candidates -v`
  - Result: 3 tests passed.
- GPT reranker suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v`
  - Result: 31 tests passed.
- Backend edit-plan agent suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v`
  - Result: 55 tests passed.
- Backend discovery suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v`
  - Result: 93 tests passed.
- Editing service discovery suite:
  - `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Result: 71 tests passed.

## Launch Notes

- Existing GPT kill switches and deterministic fallbacks still apply.
- This does not enable public cloud cutover, TestFlight submission, or production rendering by itself.
- Live staging proof still requires current deploy credentials, a deployed Worker/editing service, and post-install TestFlight smoke evidence.

# Phase Clip90 Team Evidence Context

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make GPT-led selection and revision prompts understand why a selected-team candidate is matched, uncertain, or weakly evidenced. Raw team confidence alone can be misleading when legacy or partial quick-scan metadata is present, so the compact GPT context should include an explicit evidence-quality summary.

## Change

- Added `team_evidence_summary()` in the backend edit model.
- Added `teamEvidence` to:
  - agent template editing context candidate clips
  - GPT highlight reranker compact clip payloads
  - GPT revision patch candidate payloads
- `teamEvidence` includes:
  - `status`
  - `evidenceBacked`
  - `frameRefCount`
  - `roleGroupCount`
  - `requiresEvidence`
  - `reasons`
- Weak quick-scan evidence remains reviewable when `includeUncertain=true`, but GPT sees why it should not treat the clip as a confident selected-team match.
- GPT highlight rerank and revision patch prompts now say `teamEvidence` is authoritative for selected-team confidence. Raw `teamAttribution.confidence` cannot promote weak or missing evidence to a confident match, evidence-backed confident opponent clips must be excluded, and weak/uncertain clips are review-worthy only when the play itself is strong.

## Guardrails

- The summary contains counts and reason codes only; it does not contain images, URLs, storage keys, or secrets.
- iOS still only relays metadata and user selection.
- GPT still receives sampled keyframes and compact candidate metadata, not full video.
- Renderer behavior is unchanged and remains deterministic.
- GPT still cannot generate FFmpeg commands, render instructions, file paths, URLs, storage keys, or full-video references.

## Validation

- `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py` passed.
- `PYTHONPATH=services/editing:ios/backend /tmp/hoopclips-py312-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_includes_team_targeting_and_excludes_confident_opponent_clips services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_revision_patch_payload_filters_selected_team_candidates -v` passed: 2 prompt evidence tests.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_quick_scan_match_requires_evidence_metadata ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_agent_editing_context_includes_team_targeting_and_attribution -v` passed: 2 tests.
- `PYTHONPATH=services/editing:ios/backend /tmp/hoopclips-py312-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_is_strict_structured_output_and_not_stored services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_payload_includes_team_targeting_and_excludes_confident_opponent_clips services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_revision_patch_payload_filters_selected_team_candidates -v` passed: 3 tests.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v` passed: 171 tests.
- `PYTHONPATH=services/editing:ios/backend /tmp/hoopclips-py312-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 52 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 59 tests.
- `cd services/control-plane && npm run typecheck` passed.
- `git diff --check` passed.

## Remaining Proof

This improves GPT context quality and selected-team auditability, but it is not a substitute for the labeled real-footage 85% evaluation or installed TestFlight smoke.

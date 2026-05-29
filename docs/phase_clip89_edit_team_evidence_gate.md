# Phase Clip89 Edit Team Evidence Gate

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Prevent AI Edit and GPT clip selection from treating legacy or weak selected-team metadata as a confident team match. Runtime quick scan now exports evidence refs and role groups; the edit service should require that same evidence before a cloud quick-scan attribution can become `matched`.

## Change

- Added an edit-side evidence gate for team attributions from `quick_scan` and `gpt_frame_review`.
- Confident selected-team status now requires:
  - at least two unique `evidenceFrameRefs`
  - at least two unique `evidenceRoleGroups`
- Attributions with high confidence but weak or missing evidence become `uncertain`.
- `includeUncertain=true` still keeps those clips in Review, matching the goal that borderline clips should remain visible for user review instead of being silently discarded.

## Guardrails

- This does not let iOS analyze video or decide team ownership.
- GPT and the edit planner still receive compact metadata only, not full videos.
- The renderer remains deterministic and does not receive GPT-generated commands.

## Validation

- `python3 -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py` passed.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_filter_keeps_matching_and_uncertain_clips_for_review ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_filter_rejects_conflicting_team_id_even_when_color_matches ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_filter_matches_jersey_color_alias_team_ids ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_filter_rejects_exact_team_id_with_color_conflict ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_selected_team_quick_scan_match_requires_evidence_metadata ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_explicit_uncertain_team_status_survives_edit_context -v` passed: 6 tests.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v` passed: 171 tests.
- `PYTHONPATH=services/editing:ios/backend /tmp/hoopclips-py312-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 52 tests.
- `PYTHONPATH=services/editing:ios/backend /tmp/hoopclips-py312-venv/bin/python -m unittest services.editing.tests.test_editing_service -v` passed: 42 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 59 tests.
- `cd services/control-plane && npm run typecheck` passed.
- `git diff --check` passed.

## Remaining Proof

This is a stricter selected-team confidence gate, not the final 85% real-footage proof. Internal launch still needs labeled footage evaluation and installed TestFlight smoke evidence.

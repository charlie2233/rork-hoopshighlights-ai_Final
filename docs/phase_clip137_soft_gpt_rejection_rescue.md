# Phase Clip137: Soft GPT Rejection Rescue

## Goal

Keep GPT-led editing strict while avoiding an empty edit when GPT rejects every reviewed clip only because it is uncertain about hype or confidence.

## Change

`apply_gpt_highlight_rerank` now records the rejection reason per reviewed clip. If no GPT-selected clips survive, the backend can rescue a small deterministic fallback only from clips that:

- were in the original candidate pool
- were reviewed by GPT
- pass deterministic render-quality gates
- were rejected for soft editorial reasons such as `not_confident`, `low_hype`, `not_sure`, or `not_enough_hype`

The backend still does not rescue clips rejected as boring, duplicate, unclear, non-basketball, team-ineligible, unsafe, unsupported by native/GPT evidence, or structurally invalid.

## Architecture

This stays cloud-first. GPT remains a semantic editor and never emits renderer commands. FFmpeg execution, source bounds, validation, and rendering remain deterministic backend responsibilities.

## Receipt Behavior

Soft rescue marks the rerank summary as:

- `status`: `fallback`
- `fallbackReason`: `all_clips_rejected_rescued`

Rejected reason counts are preserved so internal reviewers can see why GPT declined the clips before the deterministic review-safe rescue.

## Tests

Added backend coverage for:

- soft all-rejected GPT output rescues only quality candidates for user review
- hard all-rejected GPT output still does not fall back to original clips

Commands run:

```bash
python3 -m py_compile scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_soft_all_rejected_rescues_quality_candidates_for_review ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_all_rejected_does_not_fallback_to_original_clips ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_rejects_tracking_roles_that_were_not_sampled ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_uses_existing_clip_ids_only -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
git diff --check
```

Results:

- Python compile: passed.
- Focused GPT rerank checks: 4 tests passed.
- Full backend edit-plan agent suite: 95 tests passed.
- Editing-service GPT reranker suite: 58 tests passed.
- `git diff --check`: passed.

Launch-grade accuracy is still not claimed. This only improves resilience for internal review when GPT is too conservative.

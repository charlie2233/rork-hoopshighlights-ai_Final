# Phase Clip97 Stricter Shot Context Floor

Branch: `codex/phase-clip28-cloud-team-quick-scan`

## Goal

Make HoopClips less tolerant of shot clips that begin too close to the basket result or end before the viewer can see enough outcome context. The cloud path should expand thin source windows when possible, and reject weak shot windows when it cannot.

## Change

- Raised the backend EditPlan shot-context floor from `0.9s` lead-in / `0.6s` follow-through to `1.2s` lead-in / `0.8s` follow-through.
- Added GPT-reranker coverage for a barely contextual made-shot candidate that should be excluded before GPT review.
- Added EditPlan validator coverage for a manually patched/invalid render window that is only barely contextual around the shot event.

## Architecture Guardrails

- Cloud backend still owns analysis, GPT clip selection, edit planning, validation, rendering, and storage.
- iOS behavior did not change; it remains the upload/review/export/status/preview/share control surface.
- GPT still receives sampled candidate keyframes only, not full videos.
- GPT still cannot generate FFmpeg commands or bypass deterministic EditPlan validation.
- Blocks, steals, and defensive events continue to use the defensive-context path, so this shot-context floor does not erase non-scoring defensive highlights.

## Validation Evidence

- `python3 -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/tests/test_gpt_reranker.py` passed.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_quality_filter_excludes_tiny_and_late_shot_windows_before_gpt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_quality_filter_excludes_barely_contextual_shot_windows_before_gpt services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_source_context_expansion_salvages_thin_shot_windows_before_gpt -v` passed: 3 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_validate_edit_plan_rejects_shot_render_window_without_setup_context ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_validate_edit_plan_rejects_barely_contextual_shot_render_window ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_build_edit_plan_keeps_shot_render_window_from_shifting_too_late ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_duplicate_cleanup_prefers_complete_context -v` passed: 4 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v` passed: 53 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent -v` passed: 83 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed: 172 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` passed: 95 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 70 tests.
- `git diff --check` passed.

## Remaining Proof

This is a stricter quality guard, not the final 85% proof. Internal launch still needs the launch-grade labeled team-highlight accuracy report, live staging smoke, installed TestFlight smoke, and unblocked GitHub Actions.

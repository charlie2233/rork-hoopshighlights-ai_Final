# Phase Clip105: Uncertain Review Candidate IDs

## Goal

Keep strong-but-uncertain selected-team candidates recoverable after GPT chooses the final edit clips.

## Change

- `GPTHighlightRerankSummary` now carries bounded `uncertainReviewClipIds`.
- The list is computed before GPT-selected clips replace the request clip pool.
- Only selected-team uncertain clips that still pass plan-quality gates are included, so tiny or context-poor clips do not become review suggestions.
- `EditJobResponse` and AI Work Receipt expose the ID-only review list/count without adding video payloads, presigned URLs, or renderer instructions.

## Why

GPT should make the final edit tight, but the user still needs a way to review good moments when team ownership is uncertain. This is especially important for blocks, steals, and defensive stops where the play can be valuable even when jersey attribution is not strong enough for an automatic selected-team match.

## Validation

- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v`
  - Passed: 179 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v`
  - Passed: 97 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Passed: 71 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py ios/backend/tests/test_edit_plan_agent.py services/editing/editing_app/models.py services/editing/editing_app/main.py services/editing/tests/test_editing_service.py`
  - Passed.
- `git diff --check`
  - Passed.
- `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Failed before commit with `pass=20 warn=3 fail=9`, as expected while tracked files were still modified.
- `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Failed after commit with `pass=22 warn=2 fail=8`; repo hygiene checks passed, launch blockers remain.

## Remaining Launch Blockers

- Launch-grade labeled-footage team highlight accuracy report is still missing, so the 85% selected-team/highlight quality target remains unproven.
- Connected iPhone was detected as unavailable, so post-install TestFlight smoke is still blocked.
- Main-branch Cloud Edit Deploy Preflight and iOS Internal TestFlight Upload workflow evidence is stale relative to this branch checkout.
- Existing launch docs still record unproven TestFlight smoke, staging Worker live version proof, Cloudflare deploy credential proof, and live iOS kill-switch proof.

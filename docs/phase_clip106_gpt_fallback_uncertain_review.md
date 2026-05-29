# Phase Clip106: GPT Fallback Uncertain Review

## Goal

Keep selected-team uncertain candidates visible for user review even when GPT reranking is disabled or falls back.

## Change

- Promoted the uncertain-review ID collector into a shared backend helper.
- GPT fallback summaries now include bounded `uncertainReviewClipIds` using the same selected-team and plan-quality gates as successful GPT reranks.
- iOS cloud edit models now decode `gptUncertainReviewClipIds` and `gptUncertainReviewClipCount` from edit-job and AI Work Receipt responses.
- The AI Work Receipt adds a review row when the backend reports uncertain selected-team candidates, without adding video payloads, presigned URLs, or renderer commands.

## Why

The product goal is not to silently throw away good plays when jersey/team ownership is uncertain. If GPT cannot run, the deterministic path still needs to tell the user that strong uncertain selected-team moments are available in Review.

## Validation

- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_disabled_gpt_fallback_preserves_uncertain_team_review_ids ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_preserves_rejected_uncertain_review_clip_ids -v`
  - Passed: 2 tests.
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRenderStatusDecodesAIWorkTimelineAndReceipt -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditJobResponseDecodesUncertainReviewClipIds`
  - Passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v`
  - Passed: 179 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v`
  - Passed: 98 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Passed: 71 tests.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17'`
  - Passed.
- `xcodebuild build -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17'`
  - Passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py`
  - Passed.
- `git diff --check`
  - Passed.
- `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Failed before commit with `pass=20 warn=3 fail=9`, as expected while tracked and untracked files were still modified.
- `python3 scripts/submission_readiness_preflight.py --skip-live`
  - Failed after commit with `pass=22 warn=2 fail=8`; repo hygiene passed and remaining failures are launch-readiness blockers.

## Remaining Launch Blockers

- Launch-grade labeled-footage team highlight accuracy report is still missing, so the 85% selected-team/highlight quality target remains unproven.
- Connected iPhone/TestFlight smoke remains unproven.
- GitHub Actions are still blocked by account billing/spending-limit state until provider-side billing is fixed.

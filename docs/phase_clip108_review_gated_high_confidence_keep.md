# Phase Clip108 - Review-Gated Team Clip Keeps

## Goal

Prevent review-flagged clips from being auto-promoted into final AI Edit render candidates. Uncertain selected-team clips, unclear outcomes, and timing-risk clips should remain visible for the user to review instead of being swept into the final edit by "Keep High" or backend GPT revision paths.

## Change

- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
  - `keepHighConfidenceClips()` now keeps only high-confidence clips that do not need user review.
  - Cloud edit candidates carry `userReviewDecision: "kept"` only after the user has explicitly kept the clip for export.
- `ios/HoopsClips/HoopsClips/Views/ReviewView.swift`
  - The "Keep High" pending count excludes clips with `Team?`, `Outcome?`, or `Timing?` review badges.
- `ios/backend/app/editing.py`
  - Selected-team filtering now has a render-eligible mode that excludes uncertain clips unless `userReviewDecision == "kept"`.
  - EditPlan build, validation, GPT rerank application, and revision validation use render-eligible filtering.
- `services/editing/editing_app/main.py`
  - Render enqueue and render fallback source clips use the same render-eligible filter.
- `services/editing/editing_app/gpt_reranker.py`
  - GPT selection payloads include the review decision field and explain that uncertain selected-team clips without a user keep are review-only.
  - GPT revision patch payloads use only render-eligible clip IDs.
- `ios/HoopsClipsTests/HoopsClipsTests.swift`
  - Added coverage that a clean high-confidence clip is kept while a high-confidence uncertain-team clip stays discarded and reviewable.
- `ios/backend/tests/test_edit_plan_agent.py`, `services/editing/tests/test_editing_service.py`, `services/editing/tests/test_gpt_reranker.py`
  - Added and updated coverage for explicit user-kept uncertain clips, unreviewed uncertain clips staying out of render plans, strict GPT payloads, and revision patch filtering.

## Why

The cloud pipeline can preserve uncertain clips for Review so selected-team recall stays high, especially for blocks and steals. This keeps the review contract intact across client and backend: uncertainty is visible and recoverable, but it is not silently treated as final render intent.

## Validation

Passed on May 29, 2026:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_preserves_rejected_uncertain_review_clip_ids \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_does_not_render_unreviewed_uncertain_team_clip \
  ios.backend.tests.test_edit_plan_agent.EditPlanAgentTests.test_gpt_highlight_rerank_keeps_selected_and_uncertain_team_steals \
  services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_revision_patch_payload_filters_selected_team_candidates \
  -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker services.editing.tests.test_editing_service -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v
xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd -only-testing:HoopsClipsTests/HoopsClipsTests/testKeepHighConfidenceDoesNotAutoKeepNeedsReviewClips -only-testing:HoopsClipsTests/HoopsClipsTests/testCloudEditRequestEncodesOptionalUserPrompt
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd
git diff --check
python3 scripts/submission_readiness_preflight.py
```

Results:

- Focused backend regression tests: 4 passed.
- Touched backend/editing module suite: 185 passed.
- `ios/backend/tests` discovery: 182 passed.
- `services/editing/tests` discovery: 98 passed.
- Focused iOS Swift tests via XcodeBuildMCP and shell `xcodebuild test`: succeeded for the review-gated keep test and Cloud Edit request encoding test. Existing Swift 6 main-actor Codable warnings remain in the test target.
- iOS simulator Debug build via XcodeBuildMCP: succeeded.
- iOS `build-for-testing`: succeeded.
- `git diff --check`: passed.
- Submission readiness preflight after commit: `pass=22 warn=0 fail=11`.

## Submission Preflight Blockers

Do not submit to Apple from this branch yet. The May 29, 2026 preflight still reports:

- Missing launch-grade labeled-footage team-highlight accuracy report, so the 85% selected-team/highlight quality target is unproven.
- Physical iPhone is detected but unavailable for installed TestFlight smoke.
- Staging Worker `/v1/editing/version` route returns `404`.
- Direct editing service `/version` is stale for this checkout and is missing live feature flag fields.
- Main-branch Cloud Edit Deploy Preflight and iOS Internal TestFlight Upload workflows have not run for the current branch commit.
- Existing launch docs still record unproven installed TestFlight smoke, Worker version proof, Cloudflare deploy credential proof, and live iOS kill-switch proof.

## Remaining Launch Proof

This is a review/render guard, not the final 85% quality proof. Internal launch still needs a real labeled-footage report covering selected-team makes, misses, blocks, steals, uncertain review clips, opponent clips, and bad timing windows.

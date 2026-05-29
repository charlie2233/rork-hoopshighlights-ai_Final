# Phase Clip110 - Review Candidate Handoff and Raw Render Canonicalization

## Goal

Improve selected-team highlight recall without weakening render safety. iOS should send strong kept clips plus bounded review-only uncertain candidates to the cloud so GPT/backend can explain and preserve them for user review. Final rendering must still use only the backend's canonical stored plan and render-eligible clips.

## Change

- `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
  - AI Edit requests now include up to 60 cloud candidates instead of 40.
  - Kept clips are sent with `userReviewDecision=kept`.
  - Unkept clips that need team/outcome/timing review are sent as bounded review-only candidates with `userReviewDecision=unreviewed`.
  - Ordinary discarded clips are not sent to AI Edit.
- `services/editing/editing_app/main.py`
  - Raw `/v1/render-jobs` requests that reference a stored edit job are canonicalized through the stored cloud edit job.
  - Caller-supplied `editPlan`, `sourceClips`, `sourceObjectKey`, `planTier`, and RevenueCat user are ignored for stored edit jobs.
  - Revision renders through the raw route use the stored revision plan when `revisionId` is present.
- `services/editing/tests/test_editing_service.py`
  - Added coverage that raw render requests cannot override a stored edit job with a missing source, Pro tier, widescreen plan, or unreviewed uncertain selected-team clip.
- `ios/HoopsClipsTests/HoopsClipsTests.swift`
  - Added coverage that AI Edit requests preserve review-only uncertain candidates without auto-keeping them.
  - Updated the request cap test for the 60-candidate cloud handoff.

## Why

The backend already treats unreviewed uncertain team clips as review-only and excludes them from render-eligible source clips. Before this phase, iOS only sent already-kept clips to AI Edit, so potentially good selected-team blocks, steals, or unclear-but-reviewable clips could be lost before GPT/backend had a chance to reason about them. This phase gives the cloud a better candidate pool while keeping deterministic render safety in the backend.

## Validation

Run on May 29, 2026:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_raw_render_endpoint_uses_stored_cloud_plan_for_edit_jobs -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd
```

Result:

- Focused raw-render canonicalization backend test: passed.
- Focused Swift `HoopsClipsTests/testCloudEditRequestIncludesReviewOnlyUncertainCandidatesWithoutAutoKeepingThem`: passed via XcodeBuildMCP simulator test.
- Focused Swift `HoopsClipsTests/testCloudEditRequestSendsStrongestCandidatesBeforeSixtyClipCap`: passed via XcodeBuildMCP simulator test.
- Full `services.editing.tests.test_editing_service` suite: 44 tests passed.
- Full `services/editing/tests` discovery: 100 tests passed.
- Full `ios/backend/tests` discovery: 182 tests passed.
- iOS build-for-testing: passed.
- iOS simulator Debug build: passed via XcodeBuildMCP.

Known residual warnings:

- Focused Swift test runs reported pre-existing main actor isolation warnings in `ios/HoopsClipsTests/HoopsClipsTests.swift` around `PersistedProjectRecord` and `CloudEditJobResponse` test decoding.
- `build-for-testing` reported AppIntents metadata extraction warnings for targets without AppIntents dependencies. No build or test errors were reported.

## Launch Notes

- This does not claim the 85% accuracy target by itself. A launch-grade labeled footage run is still required.
- This does not move rendering or analysis into iOS.
- Review-only uncertain clips remain excluded from final render unless the user explicitly keeps them.

# Phase Clip109 - Canonical Stored Render Requests

## Goal

Keep the cloud backend as the source of truth for rendering. After HoopClips creates a stored edit job, iOS should only ask the backend to render that job. It should not resend or override the server-built EditPlan, source clips, plan tier, or source object key.

## Change

- `services/editing/editing_app/main.py`
  - Stored edit render requests now use the persisted cloud EditPlan, stored source object key, stored plan tier, and render-eligible selected-team source clips.
  - Client-supplied `editPlan`, `sourceClips`, `sourceObjectKey`, and `planTier` are ignored when the edit job exists.
- `ios/HoopsClips/HoopsClips/Services/CloudEditService.swift`
  - Initial AI Edit rendering now sends a stored-render command with install ID, idempotency key, and force-new flag only.
- `ios/HoopsClips/HoopsClips/Views/AIEditView.swift`
  - The AI Edit flow still verifies that a cloud source exists, then asks the backend to render the stored edit job instead of resending plan JSON.
- `services/editing/tests/test_editing_service.py`
  - Added coverage that a client override cannot swap in an invalid source object, Pro tier, widescreen aspect ratio, or unreviewed uncertain selected-team clip for a stored edit render.

## Why

This tightens the cloud-first architecture. GPT and the backend own selection, EditPlan generation, policy, source clip filtering, and render safety. iOS remains the control surface that uploads, reviews, requests render, polls status, previews, and shares.

## Validation

Run on May 29, 2026:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_stored_edit_render_uses_cloud_plan_and_render_eligible_source_clips -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip45-dd
git diff --check
```

Result:

- Focused stored-render canonicalization backend test: passed.
- Focused Swift `CloudEditServiceTests/testRequestStoredRenderCanUseStableInitialRenderKeyWithoutSourceOrPlanPayload`: passed via XcodeBuildMCP simulator test.
- Full `services.editing.tests.test_editing_service` suite: 43 tests passed.
- Full `services/editing/tests` discovery: 99 tests passed.
- Full `ios/backend/tests` discovery: 182 tests passed.
- iOS build-for-testing: passed.
- iOS simulator build: passed via XcodeBuildMCP.
- `git diff --check`: passed.

Known residual warnings:

- Xcode still reports the pre-existing main actor isolation warnings in `ios/HoopsClipsTests/HoopsClipsTests.swift` around `PersistedProjectRecord` and `CloudEditJobResponse` test decoding.

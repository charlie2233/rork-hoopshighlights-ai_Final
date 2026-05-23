# Phase UX2c Free Video Edit Limit 3

## Goal

Set the Free plan video editing chance limit to 3 while keeping the broader Free experience visible and useful for customer acquisition.

## Changes

- Kept the backend AI Edit Free plan policy at `maxDailyRenders=3`.
- Updated the iOS free-use default to `3` so visible Free counters match the AI Edit plan copy.
- Clamped stored iOS free-use counts to the configured cap so older installs do not keep showing `5`.
- Updated control-plane fallback quota metadata to return `3` when no durable quota value exists.
- Updated local analysis backend default `HOOPS_DAILY_QUOTA` documentation and test fixtures to `3`.
- Added the missing `httpx` dependency required by FastAPI/Starlette `TestClient` so backend tests run in a fresh venv.

## Validation

- `git diff --check`
- `npm --prefix services/control-plane test`
- `npm --prefix services/control-plane run typecheck`
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -only-testing:HoopsClipsTests/HoopsClipsTests -skipPackagePluginValidation`
- `PYTHONPATH=. /tmp/hoopclips-ios-backend-venv/bin/python -m unittest tests.test_local_adapters tests.test_render_jobs tests.test_edit_plan_agent tests.test_launch_guardrails`

## Notes

- This does not enable Pro rendering for Free.
- This does not change GPT candidate/keyframe caps.
- This does not add local iOS rendering or local video composition.

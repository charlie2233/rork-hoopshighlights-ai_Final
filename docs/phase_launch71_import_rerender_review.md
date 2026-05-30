# Phase Launch71 Import/Rerender Review

Date: 2026-05-30
Branch: codex/redesign-hoopclips-logo

## Scope

Follow-up review of uncommitted iOS and smoke-script changes after a second Codex pass reported possible issues.

## Fixes

- Fixed Photos-import temp filename interpolation so each imported video copies to a unique file.
- Kept Photos import file-backed by removing the `Data.self` fallback that could load large videos into memory.
- Moved Photos import error-state writes back onto `MainActor` while leaving transfer/copy work off the main actor.
- Fixed CloudEditService request-body tests to decode `URLProtocol` streamed request bodies.
- Preserved Cloud Locker rerender behavior:
  - revision rows call `/v1/edit-jobs/{editJobId}/revisions/{revisionId}/render`
  - base rows call `/v1/edit-jobs/{editJobId}/render` with `forceNew`
- Kept smoke-script failure details redacted for URLs/object keys/secrets/tokens/credentials.

## Validation

- `git fetch origin`
- `git diff --check`
- `python3 -m py_compile ios/backend/scripts/live_render_smoke.py services/editing/scripts/worker_render_smoke.py`
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2 -only-testing:HoopsClipsTests/CloudEditServiceTests test`
  - Result: passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2 build-for-testing`
  - Result: passed.
- `xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2 -only-testing:HoopsClipsTests test-without-building`
  - Result: passed.

## Notes

- Unrelated untracked root `HoopsClips.xcodeproj/` and `HoopsHighlightsAI.xcodeproj/` folders were not staged.
- No secrets, R2 credentials, or full presigned URLs were logged in this pass.
- This does not close the larger submission blockers: installed TestFlight smoke and launch-grade selected-team accuracy proof still need real evidence.

# Phase UX4b Cloud Locker Revision Re-render

Date: 2026-05-23
Branch: `codex/phase-ux4b-cloud-locker-revision-rerender`

## Scope

- Fixed My AI Edits / Cloud Locker re-render routing for revised render rows.
- Base render rows still request a force-new cloud render through `POST /v1/edit-jobs/{editJobId}/render`.
- Revision render rows now request a force-new cloud render through `POST /v1/edit-jobs/{editJobId}/revisions/{revisionId}/render`.
- iOS remains a control surface only. It sends cloud requests, watches real render state, downloads completed MP4s through backend-minted links, and shares the finished file.
- No local video analysis, planning, composition, FFmpeg command generation, or rendering was added to iOS.

## Behavior

`CloudEditService.requestLockerRerender(render:installID:)` now chooses the backend route from the selected history row:

- If `revisionId` is present, HoopClips calls the revision render endpoint with a fresh `ios-revision-rerender-...` idempotency key.
- If `revisionId` is absent, HoopClips keeps the existing stored-edit re-render path with `forceNew: true`.

This preserves the deterministic cloud renderer contract: the backend loads the stored edit or stored revision plan, validates policy/template bounds, and enqueues the new render job. iOS never resends source object keys, edit plans, source clips, presigned URLs, or renderer commands for Locker re-renders.

## Privacy And Storage

- Render history still returns metadata only.
- Download URLs are still minted only through the render-scoped download endpoint.
- Re-render requests do not include source storage keys, full presigned URLs, R2 credentials, FFmpeg commands, or local file paths.
- Telemetry continues to send render IDs, edit IDs, revision IDs, template IDs, plan tier, and failure summaries only.

## Validation

Commands run:

```sh
xcodebuildmcp session_show_defaults
xcodebuildmcp test_sim -only-testing:HoopsClipsTests/CloudEditServiceTests -skipPackagePluginValidation CODE_SIGNING_ALLOWED=NO
xcodebuildmcp test_sim -only-testing:HoopsClipsTests -skip-testing:HoopsClipsUITests -skip-testing:HoopsClipsUITestsLaunchTests -skipPackagePluginValidation CODE_SIGNING_ALLOWED=NO
xcodebuildmcp build_sim -skipPackagePluginValidation CODE_SIGNING_ALLOWED=NO
git diff --check
npm test -- --test-reporter=spec
npm run typecheck
/Users/hanfei/.homebrew/bin/python3.13 -m venv /tmp/hoopclips-editing-py313-venv
/tmp/hoopclips-editing-py313-venv/bin/python -m pip install -r services/editing/requirements.txt pytest httpx
/tmp/hoopclips-editing-py313-venv/bin/python -m pytest services/editing/tests -q
python3 scripts/submission_readiness_preflight.py
```

Results:

- Focused CloudEditService tests: 7 passed, 0 failed.
- Full HoopsClips unit target: 63 passed, 0 failed, 0 skipped.
- iOS Debug simulator build: succeeded.
- Control-plane tests: 20 passed, 0 failed.
- Control-plane typecheck: passed.
- Editing-service tests: 51 passed, 0 failed.
- `git diff --check`: passed.
- Submission readiness preflight after commit: 18 pass, 0 warn, 12 fail. The branch was clean; the remaining launch blockers are listed below and must be cleared before Apple submission.

## Launch Notes

- This removes a Cloud Locker correctness risk where a revised row could silently re-render the base edit instead of the selected revised plan.
- Live TestFlight proof still requires the existing launch smoke: upload/import, cloud analysis, review, export, AI Edit render, More Hype revision, revised preview, Locker re-render, share/open-in.
- Production/internal launch remains blocked by the existing provider and smoke-test gates documented in `docs/phase_launch11_submission_diagnostics.md`.
- Current blocking evidence includes missing local signing/team inputs, no archive/IPA artifact, unavailable wired iPhone for installed smoke, staging Worker `/v1/editing/version` returning 404, missing Cloudflare/GCP deploy inputs, failed latest main deployment/upload workflows, missing iOS upload secrets, and unproven live kill-switch state.

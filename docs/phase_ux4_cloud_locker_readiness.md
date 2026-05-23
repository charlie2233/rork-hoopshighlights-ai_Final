# Phase UX4: Render History / Cloud Locker Readiness

Branch: `codex/phase-ux4-cloud-locker-readiness`

Date: 2026-05-23

## Scope

This phase hardens My AI Edits / Cloud Locker for internal TestFlight readiness without moving analysis, edit planning, rendering, or storage into iOS. iOS remains a control surface for upload, review, status, preview, download, share, and editor handoff.

## Changes

- iOS now downloads the minted render URL to a local MP4 before previewing a new render, a revised render, or a Cloud Locker re-render. `AIEditView` no longer streams the presigned `downloadUrl` directly into `AVPlayer`.
- Share/download refreshes now request a fresh URL by `renderJobId`, keeping the selected Cloud Locker row tied to the exact render instead of falling back to the latest edit-level render.
- Expired Cloud Locker rows are labeled `Expired`, disable `Download / Share`, and keep `Re-render` available when live rendering is enabled.
- Backend `forceNew: true` stored-edit renders without an explicit client idempotency key now receive a fresh server-side forced-render key, so they cannot replay the old deterministic render.
- Retention cleanup now deletes the matching render idempotency index when it deletes an expired render state object.

## Evidence

Subagent findings addressed:

- Preview paths were using full download URLs directly in `AVPlayer`.
- Expired rendered locker rows remained actionable until backend `410 render_expired`.
- `forceNew` could be bypassed without a unique client idempotency key.
- Cleanup could leave stale idempotency indexes behind deleted render state.

Commands run:

```bash
git fetch origin --prune
python3 -m py_compile services/editing/editing_app/main.py services/editing/editing_app/render_state.py services/editing/editing_app/retention_cleanup.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_retention_cleanup_dry_run_lists_expired_delete_eligible_artifacts services.editing.tests.test_editing_service.EditingServiceTests.test_retention_cleanup_execute_deletes_expired_delete_eligible_artifacts services.editing.tests.test_editing_service.EditingServiceTests.test_render_existing_edit_job_without_resending_plan -v
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
python3 scripts/launch_backend_config_preflight.py | tee /tmp/hoopclips-ux4-cloud-locker-readiness-preflight.log
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -configuration Debug build-for-testing CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation | tee /tmp/hoopclips-ux4-cloud-locker-readiness-bft.log
rg -n "AVPlayer\(url: url\)|Preparing\.\.\.|Rendering\.\.\.|Download URL expired, refreshing" ios/HoopsClips/HoopsClips/Views/AIEditView.swift
git diff --check
```

Results:

- Python compile: passed.
- Focused backend regressions: `Ran 3 tests in 3.695s OK`.
- Full editing service suite: `Ran 37 tests in 34.524s OK`.
- Backend/config preflight: `pass=57 warn=12 fail=0`.
- XcodeBuildMCP Debug simulator build: succeeded, log `build_sim_2026-05-23T07-38-12-427Z_pid17685_6d22f5b4.log`.
- Shell build-for-testing: `** TEST BUILD SUCCEEDED **`.
- UI URL/ellipsis guard: no matches for direct `AVPlayer(url: url)`, fake progress ellipses, or old expired-link copy in `AIEditView.swift`.
- Secret/presigned marker guard: no matches for signed URL markers or literal secret assignments in changed files.
- `git diff --check`: passed after final doc edits.

Known warnings:

- Existing iOS build warnings remain in `CloudAnalysisService.swift`, `VideoAnalysisService.swift`, `VideoExportService.swift`, and `CloudAnalysisTypes.swift`. They are not introduced by this phase.
- Preflight still warns that production Worker cutover is absent by design, top-level Worker config is placeholder-only, backend Sentry/Statsig/RevenueCat runtime integrations are not fully configured, Cloud Run ingress relies on shared-secret and Worker mediation, and prior launch docs still record production/CI credential blockers.

## Blockers

- Real installed-device TestFlight smoke is still required: install app, upload/import, cloud analysis, Review, Export, AI Edit render, preview, More Hype revision, revised preview, share/open-in.
- CI deploy remains blocked until `CLOUDFLARE_API_TOKEN` scope is verified and used for Wrangler deploy and rollback.
- Production cutover remains blocked by the existing launch gate. This phase keeps internal staging behavior only.

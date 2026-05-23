# Phase UX4 Render History Cloud Locker

Date: 2026-05-22
Branch: `codex/phase-ux4-render-history-cloud-locker`

## Scope

- Added a cloud-owned render history endpoint for My AI Edits / Cloud Locker.
- Added iOS control-surface UI for latest renders, expiration copy, re-download/share, and cloud re-render.
- Kept analysis, render planning, revisions, storage, download URL minting, and re-rendering owned by the editing service.
- Did not add local iOS video analysis, composition, or rendering.

## Backend Evidence

- New endpoint: `GET /v1/render-jobs?installId=<install>&limit=<n>`.
- Response is scoped by install ID and returns render metadata only. It does not include presigned download URLs.
- Existing download URL endpoint remains the only path that mints a short-lived URL: `GET /v1/render-jobs/{renderJobId}/download-url`.
- Stored base-edit re-render uses `POST /v1/edit-jobs/{editJobId}/render` with `forceNew: true`; normal render requests remain idempotent. Follow-up UX4b routes revised Locker rows through `POST /v1/edit-jobs/{editJobId}/revisions/{revisionId}/render`.
- GPT rerank receipt reconstruction now carries the stored `gptRerankSummary` when render state is reloaded.

Synthetic test evidence:

- `test_render_history_lists_install_scoped_metadata_without_presigned_urls`
  - synthetic render ID: `render_history_1`
  - cross-install render ID excluded: `render_history_other`
  - asserts no `downloadUrl` or `leaseToken` in history payload
- `test_render_existing_edit_job_without_resending_plan`
  - verifies `forceNew: true` creates a new render ID for the same stored edit
  - verifies both original and forced re-render appear in history

## iOS Evidence

- `CloudEditService.fetchRenderHistory(installID:limit:)` reads backend render history.
- `CloudEditService.fetchDownloadURL(renderJobID:installID:)` asks the backend for a fresh short-lived URL per locker item.
- `CloudEditService.requestStoredRender(editJobID:installID:)` sends a base cloud re-render request with `forceNew: true`.
- `CloudEditService.requestLockerRerender(render:installID:)` routes revised rows through the revision render endpoint so the selected revised plan is re-rendered.
- `AIEditView` now shows a My AI Edits card with latest render status, template name, duration/aspect ratio, expiration, Download / Share, Re-render, and refresh controls.
- Download / Share downloads the rendered MP4 through the existing service path, attaches it to the export service, and opens the iOS share sheet.

No live TestFlight smoke or real cloud render job was created in this branch. This phase is verified by simulator build and editing-service tests only.

## Privacy And Storage Checks

- `git diff --check`: passed.
- Grep checked for `downloadUrl`, `presigned`, `R2_`, `AWS_`, `SECRET`, `ACCESS_KEY`, `leaseToken`, `x-hoops-editing-secret`, `print(`, and `console.log`.
- History endpoint does not create or return presigned URLs.
- Event logging for history uses only `renderCount` and `limit`; no install ID, credentials, or URLs are emitted.
- Existing presigned URL responses remain limited to explicit download endpoints.
- Root untracked Xcode folders were left untouched and unstaged:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Validation

Commands run:

```sh
git fetch --prune origin
git pull --ff-only
git checkout -b codex/phase-ux4-render-history-cloud-locker
git push -u origin codex/phase-ux4-render-history-cloud-locker
/Users/hanfei/.homebrew/bin/python3.13 -m venv /tmp/hoopclips-editing-test-venv
/tmp/hoopclips-editing-test-venv/bin/python -m pip install -r services/editing/requirements.txt pytest httpx
/tmp/hoopclips-editing-test-venv/bin/python -m pytest services/editing/tests/test_editing_service.py -q
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-derived-data -skipPackagePluginValidation build-for-testing
```

Results:

- Editing service tests: `30 passed in 28.42s`.
- iOS Debug simulator build through XcodeBuildMCP: succeeded.
- iOS `build-for-testing`: `** TEST BUILD SUCCEEDED **`.

## Remaining Blockers

- Real post-install TestFlight smoke still needs a trusted online iPhone and staging backend access.
- Production/internal launch still depends on the existing cloud deployment/config gates, including Wrangler automation credentials and verified staging/prod secrets.
- This phase does not implement RevenueCat entitlement enforcement beyond the existing Pro surfaces.

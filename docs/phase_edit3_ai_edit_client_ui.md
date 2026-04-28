# Phase Edit3 AI Edit Client UI

## Verdict

The iOS app now has a first cloud AI Edit client surface:

```text
Review kept clips
-> Make Highlight Reel
-> cloud edit plan
-> cloud render
-> remote MP4 preview
-> local MP4 download
-> system share sheet / Open In
```

The architecture boundary remains intact:

```text
iOS does not analyze, plan, compose, or render the final AI edit.
iOS only requests cloud jobs, polls status, previews the returned MP4, downloads it, and shares it.
```

## Client Flow

- `ReviewView` shows `Make Highlight Reel` when clips exist.
- `AIEditView` lets the user choose:
  - Personal Highlight: 9:16, 15/30/45 seconds
  - Full Game Highlight: 16:9, 60/90/120 seconds
  - Coach Review: 16:9, 60/120/180 seconds
- `CloudEditService` calls the active Worker URL from runtime config.
- The app fetches the backend-created edit plan, then sends that same backend plan back with the render request so Cloud Run instance routing does not require in-memory plan affinity.
- Preview uses `VideoPlayer` with the remote presigned MP4 URL.
- Sharing downloads the MP4 to a local temp file first, then presents `SystemShareSheet`.

## Backend Contract Added

The active control-plane Worker now proxies:

```text
POST /v1/edit-jobs
GET  /v1/edit-jobs/:id
GET  /v1/edit-jobs/:id/plan
POST /v1/edit-jobs/:id/render
GET  /v1/edit-jobs/:id/render-status
GET  /v1/edit-jobs/:id/download-url
```

The editing Cloud Run service stores edit plans in memory for staging, but the iOS render call also includes the returned backend plan to keep the render request robust if a later Cloud Run revision becomes stateless or load-balanced across instances.

## Runtime Config

Debug config points the AI edit client at staging:

```text
HOOPS_CLOUD_EDIT_BASE_URL = https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

Release keeps this blank by default:

```text
HOOPS_CLOUD_EDIT_BASE_URL =
```

Public release still requires an explicit gate decision before cloud rendering is made production-facing.

## Verification

Passed:

```text
services/editing tests: 7 passed
services/control-plane editing proxy tests: 4 passed
services/control-plane typecheck: passed
iOS Debug simulator build: passed
iOS HoopsClipsTests unit target: passed
git diff --check: passed
```

Remaining local simulator limitation:

```text
Full-scheme xcodebuild test, including the UI test runner, hit a local simulator runner IPC failure:
NSMachErrorDomain Code=-308 "(ipc/mig) server died".
The app unit target was rerun separately and passed.
```

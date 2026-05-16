# Phase Edit7g Post-TestFlight Internal Smoke

Date: 2026-05-15 Pacific / 2026-05-16 UTC

Branch:

```text
codex/phase-edit7g-post-testflight-internal-smoke
```

Base commit:

```text
4475bb0dfcd5153e8ece93a23329424d9e2a8bea
```

Goal:

```text
Verify the uploaded internal TestFlight build works after real TestFlight installation.
Prove the full HoopClips AI Edit Agent flow from installed app through the staging backend.
```

## Result

The real post-install TestFlight smoke is blocked in this environment because no online trusted iPhone is available to install or run the TestFlight build.

This branch does not claim the TestFlight-installed app passed. It records fresh local/device/backend evidence and the exact blocker.

## Current Repo State

Source branch before 7g:

```text
codex/phase-edit7f-internal-testflight-upload
```

Synced state:

```text
HEAD: 4475bb0dfcd5153e8ece93a23329424d9e2a8bea
origin/codex/phase-edit7f-internal-testflight-upload: 4475bb0dfcd5153e8ece93a23329424d9e2a8bea
```

Known unrelated untracked root project folders remain untouched:

```text
HoopsClips.xcodeproj/
HoopsHighlightsAI.xcodeproj/
```

## TestFlight Build Target

Phase Edit7f documented the intended internal staging candidate:

```text
App: HoopClips
Bundle ID: atrak.charlie.hoopsclips
Marketing version: 1.0.0
Build number: 3
Backend mode: staging
```

Fresh local build settings still resolve:

```text
CODE_SIGN_STYLE = Automatic
CURRENT_PROJECT_VERSION = 3
DEVELOPMENT_TEAM = K99RADPB9G
HOOPS_DEVELOPMENT_TEAM = K99RADPB9G
MARKETING_VERSION = 1.0.0
PRODUCT_BUNDLE_IDENTIFIER = atrak.charlie.hoopsclips
```

The previous temporary archive/export outputs are no longer present:

```text
/tmp/HoopsClips-AIEdit-InternalStaging.xcarchive: missing
/tmp/HoopsClips-AIEdit-InternalStaging: missing
```

That is not a product failure; it only means the earlier upload artifacts are not available for local re-inspection from `/tmp`.

## Device/TestFlight Access

Available device discovery:

```text
Mac: local MacBook Air
Offline physical device: charlie iPhone (26.4.2) (00008130-000A001A1178001)
Simulators: available
```

Blocker:

```text
The real iPhone is offline, so Codex cannot install the TestFlight build, open the installed app, or capture post-install screenshots/video from this machine.
```

Credential/environment check:

```text
No APP_STORE / ASC / FASTLANE / ITC / APPLE upload or query environment variables were present.
No CLOUDFLARE or GCP deploy environment variables were present.
```

Therefore this branch cannot independently verify App Store Connect processing status or TestFlight availability through API credentials.

## Staging Backend Verification

### Editing service

Fresh `/version` check:

```json
{
  "service": "hoopclips-editing",
  "backendModelVersion": "editing-cloud-v1",
  "gitSha": "d00d0d5",
  "ffmpeg": {
    "renderer": "cloud_ffmpeg",
    "rendererVersion": "ffmpeg-renderer-v1",
    "ffmpegAvailable": true,
    "ffprobeAvailable": true,
    "drawtextAvailable": true
  },
  "featureFlags": {
    "aiEditEnabled": true,
    "aiEditRevisionEnabled": true,
    "aiEditTemplatePackEnabled": true,
    "aiEditMaxDailyRenders": null,
    "aiEditFreeWatermarkRequired": true,
    "aiEditProExportsEnabled": false
  }
}
```

Editing service status:

```text
URL: https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
AI Edit enabled: true
Revision enabled: true
Template pack enabled: true
Renderer: ffmpeg-renderer-v1
```

### Control-plane Worker route probe

Probe:

```text
POST /v1/edit-jobs/edit_fake_probe/revise
```

Result:

```json
{
  "errorCode": "edit_job_not_found",
  "errorMessage": "Edit job was not found.",
  "failureReason": "Edit job was not found."
}
```

This is the expected response for a fake edit job and confirms the staging Worker recognizes/proxies the revision route.

### Inference service cost-control state

Fresh GCP check:

```text
service: hoopsclips-inference-staging
revision: hoopsclips-inference-staging-00036-p7l
minScale: unset, meaning 0
maxScale: 2
url: https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app
```

The clip-analysis service remains deployed, but no longer pays for one always-warm idle instance.

## Full User Flow Status

Target smoke flow:

```text
Install TestFlight build 3
-> Open app
-> Import/upload sample video
-> Cloud analysis completes
-> Review shows clips
-> Export
-> AI Edit Agent
-> Personal Highlight
-> Render
-> Preview MP4
-> More Hype revision
-> Render revision
-> Preview revised MP4
-> Share/Open In
```

Current status:

| Step | Status | Evidence |
| --- | --- | --- |
| Build 3 target metadata | ready from local settings | version/build/team/bundle verified |
| TestFlight build availability | not verified fresh | no ASC/TestFlight API credentials in environment |
| Physical install | blocked | iPhone is offline |
| App launch from TestFlight | blocked | no online physical device |
| Import/upload sample video | blocked | requires installed app/device |
| Cloud analysis | not run in this phase | requires installed app/device for user-flow proof |
| Review clips | blocked | requires installed app/device |
| Export AI Edit render | not run in this phase | backend is healthy, but installed-app flow blocked |
| More Hype revision | not run in this phase | route probe passed for fake job |
| Preview/share | blocked | requires installed app/device |

## Classification

Blocker type:

```text
TestFlight/device access blocker
```

Not classified as:

```text
app config failure
backend config failure
render service failure
control-plane route failure
network failure
UI bug
```

## Required Manual Next Step

Connect and unlock the physical iPhone, verify it is trusted by this Mac, then rerun the post-install smoke.

Minimum operator checklist:

```text
1. Open TestFlight on the iPhone.
2. Install HoopClips build 3.
3. Confirm app version 1.0.0 build 3.
4. Open the app.
5. Import/upload a sample basketball video.
6. Wait for cloud analysis.
7. Confirm Review shows detected clips.
8. Navigate to Export.
9. Confirm AI Edit Agent is visible.
10. Select Personal Highlight.
11. Render.
12. Confirm MP4 preview loads.
13. Tap More Hype.
14. Render revision.
15. Confirm revised MP4 preview loads.
16. Open Share/Open In.
17. Record editJobId, renderJobId, revisionId, revisedRenderJobId, Worker URL, Cloud Run revision, and any failureReason.
```

## Go/No-Go

Internal beta go/no-go from this branch:

```text
NO-GO for claiming post-install TestFlight proof.
```

Reason:

```text
The uploaded build may be correct, and staging backend is healthy, but the installed TestFlight app has not been run from a physical device in this phase.
```

Recommended next action:

```text
Bring the iPhone online and rerun Phase Edit7g as a real device/TestFlight smoke.
```

## Validation Run

Fresh validation:

```text
git fetch origin codex/phase-edit7f-internal-testflight-upload: passed
git branch/remote lookup for 7g before creation: no existing local/remote branch
device discovery: physical iPhone found but offline
iOS Release build settings lookup: passed
staging editing /version: passed
staging Worker revision-route fake-job probe: passed with expected edit_job_not_found
inference Cloud Run minScale check: passed, minScale unset => 0
```

No source code changed in this branch. Backend tests and iOS builds were not rerun because this branch only records post-install smoke access status and does not modify app/backend behavior.

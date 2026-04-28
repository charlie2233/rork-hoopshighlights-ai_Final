# Phase Edit3b Live AI Edit Client Smoke

## Verdict

The live cloud edit path is proven through the same Worker API surface used by the iOS client:

```text
Worker upload presign
-> source MP4 in R2 uploads
-> POST /v1/edit-jobs
-> GET /v1/edit-jobs/:id/plan
-> POST /v1/edit-jobs/:id/render
-> Cloud Run FFmpeg render
-> R2 final.mp4 + render_log.json
-> Worker download URL
-> downloaded playable MP4
```

The hands-on iOS simulator app build/install/launch also passed, but full UI import/analyze/tap-through was not completed because desktop click automation against Simulator failed in this environment.

## Deploy Evidence

Cloud Run editing service:

```text
service: hoopclips-editing-staging
region: us-central1
revision: hoopclips-editing-staging-00003-sbj
service URL: https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
version.gitSha: b891942
readyz.status: ok
readyz.ffmpegAvailable: true
readyz.ffprobeAvailable: true
readyz.drawtextAvailable: true
readyz.renderStorage.provider: r2
```

Control-plane Worker:

```text
worker: hoopsclips-control-plane-staging
url: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
version id: 8c012f96-95e2-4a39-8730-f20510d123c7
EDITING_BASE_URL: configured as Worker secret
EDITING_SHARED_SECRET: configured as Worker secret
```

Known health endpoint note:

```text
GET /readyz and GET /version return 200 from the Cloud Run service.
GET /healthz returns a Google Frontend HTML 404 on the run.app URL even though FastAPI OpenAPI advertises /healthz.
Use /readyz as the operational readiness gate for this deploy.
```

## Worker API Smoke

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend \
  ios/backend/.venv/bin/python services/editing/scripts/ios_ai_edit_client_smoke.py \
  --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --output-dir /tmp/hoopclips-phase-edit3b-worker-smoke \
  --timeout-seconds 300
```

Result:

```text
status: pass
editJobId: edit_b3997cf1f75b445aa937ccd7d08918ea
renderJobId: render_ef782a3ab812466a9762e6592a006872
sourceObjectKey: uploads/25a101ba8d234fd98094bd112276161f/source.mp4
outputObjectKey: edits/edit_b3997cf1f75b445aa937ccd7d08918ea/render_jobs/render_ef782a3ab812466a9762e6592a006872/final.mp4
renderLogObjectKey: edits/edit_b3997cf1f75b445aa937ccd7d08918ea/render_jobs/render_ef782a3ab812466a9762e6592a006872/render_log.json
downloadedPath: /tmp/hoopclips-phase-edit3b-worker-smoke/final.mp4
sha256: 48ea1422ec9bcdd64c9c72b69c148edacf01f8b6dda30d0554d1979083ee89a1
```

FFprobe summary:

```text
container: mov,mp4,m4a,3gp,3g2,mj2
duration: 14.422005
size: 349336
video: h264, 720x1280, yuv420p, 30 fps
audio: aac
```

The script does not print the presigned `downloadUrl`; it downloads the MP4 and reports object keys plus local artifact metadata.

## iOS Simulator Smoke

Simulator:

```text
device: iPhone 17
simulator id: A46E2157-77ED-42CE-959D-65C068681A47
iOS runtime: 26.0.1
bundle id: atrak.charlie.hoopsclips
```

Runtime overrides applied:

```bash
xcrun simctl spawn A46E2157-77ED-42CE-959D-65C068681A47 defaults write atrak.charlie.hoopsclips hoops.cloudAnalysisBaseURL -string 'https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev'
xcrun simctl spawn A46E2157-77ED-42CE-959D-65C068681A47 defaults write atrak.charlie.hoopsclips hoops.cloudEditBaseURL -string 'https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev'
```

Passed:

```text
Debug simulator build: passed
install to simulator: passed
app launch: passed
staging Worker host reachable from app logs: observed HTTP 200/304 network responses
screenshot: /tmp/hoopclips-phase-edit3b-launch-2.png
```

Not completed:

```text
Full manual UI flow was not completed:
Review -> Make Highlight Reel -> select Personal Highlight -> render -> preview -> share
```

Reason:

```text
Computer Use click events against Simulator returned:
Apple event error -10005: noWindowsAvailable

AppleScript System Events click returned:
error -25200
```

The source smoke video was added to the simulator Photos library, but importing it through the app requires working Simulator UI interaction or a manual tester.

## Client Hardening Added

This phase also hardens the iOS client around live smoke findings:

```text
CloudEditRenderState now accepts render_requested.
CloudEditService polling treats render_requested as in-progress.
AIEditView status icon/color handles render_requested.
Share preparation refreshes near-expired download URLs.
If a downloaded MP4 URL returns 401/403/404/410, the app fetches a fresh download URL and retries.
Downloaded MP4 files are checked for non-zero size before sharing.
```

The app still shares the downloaded local MP4 file through `SystemShareSheet`, not the raw presigned URL.

## Remaining Manual Gate

Run one manual or reliable UI-automation pass on Simulator or a real device:

```text
Import a video from Photos.
Run cloud analysis with staging Worker runtime config.
Keep at least one clip.
Open Review.
Tap Make Highlight Reel.
Select Personal Highlight and a target duration.
Request render.
Confirm status reaches rendered.
Confirm MP4 preview plays.
Confirm Download / Share / Open In presents the share sheet.
```

This is now a UI automation/access blocker, not a backend render blocker.

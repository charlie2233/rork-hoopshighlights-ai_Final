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

The iOS simulator UI smoke is also proven through the staged client flow:

```text
Review
-> Create AI Edit
-> Personal Highlight / 30s
-> cloud edit plan
-> cloud render
-> rendered MP4 preview
-> Download / Share / Open In
-> system share surface
```

The UI smoke uses a DEBUG-only launch argument to seed an already analyzed cloud clip set from a staging R2 source object. It does not add iOS analysis, edit planning, or rendering.

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

Live UI test command:

```bash
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' \
  -only-testing:HoopsClipsUITests/HoopsClipsUITests/testLiveAIEditClientSmokeFlow \
  -parallel-testing-enabled NO \
  -derivedDataPath /tmp/hoopsclips-edit3b-live-ui-derived-identifiers \
  CODE_SIGNING_ALLOWED=NO
```

Passed:

```text
test: HoopsClipsUITests.testLiveAIEditClientSmokeFlow
result: passed
duration: 133.938 seconds
xcresult: /tmp/hoopsclips-edit3b-live-ui-derived-identifiers/Logs/Test/Test-HoopsClips-2026.04.27_20-47-35--0700.xcresult
```

Verified UI sequence:

```text
Review tab exists
Make Highlight Reel card exists
Create AI Edit entry button is enabled
AI Edit sheet opens
Personal Highlight style exists
30 seconds target length exists
Create render button requests the live Worker-backed cloud edit
status reaches Rendered
rendered preview appears
Download / Share / Open In opens the system share surface
```

Captured attachments in the xcresult:

```text
01 Review Make Highlight Reel
02 AI Edit Style Picker
03 AI Edit Rendered Preview
04 AI Edit Share Sheet
```

The share surface appears in XCTest as `ActivityListView` / `ShareSheet.RemoteContainerView`, not always as an `XCUIElementTypeSheet`.

Known simulator runner note:

```text
One earlier run hit NSMachErrorDomain Code=-308 from Xcode's cloned simulator runner.
The successful pass used -parallel-testing-enabled NO on the booted iPhone 17 simulator.
```

## Client Hardening Added

This phase also hardens the iOS client around live smoke findings:

```text
CloudEditRenderState now accepts render_requested.
CloudEditService polling treats render_requested as in-progress.
AIEditView status icon/color handles render_requested.
Share preparation refreshes near-expired download URLs.
If a downloaded MP4 URL returns 401/403/404/410, the app fetches a fresh download URL and retries.
Downloaded MP4 files are checked for non-zero size before sharing.
Review and AI Edit buttons now have stable accessibility identifiers for reliable smoke automation.
```

The app still shares the downloaded local MP4 file through `SystemShareSheet`, not the raw presigned URL.

## Optional Manual Follow-Up

The live smoke proves the cloud edit client path from an already analyzed clip set. A separate manual product smoke should still cover the full user journey from a real imported video:

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

# Phase Edit7a1 Live Durable Render Smoke

Date: 2026-05-04 UTC

Branch:

```text
codex/phase-edit7a1-live-durable-render-smoke
```

Base commit:

```text
7650c88
```

Goal:

```text
Prove the Phase Edit7a durable render state changes through the real staging path:
Worker -> Cloud Run editing service -> FFmpeg -> R2 final.mp4/render_log.json.
```

This phase did not add product features. It deployed the durable-state editing service, ran a live Worker-path render/revision smoke, proved duplicate idempotency, read durable render records from R2, forced a Cloud Run service reload, and verified stale renders transition to `failed_timeout`.

## Staging Deploy

Cloud Build initially timed out while uploading the full repository source archive to GCS:

```text
gcloud builds submit . ... -> ReadTimeout uploading source to storage.googleapis.com
```

The deploy was completed by submitting a minimal temporary Cloud Build context containing `services/editing`, `ios/backend/app`, and the required editing assets. No repo files were changed for that workaround.

Cloud Build:

```text
build id: 2c09bd79-5bb2-4827-a46d-03242a5ba97d
status: SUCCESS
image: us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:7650c88
digest: sha256:7b45814b387312bf249ae5369ba71db6c6926150f2e122d55f140ce0bbb45539
```

Cloud Run service:

```text
project: hoopsclips-9d38f
region: us-central1
service: hoopclips-editing-staging
deployed revision: hoopclips-editing-staging-00017-ghd
reload-proof revision: hoopclips-editing-staging-00018-5nx
traffic: 100 percent to latest revision
service URL: https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
```

Cloud Run guardrails remained enabled:

```text
autoscaling.knative.dev/maxScale: 1
run.googleapis.com/cpu-throttling: false
```

Service checks after deploy/reload:

```text
/version: 200
gitSha: 7650c88
ffmpegAvailable: true
ffprobeAvailable: true
/readyz: 200
auth: configured
renderStorage.provider: r2
renderStorage.providerReady: true
```

`/healthz` still returns the previously observed Cloud Run frontend 404 in staging, so `/readyz` and `/version` remain the reliable deployed-service checks for this service.

Active Worker:

```text
url: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
latest observed Worker deployment version: 3dc0312f-9043-4762-b8c1-dfd46f0a0ad1
```

## Normal Render Smoke

Smoke harness:

```bash
HOOPS_SMOKE_OUTPUT_DIR=/tmp/hoopclips-phase7a1-durable-smoke-20260503T205723 \
HOOPS_SMOKE_INSTALL_ID=smoke-durable-1777867043 \
HOOPS_SMOKE_APP_VERSION=phase-edit7a1-smoke \
HOOPS_SMOKE_ANALYSIS_VERSION=phase-edit7a1-smoke \
HOOPS_SMOKE_TRACE_ID=phase-edit7a1-durable-smoke \
HOOPS_SMOKE_TIMEOUT_SECONDS=480 \
python3 services/editing/scripts/policy_observability_smoke.py
```

Result:

```text
status: pass
editJobId: edit_db9ab36166ad4246b19303ed10f4d096
renderJobId: render_c2da574a59454b2a9f5f6712b7297cb1
duplicateRenderJobId: render_c2da574a59454b2a9f5f6712b7297cb1
duplicateBehavior: idempotent_existing_render_returned
templateId: personal_highlight_v1
planTier: free
```

Output:

```text
sourceObjectKey: uploads/dea8748f1ab04417b0167a844cbaeebb/source.mp4
final object key: edits/edit_db9ab36166ad4246b19303ed10f4d096/render_jobs/render_c2da574a59454b2a9f5f6712b7297cb1/final.mp4
render log key: edits/edit_db9ab36166ad4246b19303ed10f4d096/render_jobs/render_c2da574a59454b2a9f5f6712b7297cb1/render_log.json
durable state key: render_state/render_jobs/render_c2da574a59454b2a9f5f6712b7297cb1.json
idempotency index key: render_state/idempotency/042e72db67386a783a7e8b1e0da000df6a99943f7a2e17c67fbf08bcb4ffcf67.json
```

ffprobe summary:

```json
{
  "format": {
    "duration": "18.422005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "447996"
  },
  "video": {
    "codec_name": "h264",
    "width": 720,
    "height": 1280,
    "pix_fmt": "yuv420p",
    "r_frame_rate": "30/1"
  },
  "audio": {
    "codec_name": "aac"
  }
}
```

Retention metadata existed in the render response and render log:

```text
retentionClass: free_final_render
deleteEligible: true
planTier: free
templateId: personal_highlight_v1
expiresAt: 2026-05-18T03:57:42.260946+00:00
outputBytes: 447996
durationSeconds: 18.422
```

Policy rejection was also verified before any render started:

```text
errorCode: render_duration_limit
httpStatus: 400
failureReason: Requested AI edit length exceeds this plan's render limit.
```

## Revision Render Smoke

Revision command:

```text
make_more_hype
```

Result:

```text
revisionId: rev_bb38bee369ca46dca8558be7350d1917
revision renderJobId: render_d5379ea5e0294ee9963bbeb37ac3f05b
validationResult.valid: true
status: rendered
```

Output:

```text
final object key: edits/edit_db9ab36166ad4246b19303ed10f4d096/render_jobs/render_d5379ea5e0294ee9963bbeb37ac3f05b/final.mp4
render log key: edits/edit_db9ab36166ad4246b19303ed10f4d096/render_jobs/render_d5379ea5e0294ee9963bbeb37ac3f05b/render_log.json
durable state key: render_state/render_jobs/render_d5379ea5e0294ee9963bbeb37ac3f05b.json
```

ffprobe summary:

```json
{
  "format": {
    "duration": "18.422005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "440560"
  },
  "video": {
    "codec_name": "h264",
    "width": 720,
    "height": 1280,
    "pix_fmt": "yuv420p",
    "r_frame_rate": "30/1"
  },
  "audio": {
    "codec_name": "aac"
  }
}
```

## Durable State Metadata Proof

The normal render durable record contained the required durable fields:

```json
{
  "renderJobId": "render_c2da574a59454b2a9f5f6712b7297cb1",
  "editJobId": "edit_db9ab36166ad4246b19303ed10f4d096",
  "revisionId": null,
  "idempotencyKey": "edit_db9ab36166ad4246b19303ed10f4d096-phase6b-render",
  "status": "rendered",
  "planVersion": "edit-plan-v1",
  "templateId": "personal_highlight_v1",
  "planTier": "free",
  "sourceObjectKey": "uploads/dea8748f1ab04417b0167a844cbaeebb/source.mp4",
  "outputObjectKey": "edits/edit_db9ab36166ad4246b19303ed10f4d096/render_jobs/render_c2da574a59454b2a9f5f6712b7297cb1/final.mp4",
  "renderLogObjectKey": "edits/edit_db9ab36166ad4246b19303ed10f4d096/render_jobs/render_c2da574a59454b2a9f5f6712b7297cb1/render_log.json",
  "createdAt": "2026-05-04T03:57:27.102867+00:00",
  "startedAt": "2026-05-04T03:57:29.043233+00:00",
  "completedAt": "2026-05-04T03:57:43.152100+00:00",
  "expiresAt": "2026-05-18T03:57:42.260946+00:00",
  "failureReason": null,
  "retryCount": 0,
  "rendererVersion": "ffmpeg-renderer-v1",
  "outputBytes": 447996,
  "durationSeconds": 18.422
}
```

The revision durable record contained the same required fields plus:

```text
revisionId: rev_bb38bee369ca46dca8558be7350d1917
idempotencyKey: edit_db9ab36166ad4246b19303ed10f4d096-rev_bb38bee369ca46dca8558be7350d1917-phase6b-revision-render
status: rendered
outputBytes: 440560
durationSeconds: 18.422
```

The latest-edit index pointed at the revision render:

```json
{
  "version": "render-state-index-v1",
  "editJobId": "edit_db9ab36166ad4246b19303ed10f4d096",
  "renderJobId": "render_d5379ea5e0294ee9963bbeb37ac3f05b",
  "revisionId": "rev_bb38bee369ca46dca8558be7350d1917"
}
```

The idempotency index pointed at the original render:

```json
{
  "version": "render-state-idempotency-v1",
  "editJobId": "edit_db9ab36166ad4246b19303ed10f4d096",
  "renderJobId": "render_c2da574a59454b2a9f5f6712b7297cb1",
  "revisionId": null
}
```

## Durable State Reload Proof

After the normal and revision renders completed, the editing service was updated with a harmless marker env var to force a new Cloud Run revision and clear warm process memory:

```text
HOOPS_DURABLE_RELOAD_PROOF=phase7a1-20260503T205905
new revision: hoopclips-editing-staging-00018-5nx
traffic: 100 percent to latest revision
gitSha after reload: 7650c88
```

Post-reload Worker checks:

```text
GET /v1/edit-jobs/edit_db9ab36166ad4246b19303ed10f4d096/render-status
status: rendered
renderJobId: render_d5379ea5e0294ee9963bbeb37ac3f05b
revisionId: rev_bb38bee369ca46dca8558be7350d1917

GET /v1/edit-jobs/edit_db9ab36166ad4246b19303ed10f4d096/download-url
outputObjectKey: edits/edit_db9ab36166ad4246b19303ed10f4d096/render_jobs/render_d5379ea5e0294ee9963bbeb37ac3f05b/final.mp4
download: success
ffprobe: pass
```

Post-reload ffprobe summary:

```json
{
  "format": {
    "duration": "18.422005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "440560"
  },
  "video": {
    "codec_name": "h264",
    "width": 720,
    "height": 1280,
    "pix_fmt": "yuv420p",
    "r_frame_rate": "30/1"
  },
  "audio": {
    "codec_name": "aac"
  }
}
```

This proves latest render status and download-url survived a fresh Cloud Run revision and did not depend only on process memory.

## Failed Timeout Smoke

A staging-only R2 fixture was created under a synthetic edit/render id to avoid changing product code or adding public debug routes.

Fixture:

```text
editJobId: edit_phase7a1_stale_20260504040036
renderJobId: render_phase7a1_stale_20260504040036
installId: smoke-durable-stale-20260504040036
initial durable status: rendering
initial updatedAt: 2026-05-04T03:30:36.342354+00:00
```

Fixture keys:

```text
render_state/render_jobs/render_phase7a1_stale_20260504040036.json
render_state/edit_jobs/edit_phase7a1_stale_20260504040036/latest.json
```

Worker status check:

```text
GET /v1/edit-jobs/edit_phase7a1_stale_20260504040036/render-status
status: failed_timeout
failureReason: failed_timeout
renderLogObjectKey: edits/edit_phase7a1_stale_20260504040036/render_jobs/render_phase7a1_stale_20260504040036/render_log.json
```

Updated durable state and render log:

```text
status: failed_timeout
failureReason: failed_timeout
retentionClass: free_failed_render
deleteEligible: true
expiresAt: 2026-05-11T04:00:52.854275+00:00
```

Cloud Run emitted a safe structured log:

```json
{
  "event": "render.failed",
  "editJobId": "edit_phase7a1_stale_20260504040036",
  "renderJobId": "render_phase7a1_stale_20260504040036",
  "planTier": "free",
  "failureReason": "failed_timeout"
}
```

## Observability and URL Safety

Observed safe events:

```text
render.completed
download_url.created
policy.failed
render.failed
```

Observed event fields were IDs and safe metadata only:

```text
editJobId
renderJobId
templateId
planTier
failureReason
rendererVersion
durationSeconds
outputBytes
```

The smoke commands and captured summaries did not print secret values, R2 credentials, or full presigned download URLs.

## CI Deploy Token Note

Manual staging verification used local Wrangler OAuth. CI still needs:

```text
CLOUDFLARE_API_TOKEN
```

Required token capabilities should cover:

```text
Workers Scripts write
Workers Tail read if CI smoke tails logs
D1 write if migrations run from CI
R2 read/write if smoke scripts fetch or verify objects
Queues write/read if deploy workflows validate queue bindings
```

Store it as a CI secret, not in repo files or plaintext vars. The Worker deploy step that needs it is:

```bash
cd services/control-plane
npx wrangler deploy --env staging
```

## Validation

Commands run:

```text
git diff --check
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
npm --prefix services/control-plane run typecheck
cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-phase7a1-xcodebuild build CODE_SIGNING_ALLOWED=NO
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-phase7a1-xcodebuild build-for-testing CODE_SIGNING_ALLOWED=NO
```

Results:

```text
git diff --check: pass
editing service unittest: 20 tests OK
control-plane typecheck: pass
control-plane proxy tests: 6 pass
iOS Debug simulator build: BUILD SUCCEEDED
iOS build-for-testing: TEST BUILD SUCCEEDED
```

Note: the first editing test attempt used the system Python and failed because `fastapi` was not installed there. The repo virtualenv run above is the valid project test result.

Live verification completed:

```text
Cloud Run deploy: pass
/readyz: pass
/version gitSha=7650c88: pass
normal Worker -> Cloud Run -> R2 render: pass
duplicate render idempotency before reload: pass
revision render: pass
policy rejection: pass
durable state R2 metadata: pass
status/download after Cloud Run reload: pass
failed_timeout fixture: pass
```

## Remaining Beta Blockers

- Keep `max-instances=1` until a queue or lease-based active render lock lands and has its own load smoke.
- Revision definitions/edit-plan revision state are still not independently durable; rendered revision jobs are durable, but recreating a revision render after a service restart requires the render idempotency path or a persisted revised plan.
- CI still needs `CLOUDFLARE_API_TOKEN` plus GCP deploy identity wiring.
- A cleanup worker or lifecycle policy for old `final.mp4`, `render_log.json`, and `render_state/*.json` objects is still needed before broad beta.

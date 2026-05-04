# Phase Edit7a1 Live Durable Render Smoke

Date: 2026-05-04 UTC

Branch:

```text
codex/phase-edit7a1-live-durable-render-smoke
```

Deployed code:

```text
base commit: 7650c88
image: us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:7650c88
```

## Goal

Prove the Phase Edit7a durable render state changes through the real staging path:

```text
Worker -> Cloud Run editing service -> FFmpeg -> R2 final.mp4/render_log.json
```

The smoke specifically verified that rendered status, output keys, idempotency, and download URLs survive beyond in-memory process state.

## Staging Deployment

Cloud Build:

```text
build id: ccfef7bd-8e8d-41de-b246-79dddccc7b8c
status: SUCCESS
```

Cloud Run service:

```text
project: hoopsclips-9d38f
region: us-central1
service: hoopclips-editing-staging
initial deployed revision: hoopclips-editing-staging-00015-6s6
current active revision after reload proof: hoopclips-editing-staging-00017-ghd
traffic: 100 percent to latest revision
```

Cloud Run guardrails remained enabled:

```text
autoscaling.knative.dev/maxScale: 1
run.googleapis.com/cpu-throttling: false
```

Service checks:

```text
/readyz: 200
/version: 200
gitSha: 7650c88
ffmpegAvailable: true
ffprobeAvailable: true
renderStorage.provider: r2
renderStorage.providerReady: true
```

Note: `/healthz` still returns the previously documented Cloud Run frontend 404 in staging. `/readyz` and `/version` remain the reliable deployed-service checks.

Active Worker:

```text
url: https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
latest observed deployed Worker version: 3dc0312f-9043-4762-b8c1-dfd46f0a0ad1
```

## Normal Render Smoke

Command:

```bash
PYTHONPATH=services/editing/scripts ios/backend/.venv/bin/python \
  services/editing/scripts/policy_observability_smoke.py \
  --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --editing-url https://hoopclips-editing-staging-npya43jiia-uc.a.run.app \
  --install-id phase-edit7a1-durable-1777866733 \
  --trace-id-prefix phase-edit7a1-durable \
  --timeout-seconds 480
```

Result:

```text
status: pass
editJobId: edit_c67e841a108b4d2e879bf98fe603f7fb
renderJobId: render_d4c9359f05cb43a9897f121058dc058f
duplicateRenderJobId: render_d4c9359f05cb43a9897f121058dc058f
duplicateBehavior: idempotent_existing_render_returned
templateId: personal_highlight_v1
planTier: free
```

Output:

```text
sourceObjectKey: uploads/f5a642df6ead4946a4248bc2aaf5c81a/source.mp4
final object key: edits/edit_c67e841a108b4d2e879bf98fe603f7fb/render_jobs/render_d4c9359f05cb43a9897f121058dc058f/final.mp4
render log key: edits/edit_c67e841a108b4d2e879bf98fe603f7fb/render_jobs/render_d4c9359f05cb43a9897f121058dc058f/render_log.json
durable state key: render_state/render_jobs/render_d4c9359f05cb43a9897f121058dc058f.json
```

ffprobe summary:

```json
{
  "format": {
    "duration": "18.422005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "447331"
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
expiresAt: 2026-05-18T03:52:37.490313+00:00
outputBytes: 447331
durationSeconds: 18.422
```

## Revision Render Smoke

Revision command:

```text
make_more_hype
```

Result:

```text
revisionId: rev_2b585764236541d59f4e8f088037bf41
revision renderJobId: render_795b7175134042569653cddff93f20f0
validationResult.valid: true
status: rendered
```

Output:

```text
final object key: edits/edit_c67e841a108b4d2e879bf98fe603f7fb/render_jobs/render_795b7175134042569653cddff93f20f0/final.mp4
render log key: edits/edit_c67e841a108b4d2e879bf98fe603f7fb/render_jobs/render_795b7175134042569653cddff93f20f0/render_log.json
durable state key: render_state/render_jobs/render_795b7175134042569653cddff93f20f0.json
```

ffprobe summary:

```json
{
  "format": {
    "duration": "18.422005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "441711"
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

The normal render durable record contained:

```json
{
  "renderJobId": "render_d4c9359f05cb43a9897f121058dc058f",
  "editJobId": "edit_c67e841a108b4d2e879bf98fe603f7fb",
  "revisionId": null,
  "idempotencyKey": "edit_c67e841a108b4d2e879bf98fe603f7fb-phase6b-render",
  "status": "rendered",
  "planVersion": "edit-plan-v1",
  "templateId": "personal_highlight_v1",
  "planTier": "free",
  "sourceObjectKey": "uploads/f5a642df6ead4946a4248bc2aaf5c81a/source.mp4",
  "outputObjectKey": "edits/edit_c67e841a108b4d2e879bf98fe603f7fb/render_jobs/render_d4c9359f05cb43a9897f121058dc058f/final.mp4",
  "renderLogObjectKey": "edits/edit_c67e841a108b4d2e879bf98fe603f7fb/render_jobs/render_d4c9359f05cb43a9897f121058dc058f/render_log.json",
  "createdAt": "2026-05-04T03:52:20.555982+00:00",
  "startedAt": "2026-05-04T03:52:22.553229+00:00",
  "completedAt": "2026-05-04T03:52:38.478101+00:00",
  "expiresAt": "2026-05-18T03:52:37.490313+00:00",
  "failureReason": null,
  "retryCount": 0,
  "rendererVersion": "ffmpeg-renderer-v1",
  "outputBytes": 447331,
  "durationSeconds": 18.422
}
```

The revision render durable record contained the same required fields plus:

```text
revisionId: rev_2b585764236541d59f4e8f088037bf41
idempotencyKey: edit_c67e841a108b4d2e879bf98fe603f7fb-rev_2b585764236541d59f4e8f088037bf41-phase6b-revision-render
retryCount: 1
```

## Durable State Reload Proof

After the successful normal and revision renders, the editing service was redeployed with the same image to force a fresh Cloud Run revision and clear in-process state.

Reload revision:

```text
current active revision after redeploy: hoopclips-editing-staging-00017-ghd
image digest: us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging@sha256:7b45814b387312bf249ae5369ba71db6c6926150f2e122d55f140ce0bbb45539
```

Post-redeploy Worker checks:

```text
GET /v1/edit-jobs/edit_c67e841a108b4d2e879bf98fe603f7fb/render-status
status: rendered
renderJobId: render_795b7175134042569653cddff93f20f0

GET /v1/edit-jobs/edit_c67e841a108b4d2e879bf98fe603f7fb/download-url
outputObjectKey: edits/edit_c67e841a108b4d2e879bf98fe603f7fb/render_jobs/render_795b7175134042569653cddff93f20f0/final.mp4
download: success
ffprobe: pass
```

Post-redeploy ffprobe summary:

```json
{
  "format": {
    "duration": "18.422005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "441711"
  },
  "video": {
    "codec_name": "h264",
    "width": 720,
    "height": 1280,
    "pix_fmt": "yuv420p",
    "r_frame_rate": "30/1"
  },
  "audio": {
    "codec_name": "aac",
    "sample_rate": "44100",
    "channels": 1
  }
}
```

Post-redeploy duplicate idempotency check:

```text
POST /v1/edit-jobs/edit_c67e841a108b4d2e879bf98fe603f7fb/render
idempotencyKey: edit_c67e841a108b4d2e879bf98fe603f7fb-phase6b-render
returned renderJobId: render_d4c9359f05cb43a9897f121058dc058f
status: rendered
```

This proves duplicate render idempotency survived a fresh Cloud Run revision and did not rely only on process memory.

## Failed Timeout Smoke

A staging-only R2 fixture was created under a synthetic edit/render id to avoid changing product code or adding public debug routes.

Fixture:

```text
editJobId: edit_phase7a1_stale_1777867060
renderJobId: render_phase7a1_stale_1777867060
installId: phase-edit7a1-stale-fixture
initial durable status: rendering
initial updatedAt: older than staleRenderTimeoutSeconds
```

Fixture keys:

```text
render_state/render_jobs/render_phase7a1_stale_1777867060.json
render_state/edit_jobs/edit_phase7a1_stale_1777867060/latest.json
```

Worker status check:

```text
GET /v1/edit-jobs/edit_phase7a1_stale_1777867060/render-status
status: failed_timeout
failureReason: failed_timeout
renderLogObjectKey: edits/edit_phase7a1_stale_1777867060/render_jobs/render_phase7a1_stale_1777867060/render_log.json
```

Updated durable state:

```text
status: failed_timeout
failureReason: failed_timeout
retentionClass: free_failed_render
deleteEligible: true
expiresAt: 2026-05-11T03:58:21.873926+00:00
```

Cloud Run structured log also emitted:

```json
{
  "event": "render.failed",
  "editJobId": "edit_phase7a1_stale_1777867060",
  "renderJobId": "render_phase7a1_stale_1777867060",
  "planTier": "free",
  "failureReason": "failed_timeout"
}
```

## Observability and URL Safety

Cloud Run logs contained safe structured events:

```text
render.completed
download_url.created
policy.failed
render.failed
```

Observed event fields included safe ids and metadata:

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

No secret values, R2 credentials, or full presigned download URLs were printed by the smoke commands or captured summaries.

Local observability environment:

```text
SENTRY_AUTH_TOKEN: missing
STATSIG_SERVER_SECRET: missing
CLOUDFLARE_API_TOKEN: missing
```

Wrangler OAuth was available locally and was used for manual staging verification. CI still needs `CLOUDFLARE_API_TOKEN` for repeatable Worker automation.

## CI Deploy Token Note

CI still needs:

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

Live verification completed:

```text
Cloud Run deploy: success
/readyz: 200
/version: 200, gitSha=7650c88
normal Worker -> Cloud Run -> R2 render: pass
duplicate render idempotency before reload: pass
revision render: pass
policy rejection: pass
durable state R2 metadata: pass
status/download after Cloud Run redeploy: pass
duplicate idempotency after Cloud Run redeploy: pass
failed_timeout fixture: pass
```

## Remaining Beta Blockers

- Keep `max-instances=1` until a queue or lease-based active render lock lands.
- Revision definitions/edit-plan revision state are still not independently durable; rendered revision jobs are durable, but recreating a revision render after a service restart requires the render idempotency path or a persisted revised plan.
- CI still needs `CLOUDFLARE_API_TOKEN` plus GCP deploy identity wiring.
- A real cleanup worker/lifecycle policy for old `final.mp4`, `render_log.json`, and `render_state/*.json` objects is still needed before broad beta.

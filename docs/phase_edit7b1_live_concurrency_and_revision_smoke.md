# Phase Edit7b1 Live Concurrency And Revision Smoke

Date: 2026-05-04 UTC

Branch:

```text
codex/phase-edit7b1-live-concurrency-and-revision-smoke
```

Base commit deployed:

```text
4a2d1dc
```

Goal:

```text
Deploy and verify the Phase Edit7b render lease/revision-persistence changes through:
Worker -> Cloud Run editing service -> durable render state -> R2 final.mp4/render_log.json.
```

This phase did not add product features, templates, iOS rendering, or renderer architecture changes. It deployed the existing Phase Edit7b editing service, ran a live Worker-path render/revision smoke, forced a same-image Cloud Run reload, verified durable status/revision reads after reload, and ran R2 retention cleanup in dry-run mode only.

## Staging Deploy

Cloud Build:

```text
build id: a4526c12-a0c4-40c4-92a8-74a4f0a5954a
status: SUCCESS
image: us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopclips-editing-staging:4a2d1dc
digest: sha256:fa65fc4bcdf988633aa6b70f78f0b29597a98ac28c1df2b469798ab1df274f47
```

Cloud Run service:

```text
project: hoopsclips-9d38f
region: us-central1
service: hoopclips-editing-staging
deployed revision: hoopclips-editing-staging-00020-q7r
reload-proof revision: hoopclips-editing-staging-00021-gcj
traffic: 100 percent to latest revision
service URL: https://hoopclips-editing-staging-npya43jiia-uc.a.run.app
```

Cloud Run guardrails remained enabled:

```text
autoscaling.knative.dev/maxScale: 1
run.googleapis.com/cpu-throttling: false
HOOPS_GIT_SHA: 4a2d1dc
```

Service checks:

```text
/version: 200
/readyz: 200
/healthz: 404
```

`/version` confirmed `gitSha=4a2d1dc`, FFmpeg and ffprobe available, and feature flags loaded with safe defaults. `/readyz` confirmed staging auth and R2 storage were configured. `/healthz` still returns the previously observed Cloud Run frontend 404 in staging, so `/readyz` and `/version` remain the reliable health checks for this service.

Active Worker URL used for smoke:

```text
https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev
```

Wrangler/Worker version lookup remained blocked by local Cloudflare auth:

```text
CLOUDFLARE_API_TOKEN is not set and local Wrangler OAuth is not valid.
wrangler whoami -> 401 Unauthorized / Not logged in
```

No token values were printed.

## Live Worker Render Smoke

Input:

```text
templateId: personal_highlight_v1
preset: personal_highlight
targetDurationSeconds: 30
aspectRatio: 9:16
planTier: free
```

Result:

```text
status: pass
editJobId: edit_662804df03af4736b3d887a99b7a5fdc
renderJobId: render_3ff2993db17a4778a62735bfe9ee43ef
duplicateRenderJobId: render_3ff2993db17a4778a62735bfe9ee43ef
duplicateBehavior: same_render_job_returned
```

Output:

```text
sourceObjectKey: uploads/f2c9a299a7f0436aab967e853746fb74/source.mp4
final object key: edits/edit_662804df03af4736b3d887a99b7a5fdc/render_jobs/render_3ff2993db17a4778a62735bfe9ee43ef/final.mp4
render log key: edits/edit_662804df03af4736b3d887a99b7a5fdc/render_jobs/render_3ff2993db17a4778a62735bfe9ee43ef/render_log.json
durable state key: render_state/render_jobs/render_3ff2993db17a4778a62735bfe9ee43ef.json
```

ffprobe summary:

```json
{
  "format": {
    "duration": "18.422005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "447848"
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

Durable state included:

```text
status: rendered
templateId: personal_highlight_v1
planTier: free
planVersion: edit-plan-v1
outputBytes: 447848
durationSeconds: 18.422
retryCount: 0
rendererVersion: ffmpeg-renderer-v1
leaseOwner: present
leaseToken: present
leaseAcquiredAt: 2026-05-04T16:15:06.159611+00:00
leaseExpiresAt: 2026-05-04T16:30:06.159611+00:00
heartbeatAt: 2026-05-04T16:15:21.243343+00:00
```

Retention metadata included:

```text
retentionClass: free_final_render
deleteEligible: true
expiresAt: 2026-05-18T16:15:20.251545+00:00
planTier: free
templateId: personal_highlight_v1
outputBytes: 447848
durationSeconds: 18.422
```

Cloud Run structured logs showed safe events for the base render:

```text
render.requested
render.lease_acquired
render.started
render.completed
download_url.created
```

No secret values or full presigned download URLs were logged.

## Revision Persistence Smoke

Revision command:

```text
make_more_hype
```

Result:

```text
revisionId: rev_c768043d43f34e7d9fb4fecde33984f2
revisedPlanId: edit_662804df03af4736b3d887a99b7a5fdc:rev_c768043d43f34e7d9fb4fecde33984f2
revision status before render: revision_ready
revision list count before render: 1
renderJobId: render_f886961dbd8942829dcd42d4faf14d1a
status: rendered
```

Persisted objects:

```text
revision definition: edits/edit_662804df03af4736b3d887a99b7a5fdc/revisions/rev_c768043d43f34e7d9fb4fecde33984f2.json
revised plan: edits/edit_662804df03af4736b3d887a99b7a5fdc/plans/edit_662804df03af4736b3d887a99b7a5fdc:rev_c768043d43f34e7d9fb4fecde33984f2.json
revision final object key: edits/edit_662804df03af4736b3d887a99b7a5fdc/render_jobs/render_f886961dbd8942829dcd42d4faf14d1a/final.mp4
revision render log key: edits/edit_662804df03af4736b3d887a99b7a5fdc/render_jobs/render_f886961dbd8942829dcd42d4faf14d1a/render_log.json
revision durable state key: render_state/render_jobs/render_f886961dbd8942829dcd42d4faf14d1a.json
```

Revision ffprobe summary:

```json
{
  "format": {
    "duration": "18.422005",
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "size": "440541"
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

Revision durable state included:

```text
status: rendered
revisionId: rev_c768043d43f34e7d9fb4fecde33984f2
templateId: personal_highlight_v1
planTier: free
outputBytes: 440541
durationSeconds: 18.422
retryCount: 1
rendererVersion: ffmpeg-renderer-v1
leaseOwner: present
leaseToken: present
```

The revision render log included the same `revisionId` and `personal_highlight_v1` template signature.

## Durable Read After Reload

After the base and revision renders completed, Cloud Run was updated with a same-image env marker:

```text
HOOPS_DURABLE_RELOAD_PROOF=phase7b1-20260504T161600Z
```

This created revision:

```text
hoopclips-editing-staging-00021-gcj
```

After the reload, the Worker successfully:

```text
GET /v1/edit-jobs/{editJobId}/render-status
GET /v1/edit-jobs/{editJobId}/revisions/{revisionId}
GET /v1/edit-jobs/{editJobId}/revisions
GET /v1/edit-jobs/{editJobId}/download-url
```

Post-reload proof:

```text
status: pass
editJobId: edit_662804df03af4736b3d887a99b7a5fdc
revisionId: rev_c768043d43f34e7d9fb4fecde33984f2
renderJobId: render_f886961dbd8942829dcd42d4faf14d1a
downloadObjectKey: edits/edit_662804df03af4736b3d887a99b7a5fdc/render_jobs/render_f886961dbd8942829dcd42d4faf14d1a/final.mp4
revisionListCount: 1
```

The post-reload MP4 downloaded and ffprobe passed with the same 720x1280 H.264/AAC profile.

## Lease Safety Proof

Live proof:

- duplicate base render request returned the same `renderJobId`
- durable state carried lease fields through terminal `rendered` state
- Cloud Run logs emitted `render.lease_acquired`
- terminal render logs and state were not overwritten by the duplicate request

Unit/staging-fixture proof from Phase Edit7b remains the evidence for wrong-token completion, expired lease reclaim, and stale-worker overwrite rejection:

- two workers attempting the same render
- duplicate request while render active
- expired lease reclaimed
- completion attempt with wrong lease token rejected
- rendered job cannot be overwritten by stale worker

No staging-only debug route exists for forcing wrong lease tokens live, so this branch did not add one. That keeps live staging product-surface unchanged.

## Cleanup Dry-Run

Command shape:

```bash
python services/editing/scripts/render_retention_cleanup.py \
  --render-storage-provider r2 \
  --retention-class free_final_render \
  --now 2036-01-01T00:00:00+00:00
```

The future cutoff was intentional so staging metadata would produce candidates without deleting anything.

Result:

```text
mode: dry-run
candidateCount: 8
objectKeyCount: 24
deletedObjectKeys: 0
estimatedOutputBytes: 3561533
candidatesWithOutputBytes: 8
```

The cleanup dry-run reported object keys only. No presigned URLs, R2 credentials, or secret values were logged.

## Scaling Test

Cloud Run was not raised to `max-instances=2` in this branch.

Current state remains:

```text
autoscaling.knative.dev/maxScale: 1
```

Before raising to 2+:

- run a controlled staging multi-instance duplicate render smoke
- confirm leases prevent double execution under actual Cloud Run concurrency
- confirm observability shows only one render execution for one edit/revision/idempotency key
- keep rollback command ready

## CI Deploy Readiness

Phase Edit7b added the deploy preflight workflow and docs. Phase Edit7b1 re-ran the local preflight and confirmed the remaining automation blocker:

```text
CLOUDFLARE_API_TOKEN is not set and local Wrangler OAuth is not valid.
```

Required CI secrets/identities remain:

- `CLOUDFLARE_API_TOKEN`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`
- `GCP_PROJECT_ID`
- `GCP_REGION`

Required Cloudflare token scope:

- Workers Scripts Edit
- Workers Tail Read, optional
- R2 Read/Write if CI verifies render artifacts

Required GCP access:

- Cloud Build submit permission
- Artifact Registry access
- Cloud Run deploy permission
- Secret Manager access for deploy-time secret wiring
- Service Account User on the Cloud Run runtime service account if applicable

## Validation

Passed:

```text
git diff --check
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service
npm --prefix services/control-plane run typecheck
cd services/control-plane && npx tsx --test test/control-plane-editing-proxy.test.ts
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build CODE_SIGNING_ALLOWED=NO -derivedDataPath /tmp/hoopclips-phase7b1-build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' build-for-testing CODE_SIGNING_ALLOWED=NO -derivedDataPath /tmp/hoopclips-phase7b1-build-for-testing
```

Focused live smoke passed:

```text
Worker -> Cloud Run -> R2 normal render
duplicate render idempotency
More Hype revision creation
revision render
R2 durable state read
revision definition read
revised plan read
post-reload render status/download/revision read
cleanup dry-run
```

## Notes

The first verifier run attempted an immediate R2 durable-state read after the API returned `rendered` and hit a transient `NoSuchKey`; the expected R2 durable state object appeared seconds later. The successful verifier used bounded R2 read retries. This is a smoke-harness timing note, not a product API failure, because post-reload Worker status/download reads and direct R2 durable reads passed.

## Remaining Beta Blockers

- install `CLOUDFLARE_API_TOKEN` for CI/Worker deploy automation
- run a controlled `max-instances=2` staging race before raising Cloud Run scale
- add destructive R2 cleanup execution only after dry-run policy is reviewed
- decide whether render dispatch should eventually move to Cloud Tasks, Pub/Sub, Durable Objects, or another queue before broader beta load

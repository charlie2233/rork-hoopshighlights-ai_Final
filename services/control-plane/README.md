# HoopsClips Control Plane

This package is the Cloudflare control plane scaffold for HoopsClips.

## What lives here

- Public iOS job API preserved additively at `/v1/analysis/jobs`
- Internal callback and heartbeat routes for the inference service
- Admin route stubs for the future review dashboard
- Durable Object job state
- D1 metadata index
- Queue orchestration stub
- R2 presign abstraction

## Happy Path

The runnable happy path is documented in [`docs/control_plane_happy_path.md`](../../docs/control_plane_happy_path.md).
The live staging deploy and smoke flow are documented in [`docs/staging_smoke_runbook.md`](../../docs/staging_smoke_runbook.md).

Quick local check:

```bash
npm --prefix services/control-plane install
npx tsx scripts/control-plane-happy-path.ts
```

Focused checks:

```bash
npx tsx --test services/control-plane/test/control-plane-status-transitions.test.ts
npx tsx --test services/control-plane/test/control-plane-failure-path.test.ts
npx tsx --test services/control-plane/test/control-plane-duplicate-callback.test.ts
npx tsx --test services/control-plane/test/control-plane-dlq.test.ts
```

The phase-1b verification path now uses the staging route shape end to end:

- `POST /uploads/presign`
- direct upload to the signed R2 URL
- `POST /jobs`
- queue-driven stub inference
- internal completion callback
- `GET /jobs/:id`

## Runtime shape

- `R2_UPLOADS` stores source uploads
- `R2_RESULTS` stores normalized result manifests and derived artifacts
- `JOB_STATE` is the per-job Durable Object
- `DB` is the D1 secondary index
- `ANALYSIS_QUEUE` dispatches work to the inference plane

## Local setup

1. Install dependencies.
2. Put secret values into Wrangler secrets rather than source control.
3. Run `wrangler dev` from this directory.

Required env/secret inputs:

- `ADMIN_API_TOKEN`
- `CONTROL_PLANE_BASE_URL`
- `CONTROL_PLANE_SHARED_SECRET`
- `INFERENCE_SHARED_SECRET`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

`INFERENCE_BASE_URL` remains reserved for the later dedicated inference service and is not required for the phase-1b stub staging path.

For the exact local/staging variable mapping and Wrangler secret commands, see [`docs/cloudflare_env_setup.md`](../../docs/cloudflare_env_setup.md).

## Staging deploy

1. Create or verify the Cloudflare resources with [`docs/staging_smoke_runbook.md`](../../docs/staging_smoke_runbook.md).
2. Run `npx wrangler deploy --env staging` from `services/control-plane`.
3. Use the printed staging Worker URL with a real sample MP4 file, for example `npx tsx scripts/control-plane-happy-path.ts --base-url https://<staging-worker-url> --file /tmp/hoopsclips-staging-sample.mp4 --trace-id staging-smoke-001`.

## Migration notes

- The current implementation is a scaffold, not the final production control plane.
- The public job contract remains backwards compatible at the response-field level.
- The next phase is replacing the scaffolded queue dispatch and result hydration with real R2/Durable Object/D1 backed production flows.

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

Quick local check:

```bash
npm --prefix services/control-plane install
npx tsx scripts/control-plane-happy-path.ts
```

Focused checks:

```bash
npx tsx --test services/control-plane/test/control-plane-status-transitions.test.ts
npx tsx --test services/control-plane/test/control-plane-failure-path.test.ts
```

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
- `CONTROL_PLANE_SHARED_SECRET`
- `INFERENCE_BASE_URL`
- `INFERENCE_SHARED_SECRET`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

For the exact local/staging variable mapping and Wrangler secret commands, see [`docs/cloudflare_env_setup.md`](../../docs/cloudflare_env_setup.md).

## Migration notes

- The current implementation is a scaffold, not the final production control plane.
- The public job contract remains backwards compatible at the response-field level.
- The next phase is replacing the scaffolded queue dispatch and result hydration with real R2/Durable Object/D1 backed production flows.

# HoopsClips Control Plane

This package is the Cloudflare control plane scaffold for HoopsClips.

## What lives here

- Public iOS job API preserved additively at `/v1/analysis/jobs`
- Internal callback and heartbeat routes for the inference service
- Admin route stubs for the future review dashboard
- Durable Object job state
- D1 metadata index
- Queue orchestration to the external inference service
- R2 presign abstraction

## Local Checks

```bash
npm --prefix services/control-plane ci
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
npm --prefix services/control-plane run deploy:staging:dry-run
```

Focused checks:

```bash
npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-editing-proxy.test.ts
npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-status-transitions.test.ts
npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-failure-path.test.ts
npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-duplicate-callback.test.ts
npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-dlq.test.ts
python3 scripts/launch_backend_config_preflight.py
```

The workflow dry-run and launch preflight are static and no-secret. They validate staging Worker bindings and backend config contracts without deploying, printing credentials, or printing presigned URLs. See [`docs/phase_launch2_ci_deploy_token_unblock.md`](../../docs/phase_launch2_ci_deploy_token_unblock.md) and [`docs/phase_launch2_main_deploy_workflow_handoff.md`](../../docs/phase_launch2_main_deploy_workflow_handoff.md) for current deploy-token evidence.

The phase-1b verification path now uses the staging route shape end to end:

- `POST /uploads/presign`
- direct upload to the signed R2 URL
- `POST /jobs`
- queue-driven external inference dispatch
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
- `INFERENCE_BASE_URL`
- `INFERENCE_SHARED_SECRET`
- `EDITING_BASE_URL`
- `EDITING_SHARED_SECRET`
- `PROCESSING_TIMEOUT_SECONDS`
- `MAX_INFERENCE_ATTEMPTS`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

For the exact local/staging variable mapping and Wrangler secret commands, see [`docs/cloudflare_env_setup.md`](../../docs/cloudflare_env_setup.md).

## Staging deploy

1. Create or verify Cloudflare resources using the phase launch evidence docs.
2. Validate the Worker bundle and staging bindings without deploying:

```bash
npm --prefix services/control-plane run deploy:staging:dry-run
```

3. Deploy staging with a preserved dashboard-var posture:

```bash
npm --prefix services/control-plane run deploy:staging -- --message "staging deploy <git-sha>"
```

4. List rollback targets before rollback:

```bash
npm --prefix services/control-plane run deployments:staging
npm --prefix services/control-plane run rollback:staging -- <version-id> --message "rollback <git-sha>"
```

5. Use the printed staging Worker URL with a real sample MP4 file through the launch smoke path documented in the phase launch evidence docs.

## Migration notes

- The current implementation dispatches to a dedicated external inference service instead of running stub inference in the queue consumer.
- The public job contract remains backwards compatible at the response-field level.
- The next phase is deploying the production inference service and removing the last local/test-only dispatch shims.

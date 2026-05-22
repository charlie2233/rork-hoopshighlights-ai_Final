# Phase Launch2 CI Deploy Token Audit

Date: 2026-05-22
Branch: `codex/phase-launch2-ci-deploy-token-audit`
Base: `codex/phase-ux4-cloud-locker-hardening` at `810aa26`

## Result

CI deploy automation is still blocked. The Worker dry-run and repo config checks pass locally, but the GitHub `staging` environment does not currently expose the required secret or variable names, and the deploy workflow is not available on the default branch yet.

No secrets, token values, R2 credentials, or presigned URLs were printed.

## Evidence

Commands run from `/Users/hanfei/rork-hoopshighlights-ai_Final`.

```bash
test -n "${CLOUDFLARE_API_TOKEN:-}"
```

Result: local `CLOUDFLARE_API_TOKEN=missing`.

```bash
python3 scripts/launch_backend_config_preflight.py
```

Result: `pass=57 warn=12 fail=0`.

Important warnings still present:

- Production Worker cutover is intentionally absent.
- Top-level Worker D1/R2 config is placeholder-only; internal beta should use `env.staging`.
- Editing backend Sentry DSN, Statsig remote flag source, and RevenueCat REST verifier remain production/internal-beta configuration gates.
- Launch docs still record missing CI deploy credential proof.

```bash
npm --prefix services/control-plane exec -- wrangler --version
```

Result: `4.78.0`.

```bash
npm --prefix services/control-plane run deploy:staging:dry-run
```

Result: staging Worker bundle dry-run succeeded and exited before upload/deploy. Wrangler printed staging bindings for Durable Object, queues, D1, R2 buckets, and non-secret environment variables only.

```bash
gh secret list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt
```

Result: `[]`.

```bash
gh variable list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,value,updatedAt
```

Result: `[]`.

```bash
gh run list --repo charlie2233/rork-hoopshighlights-ai_Final --workflow cloud-edit-deploy-preflight.yml --limit 5
```

Result: GitHub returned `HTTP 404: workflow cloud-edit-deploy-preflight.yml not found on the default branch`.

## Required Fix

1. Merge or otherwise publish `.github/workflows/cloud-edit-deploy-preflight.yml` to the default branch so `workflow_dispatch` is available.
2. Create or update the GitHub Actions environment named `staging`.
3. Add these `staging` environment secrets:
   - `CLOUDFLARE_API_TOKEN`
   - `GCP_WORKLOAD_IDENTITY_PROVIDER`
   - `GCP_DEPLOY_SERVICE_ACCOUNT`
4. Add these `staging` environment variables:
   - `GCP_PROJECT_ID`
   - `GCP_REGION`
5. Scope the Cloudflare token to the HoopClips account with the workflow's required operations:
   - Workers Scripts: Edit
   - Account Settings: Read
   - D1: Edit, when deployment verification touches D1
   - R2: Edit, when deployment verification touches R2 bindings or artifacts
   - Workers Tail: Read, optional for log streaming smoke
6. Dispatch the workflow with `operation=preflight`.
7. Dispatch with `operation=deploy` after preflight passes.
8. Record the deployed Worker version ID, then test rollback with `operation=rollback` and that version ID or a safe prior version.

## Current State

- Local Wrangler dry-run proves the staging Worker bundle and binding config are syntactically deployable.
- GitHub environment setup is the blocker, not local code.
- No staging deploy or rollback was performed from this branch.

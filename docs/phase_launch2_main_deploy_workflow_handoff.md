# Phase Launch2 Main Deploy Workflow Handoff

Date: 2026-05-23
Branch: `codex/phase-launch2-main-deploy-workflow-handoff`
Base: `origin/main` (`aff5524`)

## Scope

This branch publishes the cloud deploy handoff surface directly against the default branch so operators can run the staging deploy preflight after adding GitHub environment credentials.

Included cloud-only files:

- `.github/workflows/cloud-edit-deploy-preflight.yml`
- `scripts/control-plane-harness.ts`
- `services/control-plane/**`
- `services/editing/scripts/deploy_preflight.py`
- `services/editing/cloudbuild.yaml`

Not included:

- iOS app changes
- GPT reranker product changes
- App Store Connect automation
- R2 credentials, Cloudflare tokens, GCP credentials, or presigned URLs

## Why This Exists

The current stacked launch branches contain the deploy workflow, but `main` does not contain the workflow file or the `services/control-plane` Worker it needs. That keeps `workflow_dispatch` unavailable from the default branch and blocks the staging Worker refresh needed to expose:

```text
GET /v1/editing/version
```

Current evidence:

```bash
gh api 'repos/charlie2233/rork-hoopshighlights-ai_Final/contents/.github/workflows/cloud-edit-deploy-preflight.yml?ref=main'
```

Result:

```text
HTTP 404
```

GitHub's workflow registry may show PR-discovered workflow names, but the default branch content check above is the launch gate for a reliable manual dispatch.

## Credential State

Checked GitHub `staging` environment names only. No secret values were printed.

```bash
gh secret list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name --jq '.[].name'
gh variable list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name --jq '.[].name'
```

Result:

```text
no names returned
```

Operators still need to configure:

```text
CLOUDFLARE_API_TOKEN
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_DEPLOY_SERVICE_ACCOUNT
GCP_PROJECT_ID
GCP_REGION
```

## Live Worker State

The staging Worker still needs a refresh. No deploy was attempted from this branch.

```bash
curl -sS -A 'HoopClipsLaunchPreflight/1.0' -H 'Accept: application/json' -o /tmp/hoopclips-worker-version-main-handoff.json -w '%{http_code}\n' https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
```

Result:

```text
404
```

Response body was the non-secret route-not-found error. No presigned URL or credential was logged.

## Validation

Run before merge:

```bash
npm --prefix services/control-plane ci
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
npm --prefix services/control-plane run deploy:staging:dry-run
python3 -m py_compile services/editing/scripts/deploy_preflight.py
python3 services/editing/scripts/deploy_preflight.py --json
npm --prefix services/control-plane audit --audit-level=moderate
git diff --check
```

Current local results:

```text
control-plane ci: passed
control-plane typecheck: passed
control-plane tests: 20 passed
staging Worker dry-run: passed, no deploy
deploy_preflight.py py_compile: passed
deploy_preflight.py --json: blocked only on wrangler-auth; GCP auth presence, project, Artifact Registry, required Secret Manager entries, Cloud Run service, and R2 endpoint checks passed without printing the active account identity
npm audit --audit-level=moderate: passed after updating Wrangler to 4.94.0
```

Expected deploy preflight behavior before credentials:

- GCP checks may pass when local gcloud is authenticated.
- `wrangler-auth` remains blocked until `CLOUDFLARE_API_TOKEN` or local Wrangler auth is available.
- The PR-safe workflow now uses `npm ci`, then runs typecheck, control-plane tests, and staging Worker dry-run before any manual deploy job.

## Operator Steps After Merge

1. Add the five required staging environment inputs in GitHub without printing values.
2. Run `Cloud Edit Deploy Preflight` with `operation=preflight`.
3. Run `operation=deploy` to refresh the staging Worker.
4. Verify `GET /v1/editing/version` returns the editing service non-secret feature-flag payload.
5. Capture the previous Worker version ID and run `operation=rollback` to prove rollback scope.

## Remaining Blockers

- GitHub `staging` deploy inputs are not configured.
- No Worker deploy job ID exists from this branch.
- No rollback job ID exists from this branch.
- Installed TestFlight smoke remains blocked until the Worker route and iOS upload inputs are ready.

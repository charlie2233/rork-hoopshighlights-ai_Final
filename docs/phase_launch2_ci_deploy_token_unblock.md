# Phase Launch2 CI Deploy Token Unblock

Date: 2026-05-22
Branch: `codex/phase-launch2-ci-deploy-token-unblock`

## Scope

- Made the Cloud Edit Deploy Preflight workflow actionable for staging Worker verification, deploy, and rollback.
- Added a PR-safe dry-run job that typechecks `services/control-plane` and validates the staging Worker bundle/bindings without secrets.
- Added manual `workflow_dispatch` inputs for `preflight`, `deploy`, and `rollback` so the same workflow can verify token auth/read scope, perform a staging Worker deploy, and roll back by explicit Worker version ID.
- Created the GitHub `staging` environment so operators can store the expected environment secrets in the documented location.
- Did not add or print any Cloudflare, GCP, R2, or app secrets.

## GitHub Evidence

Default branch workflow state before this phase:

```sh
gh workflow list --all
```

Observed only `Release Secrets Preflight` as active on the default branch. `Cloud Edit Deploy Preflight` is not active until this branch lands on the default branch.

Environment state:

```sh
gh api repos/charlie2233/rork-hoopshighlights-ai_Final/environments --jq '.environments[].name'
```

Before this phase, only `production` existed. This phase created `staging`; the current environment list is:

```text
production
staging
```

Missing staging secret/variable evidence after creating the environment:

```text
CLOUDFLARE_API_TOKEN=missing
GCP_WORKLOAD_IDENTITY_PROVIDER=missing
GCP_DEPLOY_SERVICE_ACCOUNT=missing
GCP_PROJECT_ID=missing
GCP_REGION=missing
```

The workflow file is still not discoverable through GitHub Actions on the default branch:

```text
HTTP 404: workflow .github/workflows/cloud-edit-deploy-preflight.yml not found on the default branch
```

That is expected until this branch is merged or otherwise made available on the default branch.

## Workflow Changes

Updated `.github/workflows/cloud-edit-deploy-preflight.yml`:

- `pull_request` dry-run job:
  - installs control-plane dependencies
  - runs `npm --prefix services/control-plane run typecheck`
  - runs `npm --prefix services/control-plane run deploy:staging:dry-run`
- `workflow_dispatch` staging job:
  - requires the `staging` environment
  - verifies required Cloudflare/GCP inputs are present without printing values
  - authenticates to GCP through Workload Identity Federation
  - runs the existing editing deploy preflight script against Artifact Registry, Secret Manager, Cloud Run, R2 endpoint config, and Wrangler auth
  - runs `wrangler whoami --json` redirected to a temp file and prints only an authenticated marker
  - lists staging Worker secret names and fails if required names are missing without printing values
  - lists staging deployments as JSON redirected to a temp file and prints only a success marker
  - dry-runs staging deploy with the CI token
  - when `operation=deploy`, runs `wrangler deploy --env staging --keep-vars`
  - when `operation=rollback`, requires `rollback_version_id` and runs `wrangler rollback <version-id> --env staging --yes`

Updated `services/control-plane/package.json` with reusable Wrangler scripts:

```text
deploy:staging
deploy:staging:dry-run
deployments:staging
rollback:staging
```

Updated `services/control-plane/README.md` with staging dry-run, deploy, deployment-list, and rollback commands.

The README required-input list now also includes `EDITING_BASE_URL` and `EDITING_SHARED_SECRET`, matching the Worker `Env` contract.

## Local Validation

Commands run:

```sh
git fetch --prune origin
git pull --ff-only
git checkout -b codex/phase-launch2-ci-deploy-token-unblock
git push -u origin codex/phase-launch2-ci-deploy-token-unblock
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane run deploy:staging:dry-run
TMP_HOME=$(mktemp -d) HOME="$TMP_HOME" XDG_CONFIG_HOME="$TMP_HOME" npm --prefix services/control-plane run deploy:staging:dry-run
python3 services/editing/scripts/deploy_preflight.py --json
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "workflow yaml parses"'
node - <<'NODE'
const fs = require('fs');
const text = fs.readFileSync('services/control-plane/package.json', 'utf8');
const seen = new Set();
const duplicates = [];
for (const match of text.matchAll(/^\s+"([^"]+)":/gm)) {
  const key = match[1];
  if (seen.has(key)) duplicates.push(key);
  seen.add(key);
}
if (duplicates.length) {
  console.error(`duplicate keys: ${duplicates.join(', ')}`);
  process.exit(1);
}
JSON.parse(text);
console.log('package.json valid with no duplicate script keys');
NODE
git diff --check
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-derived-data -skipPackagePluginValidation build-for-testing
```

Results:

- Control-plane typecheck: passed.
- Staging Worker dry-run: passed.
- Staging Worker dry-run with an empty temporary home/config directory: passed, confirming the PR dry-run does not depend on local Wrangler OAuth.
- Wrangler version used locally: `4.78.0`.
- Editing deploy preflight: blocked only on Wrangler auth, with GCP CLI, project, Artifact Registry, required Secret Manager entries, Cloud Run editing service, and R2 endpoint checks passing.
- Dry-run bindings included:
  - `JOB_STATE` Durable Object
  - `ANALYSIS_QUEUE`
  - `ANALYSIS_DLQ`
  - `DB` = `hoopsclips-control-plane-staging`
  - `R2_UPLOADS` = `hoopsclips-uploads-staging`
  - `R2_RESULTS` = `hoopsclips-results-staging`
- Workflow YAML parse: passed.
- `package.json` parse/duplicate scan: passed.
- `git diff --check`: passed.
- iOS Debug simulator build through XcodeBuildMCP: passed.
- iOS `build-for-testing`: passed.

## Operator Steps To Finish The Unblock

Add these to the GitHub `staging` environment without pasting values into logs, issues, commits, or chat:

```sh
gh secret set CLOUDFLARE_API_TOKEN --env staging
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --env staging
gh secret set GCP_DEPLOY_SERVICE_ACCOUNT --env staging
gh variable set GCP_PROJECT_ID --env staging --body '<gcp-project-id>'
gh variable set GCP_REGION --env staging --body 'us-central1'
```

Then run `Cloud Edit Deploy Preflight` from Actions:

1. `operation=preflight` to verify secret presence, Wrangler auth, deployment read scope, and deploy dry-run.
2. Confirm the GCP deploy preflight passes through Workload Identity Federation.
3. `operation=deploy` to verify Workers Scripts edit scope with a real staging deploy.
4. Capture the current Worker version ID from `wrangler deployments list --env staging --json`.
5. `operation=rollback` with `rollback_version_id=<previous-version-id>` to verify rollback scope.

## Remaining Blockers

- `CLOUDFLARE_API_TOKEN` is still missing from the GitHub `staging` environment.
- GCP staging deploy identity inputs are also missing from the GitHub `staging` environment.
- No real Worker deploy or rollback job ID exists from this branch because the token is absent.
- The workflow will not be runnable from GitHub Actions until this workflow file exists on the default branch.
- `services/control-plane/wrangler.jsonc` defines `env.staging`; production Worker config remains a placeholder/top-level config and is not safe for production deploy.

## 2026-05-23 Refresh

Branch: `codex/phase-launch2-ci-deploy-token-unblock-readiness`

The deploy blocker is still current. This refresh did not print secret values and did not run a live deploy or rollback.

Commands run:

```sh
gh workflow list --repo charlie2233/rork-hoopshighlights-ai_Final --all
gh api 'repos/charlie2233/rork-hoopshighlights-ai_Final/contents/.github/workflows/cloud-edit-deploy-preflight.yml?ref=main'
gh api repos/charlie2233/rork-hoopshighlights-ai_Final/environments --jq '.environments[].name'
gh secret list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt --jq '.[] | .name'
gh variable list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt --jq '.[] | .name'
npm --prefix services/control-plane exec -- wrangler --version
npm --prefix services/control-plane run deploy:staging:dry-run
npm --prefix services/control-plane exec -- wrangler whoami
npm --prefix services/control-plane run typecheck
python3 services/editing/scripts/deploy_preflight.py --json | tee /tmp/hoopclips-launch2-deploy-preflight-refresh.json
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "workflow yaml parses"'
```

Results:

- GitHub Actions default branch still lists only `Release Secrets Preflight`.
- `cloud-edit-deploy-preflight.yml` still returns `HTTP 404` on `main`, so `workflow_dispatch` cannot be run from Actions yet.
- GitHub environments still include `production` and `staging`.
- GitHub `staging` environment secret-name list returned no names.
- GitHub `staging` environment variable-name list returned no names.
- Local deploy env vars were missing: `CLOUDFLARE_API_TOKEN`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, and `GCP_REGION`.
- Wrangler version: `4.78.0`; latest notice printed `4.94.0` available.
- `npm --prefix services/control-plane run deploy:staging:dry-run`: passed and showed staging bindings only, with no deploy.
- `npm --prefix services/control-plane exec -- wrangler whoami`: failed with `Not logged in`.
- `npm --prefix services/control-plane run typecheck`: passed.
- `deploy_preflight.py --json`: `status=blocked`; GCP project, Artifact Registry, required Secret Manager entries, Cloud Run service, and R2 endpoint checks passed; only `wrangler-auth` failed because `CLOUDFLARE_API_TOKEN` is not set and local Wrangler OAuth is not valid.
- Workflow YAML parse: passed.

Current unblock sequence:

1. Merge or publish `.github/workflows/cloud-edit-deploy-preflight.yml` to `main`.
2. Add the five required `staging` environment inputs in GitHub Actions without printing values.
3. Run `Cloud Edit Deploy Preflight` with `operation=preflight`.
4. Run `operation=deploy` to prove Wrangler edit scope.
5. Capture the previous Worker version ID and run `operation=rollback` to prove rollback scope.

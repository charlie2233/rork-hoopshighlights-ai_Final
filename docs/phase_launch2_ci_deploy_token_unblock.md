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

- GitHub's workflow registry now surfaces `Cloud Edit Deploy Preflight` from PR activity, but `cloud-edit-deploy-preflight.yml` still returns `HTTP 404` on `main`, so default-branch `workflow_dispatch` cannot be run from Actions yet.
- PR #3 run `26327853230` proved the PR-safe `Worker typecheck and dry run` job; `Verify cloud edit deploy secrets` was skipped because the run was not a manual dispatch.
- After the launch doc reconciliation and v6 action fast-forward, PR #3 run `26329438289` also proved the PR-safe `Worker typecheck and dry run` job on commit `480dd20`; `Verify cloud edit deploy secrets` was skipped because the run was not a manual dispatch.
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

No-secret deploy evidence ledger:

| Item | Current evidence | Launch meaning |
| --- | --- | --- |
| PR dry-run run ID | `26329438289` | proves typecheck and staging Worker dry-run only |
| GitHub `staging` input names | no secret or variable names observed | operator inputs still required |
| Cloud Build ID | not captured | no editing Cloud Run deploy proof from this branch |
| Cloud Run revision | not captured for this branch | deployed editing service may be older than current source |
| Worker version ID | not captured | no Worker deploy proof from this branch |
| Worker rollback run ID | not captured | rollback scope not proven |

Current unblock sequence:

1. Merge or publish `.github/workflows/cloud-edit-deploy-preflight.yml` to `main`.
2. Add the five required `staging` environment inputs in GitHub Actions without printing values.
3. Run `Cloud Edit Deploy Preflight` with `operation=preflight`.
4. Deploy the editing Cloud Run service separately with `--substitutions=_IMAGE_TAG=<git-sha>` when backend source needs to go live.
5. Run `operation=deploy` to prove Wrangler edit scope and refresh the staging Worker.
6. Capture the previous Worker version ID and run `operation=rollback` to prove rollback scope.

## 2026-05-23 Main Handoff Merge Refresh

Branch: `codex/phase-launch2-ci-deploy-token-unblock-readiness`

PR #8 published the deploy workflow handoff to `main` as commit `fe35d0618190ce150383fb5a0fc968ee1517b517`. The default-branch manual dispatch was then run with `operation=preflight`.

Default-branch evidence:

- GitHub Actions run ID: `26339989518`
- Head SHA: `fe35d0618190ce150383fb5a0fc968ee1517b517`
- `Worker typecheck and dry run`: passed
- `Verify cloud edit deploy secrets`: failed at the expected missing-input gate
- Missing input names: `CLOUDFLARE_API_TOKEN`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `GCP_PROJECT_ID`, `GCP_REGION`
- Live staging `/v1/editing/version` still returned route-not-found, so no staging Worker deploy was proven

This branch was merged forward with `origin/main` after that handoff. Conflict resolution kept the default-branch workflow hardening:

- `npm ci` instead of `npm install` in the deploy workflow
- control-plane tests in the Worker dry-run job
- `services/control-plane/package-lock.json`
- Wrangler `4.94.0`
- deploy preflight gcloud account redaction

Fresh local validation after conflict resolution:

```sh
git fetch origin --prune
git merge origin/main
npm --prefix services/control-plane ci
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
npm --prefix services/control-plane run deploy:staging:dry-run
npm --prefix services/control-plane audit --audit-level=moderate
python3 -m py_compile services/editing/scripts/deploy_preflight.py
python3 services/editing/scripts/deploy_preflight.py --json
```

Results:

- `npm ci`: passed with 0 vulnerabilities.
- `npm --prefix services/control-plane run typecheck`: passed.
- `npm --prefix services/control-plane test`: 20 passed, 0 failed.
- `npm --prefix services/control-plane run deploy:staging:dry-run`: passed with staging bindings only and no deploy.
- `npm --prefix services/control-plane audit --audit-level=moderate`: passed with 0 vulnerabilities.
- `python3 -m py_compile services/editing/scripts/deploy_preflight.py`: passed.
- `deploy_preflight.py --json`: `status=blocked` only because `CLOUDFLARE_API_TOKEN` is not set and local Wrangler OAuth is not valid; GCP CLI, project, Artifact Registry, required Secret Manager entries, Cloud Run editing service, and R2 endpoint checks passed.

No secret values, R2 credentials, or presigned URLs were printed or committed.

## 2026-05-23 Redaction Hardening Refresh

Branch: `codex/phase-launch2-ci-deploy-token-unblock-readiness`

Code-side privacy hardening completed after the submission-readiness audit found an in-hand log-risk gap.

Changes:

- Control-plane queue dispatch failures no longer persist or log raw external inference response bodies.
- The DLQ regression test now proves the simulated upstream `callback_unreachable` response body is not stored in job state, job events, or the dead-letter message.
- Editing smoke scripts now sanitize failure payloads before printing keys or values that look like URLs, object keys, secrets, credentials, tokens, authorization headers, or signed URL signatures.

Fresh validation:

```sh
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
python3 -m py_compile services/editing/scripts/live_render_smoke.py services/editing/scripts/template_pack_smoke.py services/editing/scripts/policy_observability_smoke.py
git diff --check
```

Results:

- Control-plane typecheck: passed.
- Control-plane tests: 20 passed, 0 failed.
- Smoke script Python compile: passed.
- `git diff --check`: passed.

No secret values, R2 credentials, or presigned URLs were printed or committed.

## 2026-05-23 Submission Readiness Refresh

Branch: `codex/phase-launch2-ci-deploy-token-unblock-readiness`

The latest review added two readiness hardenings that are prerequisites for internal TestFlight confidence but still do not complete App Store/TestFlight submission:

- GPT reranker story order and edit hints now flow into the deterministic cloud edit plan and AI Work Receipt.
- iOS internal/release cloud launch modes no longer silently downgrade to local video analysis or local AVFoundation export when the cloud path is required.

Fresh validation:

```sh
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent ios.backend.tests.test_render_jobs ios.backend.tests.test_launch_guardrails ios.backend.tests.test_external_providers ios.backend.tests.test_local_adapters services.editing.tests.test_gpt_reranker services.editing.tests.test_editing_service -v
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/editing_app/models.py
python3 scripts/launch_backend_config_preflight.py
XcodeBuildMCP test_sim -only-testing:HoopsClipsTests CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-launch2-gpt-cloudguard-bft-dd CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment build-for-testing
git diff --check
```

Results:

- Broad backend/editing suite: 76 passed, 0 failed.
- Python compile: passed.
- Backend launch config preflight: `pass=57 warn=12 fail=0`.
- Full `HoopsClipsTests` simulator suite: 56 passed, 0 failed.
- iOS `build-for-testing`: `** TEST BUILD SUCCEEDED **`.
- `git diff --check`: passed.

Submission blockers still open:

- Live staging Worker `/v1/editing/version` remains stale until a new Worker deploy is proven.
- GitHub `staging` environment still needs deploy inputs before the manual deploy/rollback workflow can prove Wrangler scope.
- No live Worker deploy job ID, Worker version ID, rollback job ID, or Cloud Run image/revision ID exists for this source.
- Installed TestFlight physical-device smoke remains unproven from this environment.

## 2026-05-23 Current PR Evidence

Commit: `309f2c860f2ad1f8d495ccbe23199cce72a97c26`

GitHub Actions:

- PR #3: `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/pull/3`
- Run ID: `26341526621`
- Workflow: `Cloud Edit Deploy Preflight`
- `Worker typecheck and dry run`: passed
- `Verify cloud edit deploy secrets`: skipped on `pull_request`, as expected
- PR merge state after the run: `CLEAN`

External blocker refresh:

```sh
curl -sS -D /tmp/hoopclips-worker-version-refresh.headers -o /tmp/hoopclips-worker-version-refresh.json -w '%{http_code}' https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
curl -sS -D /tmp/hoopclips-editing-version-refresh.headers -o /tmp/hoopclips-editing-version-refresh.json -w '%{http_code}' https://hoopclips-editing-staging-npya43jiia-uc.a.run.app/version
gh secret list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt --jq '.[] | .name'
gh variable list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt --jq '.[] | .name'
```

Results:

- Staging Worker `/v1/editing/version`: `404`, `Route not found.`
- Direct editing Cloud Run `/version`: `200`, with `aiEditEnabled`, `aiEditRevisionEnabled`, and `aiEditTemplatePackEnabled` true; `aiEditProExportsEnabled` false.
- GitHub `staging` secret-name list: empty.
- GitHub `staging` variable-name list: empty.

Submission decision: do not submit to App Store/TestFlight from this state.

# Phase Launch19: Editing Cloud Run Deploy Path

Date: 2026-05-24
Branch: `codex/phase-launch19-editing-cloud-run-deploy`

## Scope

- Added a manual staging Cloud Run editing deploy step to `Cloud Edit Deploy Preflight`.
- Added direct editing `/version` verification after deploy.
- Added Worker `/v1/editing/version` verification after deploy.
- Added a Cloud Run rollback input and rollback step alongside the existing Worker rollback.

## Why This Exists

The live readiness gate still fails because direct staging editing is stale and missing `aiEditLiveRenderEnabled`, while the staging Worker route returns `404`. The existing workflow verified deploy prerequisites and could deploy/rollback the Worker, but it only printed the Cloud Run editing deploy command.

This branch turns that command into a real manual `workflow_dispatch` deploy path. Push and pull-request runs remain no-secret codechecks only. Staging deploy and rollback still require explicit operator dispatch and the GitHub `staging` environment credentials.

## Deploy Behavior

Manual dispatch:

```sh
gh workflow run "Cloud Edit Deploy Preflight" --ref main -f operation=deploy
```

The deploy job now:

1. Verifies cloud deploy inputs.
2. Authenticates to Google Cloud.
3. Verifies editing deploy preflight.
4. Verifies Wrangler token auth, staging Worker secret names, and staging Worker deployment read scope.
5. Runs the Worker staging dry run.
6. Runs `gcloud builds submit` with `services/editing/cloudbuild.yaml`, `_IMAGE_TAG=$GITHUB_SHA`, `_REGION=$GCP_REGION`, and `_SERVICE_NAME=hoopclips-editing-staging`.
7. Verifies direct Cloud Run `/version` reports the current `gitSha`, `editing-cloud-v1`, and required AI Edit flags.
8. Deploys the staging Worker.
9. Verifies Worker `/v1/editing/version` reports the same current version and AI Edit flags.

The workflow does not print secret values, R2 credentials, or presigned URLs.

## Rollback Behavior

Manual rollback requires both the previous Cloud Run revision and Worker version ID:

```sh
gh workflow run "Cloud Edit Deploy Preflight" \
  --ref main \
  -f operation=rollback \
  -f cloud_run_revision=<previous-cloud-run-revision> \
  -f rollback_version_id=<previous-worker-version-id>
```

Cloud Run rollback sends 100% traffic to the requested editing revision. Worker rollback uses Wrangler's deployment rollback command.

## Validation

Commands run:

```sh
python3 -m py_compile scripts/test_main_workflow_codecheck_triggers.py
python3 -m unittest scripts.test_main_workflow_codecheck_triggers -v
npm --prefix services/control-plane run deploy:staging:dry-run
python3 -m unittest discover -s scripts -p 'test_*.py' -v
npm --prefix services/control-plane test
npm --prefix services/control-plane run typecheck
git diff --check
gh secret list --env staging --json name
gh variable list --env staging --json name
python3 scripts/submission_readiness_preflight.py
```

Results:

- Focused workflow tests: 3 passed.
- Worker staging deploy dry run: passed.
- Script test discovery: 30 passed.
- Control-plane tests: 20 passed.
- Control-plane typecheck: passed.
- `git diff --check`: passed.
- GitHub `staging` environment secret name list returned `[]`.
- GitHub `staging` environment variable name list returned `[]`.
- `scripts/submission_readiness_preflight.py` before commit: `pass=18 warn=1 fail=13`, with expected tracked/untracked branch-file checks plus live/provider/device/signing blockers.
- `scripts/submission_readiness_preflight.py` after commit: `pass=18 warn=0 fail=14`. Repo hygiene passed; required current-commit GitHub Actions are expected to be stale until this branch lands on `main`.

## Launch Notes

This branch creates the real deploy path needed to clear the stale editing and Worker route blockers, but it does not run the deploy by itself. A staging operator still needs valid GitHub `staging` environment inputs for Cloudflare and Google Cloud before dispatching `operation=deploy`.

Current provider blocker evidence: the visible GitHub `staging` environment currently reports no secret or variable names, so manual deploy dispatch will still fail until the required inputs are installed.

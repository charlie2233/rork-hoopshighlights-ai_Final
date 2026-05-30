# Phase Launch36 Secret Metadata Preflight

Branch: `codex/phase-launch36-secret-metadata-preflight`

## Goal

Clear the GCP half of the secret-gated deploy preflight and correct the repo handoff language so future provider/browser-agent repairs ask for both deploy-time secret payload access and non-secret Secret Manager metadata access.

## Current State

- `main` is at `3ae4d2a` after PR #36.
- Push codechecks are current and green:
  - Cloud Edit Deploy Preflight push run `26667599035`
  - iOS Internal TestFlight Upload push run `26667599153`
- Manual `operation=preflight` run `26667739571` failed because the deploy identity could not read Secret Manager metadata for the four required secrets and the Cloudflare token failed Wrangler auth.
- Manual `operation=preflight` run `26668177879` after the IAM repair proves all four Secret Manager checks now pass in GitHub Actions. It still fails on Wrangler auth only.
- The deploy service account is `hoopclips-github-deploy@hoopsclips-9d38f.iam.gserviceaccount.com`.

## Provider Action Taken

Without reading or printing secret values, GCP IAM bindings were updated for these four secrets:

- `HOOPS_EDITING_SERVICE_SECRET`
- `HOOPS_R2_ACCESS_KEY_ID`
- `HOOPS_R2_SECRET_ACCESS_KEY`
- `HOOPS_OPENAI_API_KEY`

The deploy service account now has:

- `roles/secretmanager.secretAccessor`
- `roles/secretmanager.viewer`

`secretAccessor` is needed for payload access during deploy/runtime. `viewer` is needed because `services/editing/scripts/deploy_preflight.py` checks secret and latest-version metadata with `gcloud secrets describe` and `gcloud secrets versions describe` without reading payload values.

## Repo Change

- `services/editing/scripts/deploy_preflight.py` now tells operators to grant Secret Manager Viewer plus Secret Manager Secret Accessor when metadata is unreadable.
- `scripts/launch_provider_input_handoff.py` and its Atlas/browser-agent prompt now ask for both roles and separate metadata access from payload access.
- `.github/workflows/cloud-edit-deploy-preflight.yml` prints the same split in its non-secret checklist.

## Validation Plan

## Validation

- `python3 -m unittest scripts.test_deploy_preflight_diagnostics scripts.test_launch_provider_input_handoff -v` passed: 13 tests.
- `python3 scripts/launch_provider_input_handoff.py --json --ref main | python3 -m json.tool >/tmp/launch36_handoff.json` passed.
- `rg -n "Secret Manager Viewer|Secret Manager Secret Accessor|metadata|operation=preflight|operation=deploy" /tmp/launch36_handoff.json` confirmed the handoff separates metadata access from payload access and still forbids `operation=deploy` during repair verification.
- `python3 services/editing/scripts/deploy_preflight.py --project hoopsclips-9d38f --json` exited `1` with GCP checks passing locally and only local Wrangler auth blocked.
- GitHub Actions manual `operation=preflight` run `26668177879` reached `Verify editing deploy preflight`; all four Secret Manager checks passed, then the run failed on `Wrangler auth failed with CLOUDFLARE_API_TOKEN; verify token account, scope, and expiration.`
- `git diff --check` passed.

## Remaining Blockers

- GitHub `staging / CLOUDFLARE_API_TOKEN` still needs replacement/rescope until Wrangler auth passes in the secret-gated workflow.
- Live Worker `/v1/editing/version` still returns `404` until the staging Worker deploy is proven.
- Direct editing service is stale/missing required GPT/live-render flags until staging deploy succeeds.
- Wired iPhone installed TestFlight smoke and launch-grade selected-team/highlight accuracy evidence remain required before submission.

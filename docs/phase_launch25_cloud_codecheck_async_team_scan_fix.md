# Phase Launch25 Cloud Codecheck Async Team Scan Fix

## Goal

Unblock the fresh `Cloud Edit Deploy Preflight` codecheck after GitHub Actions runners started again and exposed a real backend test failure.

## What Changed

- Kept the team-scan API test inside a `TestClient` context manager while it starts and polls the inline analysis task.
- Suppressed expected inline task cancellation cleanup in `InlineTaskDispatcher` by handling `asyncio.CancelledError`.

This does not change cloud production dispatch. Managed staging and production still use Cloud Tasks. The fix only makes local/test inline dispatch deterministic and prevents cancellation noise from escaping the done callback.

## Evidence

Fresh workflow evidence before this fix:

- `iOS Internal TestFlight Upload` codecheck run `26657770685`: succeeded.
- `Cloud Edit Deploy Preflight` codecheck run `26657770729`: failed in `Editing backend Python tests`.
- Failure: `test_team_scan_endpoint_runs_before_start_and_start_accepts_selection` saw job status `processing` instead of `succeeded` after the background inline task was cancelled by the test client lifecycle.

Local verification after this fix:

```bash
PYTHONPATH=ios/backend:services/editing /usr/bin/python3 -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_team_scan_endpoint_runs_before_start_and_start_accepts_selection -v
```

Result: 1 test passed.

```bash
set -euo pipefail
/tmp/hoopclips-ci-venv/bin/python -m py_compile \
  ios/backend/app/editing.py \
  ios/backend/app/main.py \
  services/editing/editing_app/gpt_reranker.py \
  services/editing/editing_app/main.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-ci-venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-ci-venv/bin/python -m unittest discover services/editing/tests -v
/tmp/hoopclips-ci-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
```

Result:

- `ios/backend/tests`: 197 passed.
- `services/editing/tests`: 107 passed.
- `scripts` tests: 80 passed.

## GitHub Actions Evidence After Push

Pushed commit: `dfb35b0094effee8f7772bf010888b2fca397137`.

- `Cloud Edit Deploy Preflight` PR codecheck run `26658183568`: success.
- `Cloud Edit Deploy Preflight` manual `operation=codecheck` run `26658186867`: success.
- `iOS Internal TestFlight Upload` PR no-secret codecheck run `26658183678`: success.

The old GitHub Actions runner/billing symptom is no longer the current blocker for this branch. Jobs start and the no-secret codecheck lanes are green.

## Staging Deploy Preflight

Manual `Cloud Edit Deploy Preflight` run `26658372197` with `operation=preflight` reached the secret-gated deploy preflight job, but failed before deploy:

- Required GitHub staging inputs were present.
- Google Cloud authentication succeeded.
- GCP project `hoopsclips-9d38f`, Artifact Registry repo `hoopsclips`, Cloud Run service `hoopclips-editing-staging`, R2 endpoint configuration, and staging bucket names were detected.
- Blockers:
  - Secret Manager secret `HOOPS_EDITING_SERVICE_SECRET` is missing or inaccessible.
  - Secret Manager secret `HOOPS_R2_ACCESS_KEY_ID` is missing or inaccessible.
  - Secret Manager secret `HOOPS_R2_SECRET_ACCESS_KEY` is missing or inaccessible.
  - Secret Manager secret `HOOPS_OPENAI_API_KEY` is missing or inaccessible.
  - Wrangler auth failed with the provided Cloudflare token.

This means GitHub has the environment input names, but the deploy identity still cannot read required GCP Secret Manager secrets and the Cloudflare token does not authenticate Wrangler.

## Remaining Launch Blockers

- Fix GCP Secret Manager access or create the missing staging secrets.
- Replace or rescope GitHub staging `CLOUDFLARE_API_TOKEN` so `wrangler whoami` and staging deploy checks authenticate.
- Rerun `Cloud Edit Deploy Preflight` with `operation=preflight`.
- After preflight passes, run staging deploy and capture Worker/Cloud Run version proof.
- Prove staging Worker `/v1/editing/version` and direct editing `/version` are current for the branch.
- Produce launch-grade real labeled team-highlight accuracy evidence.
- Run installed TestFlight smoke on an available iPhone.
- Merge/update `main` and rerun required main workflow evidence before Apple submission.

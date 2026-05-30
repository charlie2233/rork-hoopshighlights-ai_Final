# Phase Launch49: Team Scan CI Deflake

## Goal

Remove the remaining CI race in the team quick-scan start test so the deploy workflow can consistently reach the secret-gated staging deploy step.

## Evidence

- Main was merged and pushed at `5c3c9f2eb68c68493e9fc773091a51ecea5d9c2a`.
- Main push checks passed:
  - Cloud Edit Deploy Preflight run `26673159178`
  - iOS Internal TestFlight Upload run `26673159193`
- `operation=deploy` run `26673242095` proved the recreated Cloudflare token path through:
  - Wrangler token authentication
  - staging Worker secret-name checks
  - staging deployment read scope
  - staging Worker deploy dry-run
- That run then failed at `Deploy staging editing service` because the GitHub deploy service account could not access the Cloud Build source bucket.
- Local GCP IAM repair added:
  - `roles/serviceusage.serviceUsageConsumer` on project `hoopsclips-9d38f`
  - `roles/storage.legacyBucketReader` on `gs://hoopsclips-9d38f_cloudbuild`
  - `roles/storage.objectAdmin` on `gs://hoopsclips-9d38f_cloudbuild`
- Follow-up deploy run `26673508972` did not reach deploy; CI hit the same `processing` vs `succeeded` team-scan test race again.

## Change

`InlineTaskDispatcher` now awaits its process callback directly in local in-process mode. Staging and production still use `CloudTasksDispatcher`, so cloud queue behavior remains unchanged.

This makes local/TestClient analysis deterministic instead of depending on an untracked background task that can be starved under CI load.

## Validation

Commands:

```sh
PYTHONPATH=ios/backend:services/editing <python> -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_create_time_selected_team_survives_scan_and_start_without_resending_selection -v
PYTHONPATH=ios/backend:services/editing <python> -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing <python> -m unittest discover services/editing/tests -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- Targeted failing test: 1 passed.
- Full `ios/backend/tests`: 202 passed.
- Full `services/editing/tests`: 114 passed.
- Script tests: 104 passed.
- `py_compile` for `ios/backend/app/task_dispatcher.py`: passed.
- `git diff --check`: passed.

## Next Step

After this branch lands on `main`, rerun one `operation=deploy` workflow. If it reaches `Deploy staging editing service`, the Cloud Build bucket IAM repair is being exercised. If it passes, verify live `/version` endpoints and capture rollback evidence.

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

## Remaining Launch Blockers

- Re-run `Cloud Edit Deploy Preflight` on the pushed branch and confirm it is green.
- Run secret-gated staging deploy/preflight after codecheck is green.
- Prove staging Worker `/v1/editing/version` and direct editing `/version` are current for the branch.
- Produce launch-grade real labeled team-highlight accuracy evidence.
- Run installed TestFlight smoke on an available iPhone.
- Merge/update `main` and rerun required main workflow evidence before Apple submission.

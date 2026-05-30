# Phase Launch48: Team Scan CI Stabilize

## Goal

Unblock the `Cloud Edit Deploy Preflight` deploy lane after run `26672902484` failed before deployment in the backend test job.

## Failure

GitHub Actions run `26672902484` was triggered with `operation=deploy` on `main` at `cf468745c18875eb5ace858c6a3e46d5c1078df9`.

The run did not deploy. It failed in `Editing backend Python tests`:

```text
FAIL: test_create_time_selected_team_survives_scan_and_start_without_resending_selection
AssertionError: 'processing' != 'succeeded'
```

The Worker dry-run job had already passed, and the deploy/secret job was skipped because the backend tests failed first.

## Change

- Added `_poll_analysis_job_until_terminal` to `ios/backend/tests/test_team_quick_scan.py`.
- Replaced two fixed four-second polling loops with the helper so local inline background processing has a larger CI-safe window and stops on terminal states.
- Did not change production analysis, team scan, GPT, render, storage, or iOS behavior.

## Validation

To run before commit:

```sh
PYTHONPATH=ios/backend:services/editing <python> -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_create_time_selected_team_survives_scan_and_start_without_resending_selection -v
PYTHONPATH=ios/backend:services/editing <python> -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_create_time_selected_team_survives_scan_and_start_without_resending_selection ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_team_scan_endpoint_runs_before_start_and_start_accepts_selection -v
PYTHONPATH=ios/backend:services/editing <python> -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing <python> -m unittest discover services/editing/tests -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
```

Results:

- Targeted failing test plus sibling team-scan start test: 2 passed.
- Full `ios/backend/tests`: 202 passed.
- Full `services/editing/tests`: 114 passed.
- Script tests: 104 passed.
- `git diff --check`: passed.

## Next Step

After this branch lands on `main`, rerun:

```sh
gh workflow run "Cloud Edit Deploy Preflight" \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref main \
  -f operation=deploy
```

If it passes, verify live Worker `/v1/editing/version`, then capture rollback evidence.

# Phase Launch18: Current CI Gates

Date: 2026-05-24
Branch: `codex/phase-launch18-current-ci-gates`

## Scope

- Removed path filters from the required main-branch launch workflows so required no-secret codechecks run on every main push and pull request.
- Added an editing backend Python codecheck job to `Cloud Edit Deploy Preflight`.
- Tightened submission readiness preflight so stale GitHub Actions runs from older commits no longer count as current launch evidence.

## Why This Exists

The previous main commit changed GPT-led backend editing logic, but neither required GitHub Actions workflow queued because the workflow path filters did not include the edited backend paths. The submission preflight still passed the GitHub workflow check using older green runs.

Internal TestFlight readiness needs current evidence. A green workflow from an older commit is useful history, but it does not prove the current `main` commit is launch-safe.

## CI Behavior

Required workflows now run without path filters:

- `Cloud Edit Deploy Preflight`
- `iOS Internal TestFlight Upload`

`Cloud Edit Deploy Preflight` now includes:

- Worker typecheck.
- Worker route tests.
- Worker staging deploy dry run.
- Editing backend Python compile.
- `ios/backend/tests` discovery.
- `services/editing/tests` discovery.
- launch script test discovery.

The deploy/rollback jobs remain `workflow_dispatch` only and still require the staging environment inputs. The iOS upload workflow still performs only no-secret unsigned codecheck on push/pull request; signed archive/upload remains explicit `workflow_dispatch`.

## Submission Preflight

`scripts/submission_readiness_preflight.py` now compares the latest required main-branch GitHub Actions run `headSha` against the current checkout `HEAD`.

The preflight fails when:

- no recent run exists for a required workflow,
- the latest run is failed,
- the latest run is pending,
- the latest run succeeded but belongs to an older commit.

## Validation

Commands run:

```sh
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py scripts/test_main_workflow_codecheck_triggers.py
python3 -m unittest scripts.test_main_workflow_codecheck_triggers scripts.test_submission_readiness_preflight -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
npm --prefix services/control-plane test
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane run deploy:staging:dry-run
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
git diff --check
python3 scripts/staging_version_probe.py
python3 scripts/submission_readiness_preflight.py
```

Results:

- Python compile: passed.
- Focused workflow/preflight tests: 16 passed.
- Script test discovery: 29 passed.
- Control-plane tests: 20 passed.
- Control-plane typecheck: passed.
- Worker staging deploy dry run: passed.
- `ios/backend/tests` discovery: 44 passed.
- `services/editing/tests` discovery: 52 passed, including local FFmpeg render/revision/download-history coverage.
- `git diff --check`: passed.
- `scripts/staging_version_probe.py`: failed with `diagnosis=worker_route_missing_and_editing_version_stale`.
- `scripts/submission_readiness_preflight.py` before commit: `pass=16 warn=1 fail=15`. This includes the expected tracked/untracked branch-file checks and the new stale GitHub Actions failures for both required workflows.
- `scripts/submission_readiness_preflight.py` after commit: `pass=18 warn=0 fail=14`. Repo hygiene passed; stale GitHub Actions evidence, live staging, provider input, signing, artifact, and device blockers remain.

## Launch Notes

This branch improves CI evidence quality, but it does not unblock Apple/TestFlight submission by itself. Current launch blockers still include stale/unproxied staging editing version state, missing deploy credentials, missing signed iOS archive/upload artifact, missing iOS upload inputs, and unproven installed-device TestFlight smoke.

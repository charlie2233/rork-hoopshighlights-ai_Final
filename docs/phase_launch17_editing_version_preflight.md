# Phase Launch17 Editing Version Preflight

Date: 2026-05-24
Branch: `codex/phase-launch17-editing-version-preflight`

## Scope

- Extended `scripts/submission_readiness_preflight.py` to probe the direct staging editing `/version` endpoint in addition to the Worker proxy.
- The submission preflight now fails when direct editing `/version` is missing required non-secret AI Edit feature flags.
- The submission preflight now compares direct editing `gitSha` against the current checkout so stale Cloud Run revisions are launch blockers.
- Added unit coverage for missing direct editing flags and stale direct editing `gitSha`.
- Reused the same default editing version URL from `submission_readiness_preflight.py` in `scripts/staging_version_probe.py`.
- Tightened `scripts/staging_version_probe.py` so reachable Worker and direct editing endpoints must include matching `gitSha` and `backendModelVersion` before the probe can pass.

## Why This Exists

The previous readiness preflight already failed when the staging Worker did not proxy:

```text
GET /v1/editing/version
```

Phase Launch16 then proved a second issue: direct editing Cloud Run was reachable, but stale:

```text
editing /version: HTTP 200
missing feature flag: aiEditLiveRenderEnabled
gitSha: d00d0d5
```

That direct Cloud Run drift is now part of the main submission gate, not just a separate diagnostic script. Internal TestFlight cannot be called ready while either the Worker proxy or direct editing service is stale.

## Validation

Commands run:

```sh
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py scripts/staging_version_probe.py
python3 -m unittest scripts.test_submission_readiness_preflight -v
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py scripts/staging_version_probe.py scripts/test_staging_version_probe.py
python3 -m unittest scripts.test_submission_readiness_preflight scripts.test_staging_version_probe -v
python3 -m unittest scripts.test_staging_version_probe scripts.test_submission_readiness_preflight -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/staging_version_probe.py
python3 scripts/submission_readiness_preflight.py
```

Initial results before commit:

- `python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py scripts/staging_version_probe.py` exited `0`.
- `python3 -m unittest scripts.test_submission_readiness_preflight -v` ran 12 tests, all passing.
- `python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py scripts/staging_version_probe.py scripts/test_staging_version_probe.py` exited `0`.
- `python3 -m unittest scripts.test_submission_readiness_preflight scripts.test_staging_version_probe -v` ran 16 tests, all passing.
- `python3 -m unittest scripts.test_staging_version_probe scripts.test_submission_readiness_preflight -v` ran 18 tests, all passing after adding Worker/direct editing metadata drift checks.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` ran 27 tests, all passing.
- `python3 scripts/staging_version_probe.py` exited `1` with `diagnosis=worker_route_missing_and_editing_version_stale`.
- `python3 scripts/submission_readiness_preflight.py` exited `1` with `pass=18 warn=1 fail=13` because this branch still had tracked changes and this new doc was not staged yet.
- After staging the branch files, `python3 scripts/submission_readiness_preflight.py` exited `1` with `pass=19 warn=0 fail=13`; the extra failure is the expected tracked-change gate before commit.
- After commit, `python3 scripts/submission_readiness_preflight.py` exited `1` with `pass=20 warn=0 fail=12`.
- New expected live failures:
  - `live editing feature flags`: missing `aiEditLiveRenderEnabled`.
  - `live editing git sha`: direct editing service `gitSha` does not match the current checkout.

## Launch Notes

- This branch does not deploy Cloud Run or Worker.
- The operator still needs to install GitHub staging deploy inputs, deploy current editing/Worker source, and rerun:

```sh
python3 scripts/staging_version_probe.py
python3 scripts/submission_readiness_preflight.py
```

- Do not submit to Apple until the direct editing version, Worker version proxy, signed artifact, iPhone smoke, and installed TestFlight loop are all proven.

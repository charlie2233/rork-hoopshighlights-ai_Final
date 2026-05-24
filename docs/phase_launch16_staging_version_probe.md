# Phase Launch16 Staging Version Probe

Date: 2026-05-24
Branch: `codex/phase-launch16-staging-version-probe`

## Scope

- Added `scripts/staging_version_probe.py` to separately probe the staging Worker version proxy and the direct editing Cloud Run version endpoint.
- Added focused tests in `scripts/test_staging_version_probe.py`.
- Updated `scripts/launch_provider_input_handoff.py` so the operator handoff runs the staging version probe after deploy and before final submission preflight.
- The probe prints endpoint labels, HTTP status, non-secret feature-flag keys, `gitSha`, and `backendModelVersion` only.
- It does not print response bodies, secrets, R2 credentials, object keys, or presigned URLs.
- It does not change cloud deploy, iOS upload, GPT editing, rendering, storage, or app runtime behavior.

## Why This Exists

The submission readiness preflight currently fails on the live staging Worker route:

```text
GET /v1/editing/version -> HTTP 404
```

The new probe distinguishes between:

- the Worker source not being deployed or route proxy missing live,
- the direct editing service being unreachable,
- the direct editing service being reachable but stale,
- both endpoints returning the required non-secret AI Edit kill-switch feature flags.

## Usage

```sh
python3 scripts/staging_version_probe.py
python3 scripts/staging_version_probe.py --json
python3 scripts/staging_version_probe.py --worker-base-url https://<worker> --editing-version-url https://<editing-service>/version
```

The command exits `0` only when both endpoints return all required feature flags:

- `aiEditEnabled`
- `aiEditLiveRenderEnabled`
- `aiEditRevisionEnabled`
- `aiEditTemplatePackEnabled`

## Current Live Evidence

Command:

```sh
python3 scripts/staging_version_probe.py
```

Result:

```text
status=fail
diagnosis=worker_route_missing_and_editing_version_stale

worker: HTTP 404 for hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
editing: HTTP 200 for hoopclips-editing-staging-npya43jiia-uc.a.run.app/version
editing gitSha: d00d0d5
editing backendModelVersion: editing-cloud-v1
editing missing feature flag: aiEditLiveRenderEnabled
```

Interpretation:

- The staging Worker still needs a real deploy before iOS can prove live kill-switch state through the Worker.
- The direct editing Cloud Run endpoint is reachable, but its `/version` payload is not current enough for launch proof because it is missing `aiEditLiveRenderEnabled`.
- After provider credentials are installed, run the cloud deploy workflow and then rerun this probe before attempting the installed TestFlight smoke.

## Validation

Commands run:

```sh
python3 -m py_compile scripts/staging_version_probe.py scripts/test_staging_version_probe.py
python3 -m unittest scripts.test_staging_version_probe -v
python3 -m py_compile scripts/staging_version_probe.py scripts/test_staging_version_probe.py scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py
python3 -m unittest scripts.test_staging_version_probe scripts.test_launch_provider_input_handoff -v
python3 scripts/launch_provider_input_handoff.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/launch_backend_config_preflight.py
git diff --check
python3 scripts/staging_version_probe.py
python3 scripts/staging_version_probe.py --json
python3 scripts/submission_readiness_preflight.py
```

Results:

- `python3 -m py_compile scripts/staging_version_probe.py scripts/test_staging_version_probe.py` exited `0`.
- `python3 -m unittest scripts.test_staging_version_probe -v` ran 4 tests, all passing.
- `python3 -m py_compile scripts/staging_version_probe.py scripts/test_staging_version_probe.py scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py` exited `0`.
- `python3 -m unittest scripts.test_staging_version_probe scripts.test_launch_provider_input_handoff -v` ran 7 tests, all passing.
- `python3 scripts/launch_provider_input_handoff.py` includes `python3 scripts/staging_version_probe.py` in the verification commands.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` ran 23 tests, all passing.
- `python3 scripts/launch_backend_config_preflight.py` exited `0` with `pass=63 warn=12 fail=0`.
- `git diff --check` exited `0`.
- `python3 scripts/staging_version_probe.py` exited `1` with `diagnosis=worker_route_missing_and_editing_version_stale`.
- `python3 scripts/staging_version_probe.py --json` exited `1` and wrote machine-readable evidence to `/tmp/hoopclips-staging-version-probe.json`.
- `python3 scripts/submission_readiness_preflight.py` exited `1` with `pass=18 warn=1 fail=11` before commit because this branch still had tracked/untracked changes. The remaining launch failures are still provider/device/live-route gates.
- After commit, `python3 scripts/submission_readiness_preflight.py` exited `1` with `pass=20 warn=0 fail=10`.

## Launch Notes

- This branch does not unblock Apple submission by itself.
- Do not submit until this probe passes through the Worker and `python3 scripts/submission_readiness_preflight.py` is green.
- Keep the full installed TestFlight smoke requirement unchanged: upload/import, cloud analysis, Review, Export, AI Edit render, preview, More Hype revision, revised preview, and share/open-in.

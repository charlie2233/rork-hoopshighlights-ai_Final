# Phase Launch32: Secret-Gated Readiness Guard

Date: 2026-05-29
Branch: `codex/phase-launch32-secret-gated-readiness`

## Goal

Prevent HoopClips from being marked submission-ready when only no-secret push codechecks are green. Internal launch readiness also needs a current-commit `workflow_dispatch` run of `Cloud Edit Deploy Preflight` that reaches and passes the secret-gated provider-auth job.

## Change

`scripts/submission_readiness_preflight.py` now checks the latest manually dispatched `cloud-edit-deploy-preflight.yml` run on `main`:

- it must be for the current checkout SHA
- it must complete successfully
- it must include the `Verify cloud edit deploy secrets` job
- that job must complete successfully

A green push run still proves codechecks, but it no longer stands in for GCP Secret Manager, Cloudflare Wrangler, Worker secret, or staging deploy authentication proof.

## Current Evidence

Current `main` before this branch was `f16b052ef1614531148b5de5e17b9a6e1d2d0fdc`.

- Push run `26664692298` succeeded for `Cloud Edit Deploy Preflight`, but only covered codecheck jobs.
- Manual run `26664444002` failed in `Verify cloud edit deploy secrets`.
- The failed manual run was also for previous merge commit `2a7ff43f93ca950a851cf3997bcd99660d6b2895`, not current `main`.

No secret values, token values, R2 credentials, private keys, or full presigned URLs were recorded.

## Tests

Added coverage for:

- stale or failed manually dispatched deploy preflight is rejected
- successful dispatch without the secret-gated job is rejected
- current successful dispatch with the secret-gated job passes

Validation commands:

```bash
python3 -m py_compile scripts/submission_readiness_preflight.py scripts/test_submission_readiness_preflight.py
python3 -m unittest scripts.test_submission_readiness_preflight -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/launch_backend_config_preflight.py --json
git diff --check
python3 scripts/submission_readiness_preflight.py --json
```

Results:

- `py_compile`: passed.
- `scripts.test_submission_readiness_preflight`: 27 tests passed.
- `scripts` test discovery: 95 tests passed.
- backend config preflight: pass=79, warn=12, fail=0.
- `git diff --check`: passed.
- `submission_readiness_preflight.py --json`: failed as expected before provider repair, now with an explicit `secret-gated deploy preflight` failure. The latest manual dispatch was for `2a7ff43`, not current `f16b052`, and it failed the provider-auth job.

## Launch Recommendation

Keep the app out of Apple submission until provider-side repair is complete and a fresh `workflow_dispatch` deploy preflight passes on current `main` after GCP Secret Manager and Cloudflare token fixes.

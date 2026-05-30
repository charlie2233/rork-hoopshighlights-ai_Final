# Phase Launch44: Cheap Deploy Credential Check

## Goal

Reduce GitHub Actions burn while the staging Cloudflare deploy token is being corrected. The cloud deploy workflow now supports a credential-only dispatch path that checks the provider credentials without running the full Worker/backend test jobs first.

## Change

- Added `operation=credential-check` to `.github/workflows/cloud-edit-deploy-preflight.yml`.
- Skips `worker-dry-run` and `editing-backend-codecheck` for credential-only dispatches.
- Adds `deploy-credential-check`, which verifies required GitHub environment inputs, authenticates to GCP, and runs the editing deploy preflight script.
- Keeps `preflight`, `deploy`, and `rollback` on the full path with Worker/backend tests.
- Adds workflow regression coverage in `scripts/test_main_workflow_codecheck_triggers.py`.

## Evidence

- Existing failed run inspected: GitHub Actions run `26672081953`.
- Failure was still in Wrangler authentication, after GCP and Secret Manager checks succeeded.
- Staging `CLOUDFLARE_API_TOKEN` secret timestamp observed locally as `2026-05-30T02:08:45Z`, older than the inspected failed run.
- No secret values, private keys, R2 credentials, or full presigned URLs were printed.

## Validation

Commands run locally:

```bash
git diff --check
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "yaml syntax ok"'
python3 -m py_compile services/editing/scripts/deploy_preflight.py
python3 -m unittest scripts.test_main_workflow_codecheck_triggers -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Results:

- YAML syntax check passed.
- `git diff --check` passed.
- `deploy_preflight.py` compiled.
- Targeted workflow tests: 4 passed.
- Full script tests: 104 passed.

## Next Command

After the Cloudflare token is updated in the GitHub `staging` environment, run only:

```bash
gh workflow run cloud-edit-deploy-preflight.yml \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref main \
  -f operation=credential-check
```

Only run `operation=preflight` or `operation=deploy` after the credential-only run succeeds.

## 2026-05-30 Result

The credential-only lane is now proven on `main`.

Evidence:

- GitHub Actions run `26672739316`
- Ref: `main`
- Head SHA: `cf468745c18875eb5ace858c6a3e46d5c1078df9`
- Operation: `credential-check`
- Result: success
- Successful job: `Verify cloud deploy credentials only`

This clears the cheap Cloudflare/GCP credential proof. It does not replace the required full `operation=preflight`, staging deploy, rollback, live Worker `/v1/editing/version`, installed TestFlight smoke, or labeled team/highlight accuracy proof.

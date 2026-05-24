# Phase Launch14 Main Codecheck Triggers

Date: 2026-05-23
Branch: `codex/phase-launch14-main-codecheck-triggers`

## Scope

- Added safe `main` push triggers for the two launch-critical GitHub workflows:
  - `Cloud Edit Deploy Preflight`
  - `iOS Internal TestFlight Upload`
- The push triggers run only no-secret codecheck paths.
- Deploy, rollback, archive, and upload still require explicit `workflow_dispatch` and the `staging` environment.
- No secrets, signing credentials, App Store Connect keys, Cloudflare tokens, GCP identities, or runtime URLs were added.

## Why This Matters

Before this branch, the latest main-branch status for both required workflows could stay pinned to old failed manual runs that were correctly blocked by missing provider inputs. Main pushes now produce fresh no-secret codecheck evidence while separate preflight checks still require the real deploy/upload secrets before submission.

## Safety

- Cloud deploy codecheck on push runs Worker typecheck/tests and Wrangler staging dry-run only.
- iOS upload codecheck on push runs unsigned Debug build-for-testing with `CODE_SIGNING_ALLOWED=NO`.
- The secret-gated deploy/upload jobs remain unavailable on push through their `workflow_dispatch` conditions.

## Validation

Commands run:

```sh
python3 -m unittest scripts.test_main_workflow_codecheck_triggers -v
python3 -m unittest scripts.test_submission_readiness_preflight scripts.test_main_workflow_codecheck_triggers -v
git diff --check
```

Results:

- Main workflow trigger tests: 2 passed, 0 failed.
- Submission readiness + workflow trigger tests: 12 passed, 0 failed.
- `git diff --check`: passed.
- `actionlint` was not installed locally, so workflow validation used static tests and repository command checks.
- After merge to `main`, GitHub Actions automatically started both push codechecks at `2026-05-24T00:04:36Z` for commit `b812398`.
- `Cloud Edit Deploy Preflight` push codecheck succeeded: run `26347032786`.
- `iOS Internal TestFlight Upload` push codecheck succeeded: run `26347032779`.
- Submission readiness preflight after the green push codechecks: 20 pass, 0 warn, 10 fail.

## Launch Notes

- This does not resolve missing provider inputs. `CLOUDFLARE_API_TOKEN`, GCP deploy identity/region/project, iOS signing/upload inputs, a signed archive/IPA, staging Worker deploy proof, and real installed TestFlight smoke remain required before Apple submission.
- The two automatically triggered main workflow runs are now current green codecheck evidence only. Secret-gated deploy/upload proof still requires explicit `workflow_dispatch` runs after the staging/provider inputs are installed.

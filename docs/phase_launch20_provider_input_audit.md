# Phase Launch20 Provider Input Audit

Date: 2026-05-24
Branch: `codex/phase-launch20-provider-input-audit`

## Scope

- Added `scripts/configure_github_staging_public_variables.py` for staging GitHub environment variables that are repo-documented as public/non-secret.
- Kept all secret inputs as manual operator handoff only.
- Updated `scripts/launch_provider_input_handoff.py` so the provider setup packet includes the new dry-run and apply commands.
- Did not change iOS runtime behavior, cloud rendering behavior, AI/GPT editing, Worker routing, or App Store submission automation.

## Public Variable Sources

- `GCP_PROJECT_ID` is resolved from `docs/gcp_cost_control_2026_05_10.md`.
- `GCP_REGION` is resolved from `services/editing/cloudbuild.yaml`.
- `HOOPS_PRIVACY_POLICY_URL` is resolved from `ios/docs/runbooks/rork-release-operator-handoff.md`.
- `HOOPS_TERMS_OF_SERVICE_URL` is resolved from `ios/docs/runbooks/rork-release-operator-handoff.md`.

The helper never prints the variable values in normal text or JSON output. `--apply` passes them directly to `gh variable set` and prints only the variable names and source paths.

## Still Manual

These remain manual because they are secrets, credential identifiers, legal URLs that are not HoopClips-specific in repo truth, or provider-side state:

- `CLOUDFLARE_API_TOKEN`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`
- iOS signing, RevenueCat, Google/Firebase, Sentry, and App Store Connect upload secrets
- real signed archive/IPA
- trusted wired iPhone and installed TestFlight smoke
- staging deploy/rollback dispatch after credentials are installed

## Commands

```sh
python3 scripts/configure_github_staging_public_variables.py
python3 scripts/configure_github_staging_public_variables.py --json
python3 scripts/configure_github_staging_public_variables.py --apply
gh variable list --env staging --json name
python3 scripts/launch_provider_input_handoff.py --json
python3 -m py_compile scripts/configure_github_staging_public_variables.py scripts/test_configure_github_staging_public_variables.py scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py
python3 -m unittest scripts.test_configure_github_staging_public_variables scripts.test_launch_provider_input_handoff -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
git diff --check
python3 scripts/submission_readiness_preflight.py
```

## Evidence

- Dry run exited `0` and printed only variable names/source paths.
- JSON dry run exited `0` and omitted variable values.
- `--apply` exited `0` and set only `GCP_PROJECT_ID`, `GCP_REGION`, `HOOPS_PRIVACY_POLICY_URL`, and `HOOPS_TERMS_OF_SERVICE_URL` in the GitHub `staging` environment.
- `gh variable list --env staging --json name` returned the four public variable names: `GCP_PROJECT_ID`, `GCP_REGION`, `HOOPS_PRIVACY_POLICY_URL`, `HOOPS_TERMS_OF_SERVICE_URL`.
- `gh secret list --env staging --json name` returned `[]`; no secrets were created or inferred.
- `python3 scripts/submission_readiness_preflight.py --skip-live` exited `1` with `pass=18 warn=3 fail=10` before commit. The cloud deploy input failure now lists only `CLOUDFLARE_API_TOKEN`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, and `GCP_DEPLOY_SERVICE_ACCOUNT`; the GCP project/region variable names are present.
- After legal URLs were added to the public helper, `python3 scripts/submission_readiness_preflight.py --skip-live` exited `1` with `pass=17 warn=2 fail=12` while tracked files were still modified. The iOS upload input failure no longer lists `HOOPS_PRIVACY_POLICY_URL` or `HOOPS_TERMS_OF_SERVICE_URL`; remaining iOS inputs are credential secrets only.
- `python3 -m py_compile scripts/configure_github_staging_public_variables.py scripts/test_configure_github_staging_public_variables.py scripts/launch_provider_input_handoff.py scripts/test_launch_provider_input_handoff.py` exited `0`.
- Focused provider handoff tests ran 7 tests, all passing.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` ran 34 tests, all passing.
- `git diff --check` exited `0`.
- `python3 scripts/launch_backend_config_preflight.py` exited `0` with `pass=63 warn=12 fail=0`.
- Full `python3 scripts/submission_readiness_preflight.py` exited `1` with `pass=18 warn=1 fail=13` before commit. Expected live/provider/device/signing blockers remain: no local signing team, no archive/IPA, no available physical iPhone, Worker `/v1/editing/version` still `404`, direct editing `/version` still stale and missing `aiEditLiveRenderEnabled`, three cloud deploy secrets missing, installed TestFlight smoke unproven, and iOS upload secrets/legal URLs missing.
- After staging branch files, `python3 scripts/submission_readiness_preflight.py --skip-live` exited `1`; repo untracked-file hygiene passed and the remaining failures were the expected signing/artifact/device/provider/manual blocker gates.
- After commit, `python3 scripts/submission_readiness_preflight.py --skip-live` exited `1`; repo hygiene passed, and the added failure is expected current-commit CI staleness until this commit lands on `main` and the no-secret main codechecks rerun.
- Full `python3 scripts/submission_readiness_preflight.py` after commit exited `1` with `pass=18 warn=0 fail=14`; repo hygiene passed, legal URL variables were no longer missing, and the remaining failures were live staging/provider/device/signing/artifact/manual smoke gates.

## Launch Recommendation

Run the helper once from an authenticated GitHub CLI session, then add the remaining secrets in the GitHub `staging` environment UI or with `gh secret set`. After that, dispatch the cloud deploy preflight, staging deploy, iOS TestFlight preflight/upload, and post-install smoke before Apple submission.

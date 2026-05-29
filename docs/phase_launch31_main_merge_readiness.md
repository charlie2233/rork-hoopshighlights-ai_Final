# Phase Launch31: Main Merge Readiness Snapshot

Date: 2026-05-29
Branch: `main`
Merge commit: `2a7ff43f93ca950a851cf3997bcd99660d6b2895`

## Goal

Move the launch-critical GPT/team-selection work from PR #32 onto `main` and refresh submission-readiness evidence from the actual submission baseline.

## Main Update

PR #32, `codex/phase-clip28-cloud-team-quick-scan`, was merged into `main`.

Merged work now on `main` includes:

- cloud quick-scan team selection before analysis
- All teams mode
- selected-team control-plane contract
- stronger GPT-led clip review/keyframe quality gates
- Agent Template Cookbook integration
- Free plan 3 AI edits/day policy
- launch-grade team/highlight accuracy report builder
- provider handoff hardening for missing `HOOPS_OPENAI_API_KEY`

The root checkout `codex/redesign-hoopclips-logo` still has unrelated dirty files and untracked root Xcode folders. It was not used for launch validation.

## Validation Commands

```bash
git fetch --all --prune
gh pr view 32 --json number,state,mergedAt,mergeCommit,url,headRefName,baseRefName,headRefOid,baseRefOid
git switch main
git pull --ff-only origin main
git diff --check
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/launch_backend_config_preflight.py --json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
npm test -- --test-reporter=spec
npm run typecheck
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/hoopclips-main-build-derived CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation
python3 scripts/submission_readiness_preflight.py --json
gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight
gh run watch 26664444002 --exit-status
```

## Results

- PR #32 merged into `main` at `2a7ff43f93ca950a851cf3997bcd99660d6b2895`.
- `git diff --check`: passed.
- Script test discovery: 92 tests passed.
- Backend config preflight: pass=79, warn=12, fail=0.
- GPT reranker focused tests: 60 tests passed.
- Control-plane tests: 28 tests passed.
- Control-plane typecheck: passed.
- iOS Debug build-for-testing: `** TEST BUILD SUCCEEDED **`.
- Main push CI:
  - Cloud Edit Deploy Preflight run `26664279005`: success.
  - iOS Internal TestFlight Upload run `26664279023`: success.
- Manual main deploy preflight run `26664444002`: failed at `Verify editing deploy preflight`.

## Current Manual Deploy Preflight Blockers

Manual preflight proved the GitHub staging deploy inputs are present and GCP Workload Identity starts correctly:

- active GCP project: `hoopsclips-9d38f`
- Artifact Registry repo: `hoopsclips` in `us-central1`
- Cloud Run service: `hoopclips-editing-staging`
- R2 endpoint configured
- source bucket: `hoopsclips-uploads-staging`
- output bucket: `hoopsclips-results-staging`

It still blocks on provider-side secret/auth state:

- Secret Manager secret `HOOPS_EDITING_SERVICE_SECRET` is missing or inaccessible.
- Secret Manager secret `HOOPS_R2_ACCESS_KEY_ID` is missing or inaccessible.
- Secret Manager secret `HOOPS_R2_SECRET_ACCESS_KEY` is missing or inaccessible.
- Secret Manager secret `HOOPS_OPENAI_API_KEY` is missing or inaccessible.
- Wrangler auth failed with the provided Cloudflare token.

No secret values, R2 credentials, private keys, or full presigned URLs were added to this doc.

## Provider Agent Follow-Up

The external browser/provider agent reported:

- GCP secret `HOOPS_OPENAI_API_KEY`: missing; enabled version not confirmed.
- Secret accessor grant: not confirmed.
- Cloudflare token update: not completed.
- GitHub Actions verification run: not triggered.
- Conclusion: stopped at step 1 because `HOOPS_OPENAI_API_KEY` is missing.

Reply to the provider agent with a repair-only continuation:

```text
Continue from the current provider state. Do not paste or reveal any secret values, private keys, base64 values, tokens, or full URLs.

First repair Google Cloud Secret Manager for project hoopsclips-9d38f:
1. Create or update secret HOOPS_OPENAI_API_KEY with the OpenAI API key.
2. Ensure it has an enabled latest version.
3. Grant the staging GCP_DEPLOY_SERVICE_ACCOUNT Secret Manager Secret Accessor for HOOPS_OPENAI_API_KEY and the other staging deploy secrets if they are still inaccessible.

Then repair Cloudflare:
4. Create or replace the GitHub staging secret CLOUDFLARE_API_TOKEN with a token that Wrangler can authenticate with for the HoopClips account and required Worker/R2 deploy scope.

Then trigger verification:
5. Trigger GitHub Actions workflow cloud-edit-deploy-preflight.yml on main with operation=preflight.

Return only this non-secret status:
- HOOPS_OPENAI_API_KEY exists: yes/no
- HOOPS_OPENAI_API_KEY enabled latest version: yes/no
- Secret accessor granted to staging deploy service account: yes/no
- Cloudflare token updated in GitHub staging environment: yes/no
- GitHub run URL:
- Final conclusion:
```

## Submission Readiness

`python3 scripts/submission_readiness_preflight.py --json` on clean `main` returned:

- pass: 24
- fail: 9
- warn: 0

Remaining NO-GO items:

- launch-grade labeled team/highlight accuracy report is missing, so 85% selected-team/highlight quality is unproven
- connected iPhone is detected but unavailable for installed TestFlight smoke
- staging Worker `/v1/editing/version` returns 404
- direct editing `/version` is stale/missing live-render/GPT feature flags
- direct editing `gitSha` does not match `main`
- installed TestFlight post-install smoke remains unproven
- staging Worker editing version route remains unproven live
- Cloudflare deploy credential proof is still missing
- live iOS kill-switch state is not proven through the Worker

## Launch Recommendation

Do not submit to Apple yet.

Next required external/provider steps:

1. Repair the four GCP Secret Manager secrets and grant the staging deploy service account Secret Manager Secret Accessor.
2. Replace or rescope GitHub staging `CLOUDFLARE_API_TOKEN` so Wrangler authenticates in GitHub Actions.
3. Rerun `Cloud Edit Deploy Preflight` with `operation=preflight` on `main`.
4. After preflight passes, run staging deploy and verify direct editing and Worker `/v1/editing/version` report `main` commit `2a7ff43f93ca950a851cf3997bcd99660d6b2895` with the required AI Edit/GPT flags.
5. Generate a launch-grade real labeled team/highlight accuracy report.
6. Run the installed TestFlight smoke on an available trusted iPhone.

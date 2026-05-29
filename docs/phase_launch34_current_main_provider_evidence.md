# Phase Launch34: Current Main Provider Evidence

Date: 2026-05-29
Branch: `codex/phase-launch34-current-main-provider-evidence`
Main commit checked: `77935cd4b9a874471108a639f7296b30f93864dc`

## Goal

Record launch-readiness evidence after `main` absorbed the provider preflight refresh. This keeps the current submission gate tied to the latest merge commit instead of the pre-merge `5fb833e` snapshot.

## Commands

```bash
git status --short --branch
git log --oneline -8
gh run list --repo charlie2233/rork-hoopshighlights-ai_Final --branch main --limit 12 --json databaseId,workflowName,event,status,conclusion,headSha,createdAt,url
gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight
gh workflow run ios-testflight-upload.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight
gh run watch 26665828548 --repo charlie2233/rork-hoopshighlights-ai_Final --exit-status
gh run watch 26665828532 --repo charlie2233/rork-hoopshighlights-ai_Final --exit-status
gh run view 26665828548 --repo charlie2233/rork-hoopshighlights-ai_Final --job 78599217625 --log
python3 scripts/submission_readiness_preflight.py --json
python3 -m unittest discover -s scripts -p 'test_*.py' -v
PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent ios.backend.tests.test_team_quick_scan ios.backend.tests.test_pipeline_quality -v
```

## Current Main Evidence

- Current clean `main` is `77935cd4b9a874471108a639f7296b30f93864dc`.
- Push codechecks on `77935cd` passed:
  - `Cloud Edit Deploy Preflight` push run `26665805937`.
  - `iOS Internal TestFlight Upload` push run `26665805960`.
- Manual current-main iOS preflight passed:
  - `iOS Internal TestFlight Upload` workflow_dispatch run `26665828532`.
  - Job `Build internal staging TestFlight archive` built a signed internal staging archive and verified archive metadata.
  - `Upload to internal TestFlight` was skipped because this run used `operation=preflight`.
- Manual current-main cloud preflight failed:
  - `Cloud Edit Deploy Preflight` workflow_dispatch run `26665828548`.
  - `Worker typecheck and dry run` passed.
  - `Editing backend Python tests` passed.
  - `Verify cloud edit deploy secrets` failed at `Verify editing deploy preflight`.

No secret values, token values, R2 credentials, private keys, base64 values, bearer tokens, or full presigned URLs were recorded.

## Provider Blockers

The current-main secret-gated deploy job still proves these non-secret positives:

- Required GitHub deploy input names are present.
- GCP Workload Identity authenticated.
- Artifact Registry repo `hoopsclips` exists in `us-central1`.
- Cloud Run service `hoopclips-editing-staging` exists.
- R2 endpoint URL is configured.

The same job is blocked by:

- Secret Manager secret `HOOPS_EDITING_SERVICE_SECRET` is missing or inaccessible.
- Secret Manager secret `HOOPS_R2_ACCESS_KEY_ID` is missing or inaccessible.
- Secret Manager secret `HOOPS_R2_SECRET_ACCESS_KEY` is missing or inaccessible.
- Secret Manager secret `HOOPS_OPENAI_API_KEY` is missing or inaccessible.
- Wrangler auth failed with the provided Cloudflare token.

Live smoke env presence is also incomplete for:

- `HOOPS_EDITING_BASE_URL`
- `HOOPS_EDITING_SERVICE_SECRET`
- `HOOPS_R2_ENDPOINT_URL`
- `HOOPS_R2_ACCESS_KEY_ID`
- `HOOPS_R2_SECRET_ACCESS_KEY`

## Readiness Gate

`python3 scripts/submission_readiness_preflight.py --json` still fails with `pass=23`, `fail=11`, `warn=0`.

Current blockers reported by the readiness gate:

- Launch-grade real labeled team/highlight accuracy report is missing, so the 85% selected-team/highlight quality target is unproven.
- The wired iPhone is detected but unavailable for installed TestFlight smoke.
- The live Worker editing version route returns HTTP 404.
- Direct editing `/version` is stale and missing required live-render/GPT feature flags.
- Current-main secret-gated deploy preflight failed.
- Installed TestFlight smoke, live Worker kill-switch proof, and Cloudflare deploy credential proof remain documented launch blockers.

## Product Quality Evidence

Repo-side GPT/team-selection quality checks passed locally:

- `scripts` test discovery: 95 tests passed.
- GPT highlight reranker suite: 60 tests passed.
- Edit plan, team quick scan, and pipeline quality suites: 178 tests passed.

This proves the repo-side implementation is covered for strict GPT structured output, keyframe-only payloads, agent cookbook use, GPT plan edit/revision patches, selected-team/all-teams filtering, defensive blocks/steals retention, and Free quota policy. It does not prove live staging readiness until provider deploy passes and staging is redeployed from current `main`.

## Handoff Tooling Update

`scripts/launch_provider_input_handoff.py` no longer asks the browser/provider agent to check GitHub Actions billing or spending-limit state by default. Current-main push and workflow_dispatch runs now prove hosted runners can start. The safe provider prompt should stay focused on the live blockers that still fail today: GCP Secret Manager access and Cloudflare Wrangler authentication.

## Atlas / Browser Agent Prompt

```text
Continue HoopClips provider repair for repo charlie2233/rork-hoopshighlights-ai_Final, GitHub environment staging, current main commit 77935cd4b9a874471108a639f7296b30f93864dc.

Do not paste, reveal, summarize, screenshot, or return secret values, API keys, private key contents, base64 values, credentials, bearer tokens, R2 credentials, OpenAI keys, Secret Manager payloads, or full presigned URLs.

Current GitHub proof:
- Cloud Edit Deploy Preflight workflow_dispatch run 26665828548 reached the secret-gated job and failed at Verify editing deploy preflight.
- iOS Internal TestFlight Upload workflow_dispatch run 26665828532 passed operation=preflight and built a signed internal staging archive.

Repair only provider-side blockers:
1. In Google Cloud project hoopsclips-9d38f, create or repair these Secret Manager secrets and make sure each has a latest ENABLED version:
   - HOOPS_EDITING_SERVICE_SECRET
   - HOOPS_R2_ACCESS_KEY_ID
   - HOOPS_R2_SECRET_ACCESS_KEY
   - HOOPS_OPENAI_API_KEY
2. Grant the staging deploy service account configured by GitHub staging / GCP_DEPLOY_SERVICE_ACCOUNT Secret Manager Secret Accessor for those secrets.
3. In Cloudflare, create or replace a scoped API token that allows Wrangler authentication for the HoopClips staging Worker/R2/D1 deploy checks.
4. Set that token directly as GitHub environment secret staging / CLOUDFLARE_API_TOKEN.
5. Trigger GitHub Actions workflow cloud-edit-deploy-preflight.yml on main with operation=preflight.

Return only this non-secret status:
- HOOPS_EDITING_SERVICE_SECRET present and enabled: yes/no
- HOOPS_R2_ACCESS_KEY_ID present and enabled: yes/no
- HOOPS_R2_SECRET_ACCESS_KEY present and enabled: yes/no
- HOOPS_OPENAI_API_KEY present and enabled: yes/no
- staging deploy service account has Secret Manager Secret Accessor: yes/no
- GitHub staging CLOUDFLARE_API_TOKEN replaced or rescope completed: yes/no
- GitHub run URL:
- Final conclusion:
```

## Launch Recommendation

Do not submit to Apple yet. The current-main iOS archive preflight is green, but internal launch still needs provider secret repair, valid Wrangler auth, current staging deploy/version proof, an available installed-device smoke, and launch-grade real labeled accuracy evidence.

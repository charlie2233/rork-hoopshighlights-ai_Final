# Phase Launch33: Current Provider Preflight Refresh

Date: 2026-05-29
Branch: `codex/phase-launch33-provider-preflight-refresh`
Main commit checked: `5fb833e23fc3054ebd686ff4bab57fa498bec31c`

## Goal

Refresh launch readiness from current `main` after the secret-gated deploy-readiness guard landed. This records which launch blockers are still external/provider-owned and which checks now pass.

## Commands

```bash
git status --short --branch
git log --oneline -8
gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight
gh workflow run ios-testflight-upload.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=preflight
gh run watch 26665374215 --repo charlie2233/rork-hoopshighlights-ai_Final --exit-status
gh run view 26665374215 --repo charlie2233/rork-hoopshighlights-ai_Final --job 78597862005 --log
gh run view 26665374219 --repo charlie2233/rork-hoopshighlights-ai_Final --json databaseId,workflowName,event,displayTitle,status,conclusion,headSha,createdAt,url,jobs
xcrun devicectl list devices
python3 scripts/submission_readiness_preflight.py --json
```

## Current Results

- Clean `main` was at `5fb833e23fc3054ebd686ff4bab57fa498bec31c`.
- Root checkout `codex/redesign-hoopclips-logo` still has unrelated dirty files and untracked root Xcode folders. They were not staged or used for launch validation.
- Current-commit `Cloud Edit Deploy Preflight` workflow_dispatch run `26665374215` failed in job `Verify cloud edit deploy secrets`.
- Current-commit `iOS Internal TestFlight Upload` workflow_dispatch run `26665374219` succeeded with operation `preflight`.
- The iOS run built a signed internal staging archive and verified archive metadata. Upload was skipped because operation was `preflight`.
- The wired iPhone is still detected as `unavailable`, so installed TestFlight smoke cannot be claimed.
- `submission_readiness_preflight.py --json` now reports pass=23, fail=11, warn=0.

## Provider Blockers

The secret-gated deploy job proved these non-secret facts:

- GCP Workload Identity authenticated.
- Active GCP project is `hoopsclips-9d38f`.
- Artifact Registry repo `hoopsclips` exists in `us-central1`.
- Cloud Run service `hoopclips-editing-staging` exists.
- R2 endpoint is configured.
- R2 source bucket is `hoopsclips-uploads-staging`.
- R2 output bucket is `hoopsclips-results-staging`.

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

No secret values, R2 credentials, private keys, base64 values, bearer tokens, or full presigned URLs were recorded.

## Accuracy Evidence

No launch-grade real labeled team/highlight accuracy artifacts were found in the repo or worktrees. The readiness gate still fails without `--team-accuracy-report`, so the 85% selected-team/highlight quality target is unproven.

Required local artifact flow once real cloud analysis exports and human labels exist:

```bash
python3 -m scripts.make_team_highlight_label_template \
  --analysis-result artifacts/staging_analysis_result.json \
  --output artifacts/team_highlight_manual_labels.json \
  --case-id internal_game_001 \
  --video-id internal_video_001

python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --eval-output artifacts/team_highlight_eval.json \
  --report-output artifacts/team_highlight_accuracy_report.json \
  --json

python3 scripts/submission_readiness_preflight.py \
  --team-accuracy-report artifacts/team_highlight_accuracy_report.json
```

## Atlas / Browser Agent Prompt

```text
Continue HoopClips provider repair for repo charlie2233/rork-hoopshighlights-ai_Final, GitHub environment staging, current main commit 5fb833e23fc3054ebd686ff4bab57fa498bec31c.

Do not paste, reveal, screenshot, summarize, or return secret values, API keys, private key contents, base64 values, credentials, bearer tokens, R2 credentials, or full presigned URLs.

Current GitHub proof:
- Cloud Edit Deploy Preflight workflow_dispatch run 26665374215 reached the secret-gated job and failed.
- iOS Internal TestFlight Upload workflow_dispatch run 26665374219 passed operation=preflight.

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

Do not submit to Apple yet. The iOS archive preflight is green, but the cloud render path is still blocked by provider secrets/auth, live Worker `/v1/editing/version` is still unproven, the connected iPhone is unavailable for installed smoke, and real labeled accuracy proof is missing.

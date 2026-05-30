# Phase Launch47: Cloud Token Proof Reconciliation

## Goal

Record the current no-secret evidence that the recreated Cloudflare deploy token works in the cheap credential-check lane, while preserving the remaining launch gates for full staging deploy, rollback, live Worker version proof, and installed TestFlight smoke.

## Evidence

Commands run:

```sh
gh secret list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt
gh variable list --repo charlie2233/rork-hoopshighlights-ai_Final --env staging --json name,updatedAt
gh workflow run cloud-edit-deploy-preflight.yml --repo charlie2233/rork-hoopshighlights-ai_Final --ref main -f operation=credential-check
gh run watch 26672739316 --repo charlie2233/rork-hoopshighlights-ai_Final --exit-status
gh run view 26672739316 --repo charlie2233/rork-hoopshighlights-ai_Final --json headSha,headBranch,event,status,conclusion,url,createdAt,jobs
python3 scripts/submission_readiness_preflight.py --json
python3 scripts/submission_readiness_preflight.py --skip-live --json
```

Observed:

- Staging secret names include `CLOUDFLARE_API_TOKEN`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, and `GCP_DEPLOY_SERVICE_ACCOUNT`.
- Staging variable names include `GCP_PROJECT_ID` and `GCP_REGION`.
- `CLOUDFLARE_API_TOKEN` was updated at `2026-05-30T03:02:50Z`.
- `Cloud Edit Deploy Preflight` run `26672739316` completed successfully on `main` at `cf468745c18875eb5ace858c6a3e46d5c1078df9`.
- The successful job was `Verify cloud deploy credentials only`.
- Full Worker/backend jobs were skipped by design because the operation was `credential-check`.

No secret values, R2 credentials, object keys, or full presigned URLs were printed or committed.

## Readiness Impact

Resolved:

- The cheap Cloudflare/GCP credential proof path is now green.
- The old documentation marker saying the Cloudflare token is missing is no longer current.

Still open:

- Full `operation=preflight` on the release ref.
- `operation=deploy` to refresh staging Cloud Run/Worker and prove live Worker `/v1/editing/version`.
- Worker rollback proof with a captured previous Worker version ID.
- Launch-grade labeled team/highlight accuracy report.
- Signed archive/current upload artifact.
- Installed TestFlight smoke on a trusted iPhone.

## Submission Preflight Snapshot

`python3 scripts/submission_readiness_preflight.py --json` still failed with `21 pass`, `13 fail` before this documentation update.

After this documentation update was committed, `python3 scripts/submission_readiness_preflight.py --skip-live --json` reported `22 pass`, `2 warn`, and `9 fail`. The known Cloudflare credential-proof blocker doc marker is now absent; the remaining failures are still real launch gates.

Important remaining failures:

- Missing launch-grade team/highlight accuracy evidence.
- Missing local signing team value in `LocalSecrets.xcconfig`.
- No `.xcarchive` or `.ipa` upload artifact under expected build output locations.
- Live staging Worker `/v1/editing/version` returned `404`.
- Direct editing `/version` is stale and missing required live GPT/render feature flags.
- Full main workflow and secret-gated deploy preflight proof must run on the release ref before submission.
- Installed TestFlight post-install smoke remains unproven.

## Next Recommended Action

Run the full cloud deploy preflight only when ready to spend the workflow:

```sh
gh workflow run cloud-edit-deploy-preflight.yml \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref main \
  -f operation=preflight
```

If that passes, run `operation=deploy`, verify live Worker `/v1/editing/version`, capture the previous Worker version ID, and run `operation=rollback`.

## Validation

Commands run:

```sh
git diff --check
python3 -m unittest discover -s scripts -p 'test_*.py' -v
LC_ALL=C grep -RIn '[^ -~]' docs/phase_launch2_ci_deploy_token_unblock.md docs/phase_launch44_cheap_deploy_credential_check.md docs/phase_launch_doc_reconciliation.md docs/phase_launch47_cloud_token_proof_reconciliation.md || true
```

Results:

- `git diff --check`: passed.
- Script tests: 104 passed.
- ASCII scan: passed.

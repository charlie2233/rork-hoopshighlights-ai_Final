# Phase Launch Doc Reconciliation

Date: 2026-05-23
Branch: `codex/phase-launch-doc-reconciliation`

## Scope

- Reconciled launch-decision docs with the current internal TestFlight and staging backend state.
- Clarified that the iOS kill-switch Worker route is implemented in source but not yet deployed on live staging.
- Clarified that the build 3 TestFlight upload note is historical upload evidence, not current installed-app proof.
- Redacted exact storage object-key paths from the Phase Edit7e final smoke summary while preserving job IDs and ffprobe evidence.
- Did not change app code, backend code, cloud config, local rendering behavior, feature flags, thresholds, secrets, or production cutover settings.

## Current Evidence

Commands run before the doc updates:

```sh
git status --short --branch
git log --oneline --decorate -12
git diff --check
gh pr list --repo charlie2233/rork-hoopshighlights-ai_Final --state open --json number,title,headRefName,baseRefName,isDraft,mergeStateStatus,mergeable,url,statusCheckRollup
curl -sS -o /tmp/hoopclips-worker-version.json -w '%{http_code}\n' https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
gh api 'repos/charlie2233/rork-hoopshighlights-ai_Final/contents/.github/workflows/cloud-edit-deploy-preflight.yml?ref=main' --jq '.path'
rg -n "uploads/[a-f0-9]{16,}/source\\.mp4|edits/edit_[a-f0-9]{16,}/render_jobs/render_[a-f0-9]{16,}/(final\\.mp4|render_log\\.json)|sourceObjectKey: uploads/|outputObjectKey: edits/|renderLogObjectKey: edits/" docs
npm --prefix services/control-plane exec -- wrangler deployments --help
npm --prefix services/control-plane exec -- wrangler rollback --help
npm --prefix services/control-plane exec -- wrangler secret list --help
npm --prefix services/control-plane exec -- wrangler deploy --help
gh api repos/actions/checkout/releases/latest --jq '{tag_name, name, published_at}'
gh api repos/actions/setup-node/releases/latest --jq '{tag_name, name, published_at}'
```

Observed results:

- PR #3, `codex/phase-launch2-ci-deploy-token-unblock-readiness`, is draft, `MERGEABLE`, and `CLEAN`.
- PR #3 `Worker typecheck and dry run` passed on run `26329438289` after the v6 action update; `Verify cloud edit deploy secrets` was skipped because the workflow was not a manual dispatch.
- PR #2, `codex/phase4h-calibrated-acceptance-gate-unblocking`, is draft, `CONFLICTING`, and `DIRTY`.
- Live staging Worker `GET /v1/editing/version` returned `404`, so live iOS kill-switch state remains unproven through the Worker.
- `.github/workflows/cloud-edit-deploy-preflight.yml` still returned `404` from `main`, so the manual deploy/rollback workflow is not runnable from the default branch yet.
- Wrangler help confirmed the current command shapes used by the deploy workflow for `deploy`, `deployments list/status`, `rollback`, and `secret list`.
- Historical docs still contain older real storage object-key evidence in several smoke reports. This branch redacts only the current launch-decision Phase Edit7e summary and records the broader scan as future cleanup.
- The Cloud Edit Deploy Preflight workflow did not run for editing deploy preflight script changes before this branch because the PR path filter watched `services/editing/cloudbuild.yaml` but not `services/editing/scripts/deploy_preflight.py`.
- The editing service deploy README omitted `_IMAGE_TAG`, which would make operator Cloud Build deploys fall back to the default `manual` tag.
- The PR dry-run emitted a GitHub Actions Node.js 20 deprecation annotation for `actions/checkout@v4` and `actions/setup-node@v4`.
- GitHub API reported current official releases `actions/checkout@v6.0.2` and `actions/setup-node@v6.4.0`.

## Files Reconciled

- `docs/phase_launch5_ios_kill_switch_status.md`
  - Changed wording from live-implied Worker proxy behavior to source-implemented behavior pending staging deploy.
  - Added a 2026-05-23 live staging refresh note for the current `404` response.
- `docs/phase_edit7f_internal_testflight_upload.md`
  - Changed the internal TestFlight lane from ready-after-upload wording to historical build 3 upload candidate wording.
  - Added the current state note that installed TestFlight proof and staging Worker refresh remain open.
  - Added staging Worker refresh to the remaining blockers.
- `docs/phase_edit7e_testflight_upload_prep.md`
  - Replaced stale "go" gate wording for the internal staging product loop, Worker URL, Cloud Run, and R2 buckets with historical RC smoke/current-proof wording.
  - Marked the final smoke evidence as historical RC evidence.
  - Replaced exact source/output/render-log object-key paths in that summary with redacted placeholders.
- `docs/phase_edit7g_post_testflight_internal_smoke.md`
  - Added the later launch audit note that live staging Worker `/v1/editing/version` still returns `404`.
  - Replaced broad healthy-backend wording with direct-backend historical proof plus Worker version-route blocker wording.
- `docs/phase_launch2_ci_deploy_token_unblock.md`, `docs/phase_launch2_ci_deploy_token_audit.md`, and `docs/phase_launch3_internal_staging_config.md`
  - Clarified that PR workflow checks are visible, but default-branch manual dispatch remains unavailable until the workflow stack lands on `main`.
- `.github/workflows/cloud-edit-deploy-preflight.yml`
  - Added `services/editing/scripts/deploy_preflight.py` to PR path filters so deploy-preflight script changes trigger the PR-safe typecheck/dry-run job.
  - Updated `actions/checkout` and `actions/setup-node` to v6 major tags to remove the Node.js 20 action-runtime deprecation warning on future runs.
- `.github/workflows/release-secrets-preflight.yml`
  - Updated `actions/checkout` to the v6 major tag for the same GitHub Actions runtime warning.
- `services/editing/README.md`
  - Added an explicit `_IMAGE_TAG` substitution to the Cloud Build command.
  - Added `--keep-vars` to the staging Worker deploy command and warned operators not to paste secret values into shell history or docs.

## No-Secret Deploy Evidence Ledger

| Item | Current evidence | Launch meaning |
| --- | --- | --- |
| PR dry-run run ID | `26329438289` | proves typecheck and staging Worker dry-run only |
| GitHub `staging` input names | no secret or variable names observed | operator inputs still required |
| Cloud Build ID | not captured | no editing Cloud Run deploy proof from this branch |
| Cloud Run revision | not captured for this branch | deployed editing service may be older than current source |
| Worker version ID | not captured | no Worker deploy proof from this branch |
| Worker rollback run ID | not captured | rollback scope not proven |

## Remaining Blockers

- Install the internal staging TestFlight build on a trusted online iPhone and run the full post-install smoke: upload/import -> cloud analysis -> Review -> Export -> AI Edit -> render -> preview -> More Hype revision -> revised preview -> share/open-in.
- Use the already published `.github/workflows/cloud-edit-deploy-preflight.yml` from `main` for GitHub Actions `workflow_dispatch`.
- GitHub `staging` environment deploy input names are now present, but full preflight/deploy/rollback proof remains required.
- Run `Cloud Edit Deploy Preflight` with `operation=preflight`, then `operation=deploy`, then `operation=rollback` with a captured previous Worker version ID.
- Refresh staging Worker and prove `GET /v1/editing/version` returns live editing service flag state through the Worker.
- Keep production cutover blocked until production Worker, Cloud Run, R2, D1, Sentry, Statsig, RevenueCat, Google config, privacy/storage copy, rollback, and beta proof gates clear.

## 2026-05-30 Credential-Check Reconciliation

Cloudflare/GCP deploy credential names are now installed enough to pass the cheap credential-only lane:

- Workflow: `Cloud Edit Deploy Preflight`
- Run ID: `26672739316`
- Ref: `main`
- Head SHA: `cf468745c18875eb5ace858c6a3e46d5c1078df9`
- Operation: `credential-check`
- Result: success

This refresh intentionally did not run full `operation=preflight`, `operation=deploy`, or `operation=rollback` to conserve GitHub Actions budget. The live staging Worker `/v1/editing/version` proof and installed TestFlight smoke remain open launch gates.

## Validation

Commands run:

```sh
git diff --check
LC_ALL=C grep -RIn '[^ -~]' .github/workflows/cloud-edit-deploy-preflight.yml services/editing/README.md docs/phase_launch_doc_reconciliation.md docs/phase_launch5_ios_kill_switch_status.md docs/phase_edit7f_internal_testflight_upload.md docs/phase_edit7e_testflight_upload_prep.md docs/phase_edit7g_post_testflight_internal_smoke.md docs/phase_launch2_ci_deploy_token_unblock.md docs/phase_launch2_ci_deploy_token_audit.md docs/phase_launch3_internal_staging_config.md || true
rg -n '<secret and presigned URL marker pattern>' .github/workflows/cloud-edit-deploy-preflight.yml services/editing/README.md docs/phase_launch_doc_reconciliation.md docs/phase_launch5_ios_kill_switch_status.md docs/phase_edit7f_internal_testflight_upload.md docs/phase_edit7e_testflight_upload_prep.md docs/phase_edit7g_post_testflight_internal_smoke.md docs/phase_launch2_ci_deploy_token_unblock.md docs/phase_launch2_ci_deploy_token_audit.md docs/phase_launch3_internal_staging_config.md
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "workflow yaml parses"'
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane run deploy:staging:dry-run
python3 -m py_compile services/editing/scripts/deploy_preflight.py
XcodeBuildMCP build_run_sim -skipPackagePluginValidation
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-doc-reconciliation-derived-data -skipPackagePluginValidation build-for-testing
```

Results:

- `git diff --check`: passed.
- ASCII scan: passed.
- Secret/presigned marker scan: only existing `CLOUDFLARE_API_TOKEN=missing` placeholder evidence matched; no secret values, R2 credentials, or full presigned URLs were added.
- Workflow YAML parse: passed.
- Control-plane typecheck: passed.
- Staging Worker dry-run: passed with staging bindings and no deploy.
- Editing deploy preflight script compile: passed.
- XcodeBuildMCP Debug simulator build/run: passed.
- iOS `build-for-testing`: passed with `** TEST BUILD SUCCEEDED **`.
- PR #3 GitHub Actions run `26329438289`: passed `Worker typecheck and dry run`; deploy-secret verification was skipped because the run was a pull request, not `workflow_dispatch`.

## Not Changed

- No local iOS video analysis, composition, rendering, or export was added.
- No Remotion or Canva path was added to iOS.
- No feature flag, kill switch, model, threshold, renderer, queue, or production launch-mode value was changed.
- No secrets, R2 credentials, or full presigned URLs were added.

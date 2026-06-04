# Phase Launch 1: Deploy and Staging Refresh

Date: 2026-06-04
Branch: codex/phase-launch1-deploy-and-staging-refresh
Latest commit: 72d54b8e0425d6a0b5f1b4071933b1479ea24abe

## Goal

Refresh HoopClips staging so the cloud-owned AI Edit path is no longer stale, and prove that the CI deploy lane can authenticate, deploy, and verify both backend services.

## Repo hygiene

Initial branch state was clean for tracked files. The following unrelated root Xcode folders were present and intentionally not staged:

- HoopsClips.xcodeproj/
- HoopsHighlightsAI.xcodeproj/

## What changed

Two launch script test gates were fixed so the deploy workflow could reach the real cloud deploy stage:

- scripts/test_build_team_highlight_eval_payload.py
- scripts/test_prepare_team_highlight_labeling_bundle.py

The first fix defined the clip fixture reused by the clip-window padding payload assertion.

The second fix normalized a macOS /var versus /private/var path comparison by comparing resolved Paths.

## Validation before deploy

Local validation:

```bash
git diff --check
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Result:

- git diff --check: pass
- script tests: 182 tests passed

## Deploy workflow

Workflow:

```bash
gh workflow run cloud-edit-deploy-preflight.yml \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref codex/phase-launch1-deploy-and-staging-refresh \
  -f operation=deploy
```

Successful run:

- Run ID: 26938436787
- URL: https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/26938436787
- Head SHA: 72d54b8e0425d6a0b5f1b4071933b1479ea24abe
- Conclusion: success

Successful jobs and gates:

- Secret-safe launch evidence snapshot: success
- Worker typecheck and dry run: success
- Editing backend Python tests: success
- Verify cloud edit deploy secrets: success
- Assert cloud deploy inputs are present: success
- Authenticate to Google Cloud: success
- Verify editing deploy preflight: success
- Verify Wrangler token authentication: success
- Verify staging Worker secret names: success
- Verify staging deployment read scope: success
- Verify staging deploy dry run with CI token: success
- Deploy staging editing service: success
- Verify direct editing version after deploy: success
- Deploy staging Worker: success
- Verify Worker editing version after deploy: success

## Independent staging probe

Command:

```bash
python3 scripts/staging_version_probe.py \
  --worker-base-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --editing-version-url https://hoopclips-editing-staging-npya43jiia-uc.a.run.app/version \
  --json
```

Result:

- status: pass
- diagnosis: staging_version_ready
- expectedGitSha: 72d54b8e0425d6a0b5f1b4071933b1479ea24abe
- Worker endpoint: hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
- Worker HTTP status: 200
- Worker gitSha: 72d54b8e0425d6a0b5f1b4071933b1479ea24abe
- Editing endpoint: hoopclips-editing-staging-npya43jiia-uc.a.run.app/version
- Editing HTTP status: 200
- Editing gitSha: 72d54b8e0425d6a0b5f1b4071933b1479ea24abe

Observed non-secret feature flags on both endpoints:

- aiClipGptEditorEnabled
- aiClipGptPlanEditEnabled
- aiClipGptRevisionEnabled
- aiEditEnabled
- aiEditFreeWatermarkRequired
- aiEditLiveRenderEnabled
- aiEditMaxDailyRenders
- aiEditProExportsEnabled
- aiEditRevisionEnabled
- aiEditTemplatePackEnabled
- gptHighlightRerankerEnabled

## Current blocker state

Resolved in this phase:

- Staging backend stale SHA blocker is resolved for this branch.
- Worker /v1/editing/version is reachable and returns HTTP 200.
- Direct editing /version is reachable and returns HTTP 200.
- Cloudflare and GCP deploy credentials were sufficient for staging deploy.
- Staging Worker and staging editing Cloud Run were both redeployed and verified.

Still open after this phase:

- Real iPhone/TestFlight smoke still needs human/device proof.
- 85% team-highlight accuracy proof is still not met.
- Production release secret preflight still needs production HOOPS_CLOUD_ANALYSIS_BASE_URL and HOOPS_CLOUD_EDIT_BASE_URL values.
- Production cutover remains blocked until TestFlight smoke, accuracy proof, and production release inputs are complete.

## Next recommended branch

The next highest-leverage product-quality branch is:

```text
codex/phase-clip1-gpt-led-highlight-editor
```

That branch should improve final clip selection quality using GPT as the semantic editor/director over sampled keyframes and compact metadata, while keeping CV as the high-recall candidate source and backend validation as the safety gate.

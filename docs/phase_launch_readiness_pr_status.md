# Phase Launch Readiness PR Status

Date: 2026-05-23
Branch: `codex/phase-launch-readiness-pr-status`

## Current GitHub State

Draft PR opened for the current launch stack:

- PR: https://github.com/charlie2233/rork-hoopshighlights-ai_Final/pull/3
- Head: `codex/phase-launch2-ci-deploy-token-unblock-readiness`
- Base: `main`
- Mode: draft
- Purpose: make the internal TestFlight/cloud-editing readiness stack reviewable and publish `.github/workflows/cloud-edit-deploy-preflight.yml` to `main` after approval.

Existing separate PR:

- PR: https://github.com/charlie2233/rork-hoopshighlights-ai_Final/pull/2
- Head: `codex/phase4h-calibrated-acceptance-gate-unblocking`
- Base: `main`
- GitHub merge state observed as `CONFLICTING` / `DIRTY`.
- This branch is not an ancestor of the current launch-readiness stack, and the current launch-readiness stack is not an ancestor of that branch.

## Evidence

Commands run:

```sh
git status --short --branch
git log --oneline --decorate -10
git merge-base --is-ancestor origin/main HEAD
git diff --check origin/main...HEAD
gh pr list --repo charlie2233/rork-hoopshighlights-ai_Final --state open --json number,title,headRefName,baseRefName,isDraft,url
gh pr view 2 --repo charlie2233/rork-hoopshighlights-ai_Final --json number,title,headRefName,baseRefName,isDraft,mergeStateStatus,reviewDecision,url,commits,files
git merge-tree --write-tree HEAD origin/codex/phase4h-calibrated-acceptance-gate-unblocking
```

Results:

- Local branch before this doc: `codex/phase-launch2-ci-deploy-token-unblock-readiness`.
- `origin/main` is an ancestor of the launch-readiness stack.
- `git diff --check origin/main...HEAD`: passed.
- Draft PR #3 was created successfully and was observed as `MERGEABLE` / `UNSTABLE`.
- PR #2 was observed as `CONFLICTING` / `DIRTY`.
- PR #3 is based on current `origin/main`; PR #2 is stale from an older `main` base and is missing current `main` history.
- A dry merge-tree probe of current launch stack plus PR #2 reported conflicts in:
  - `.gitignore`
  - `AGENTS.md`
  - `ios/HoopsClips.xcodeproj/project.pbxproj`
  - `ios/HoopsClips/HoopsClips/ContentView.swift`
  - `ios/HoopsClips/HoopsClips/HoopsClipsApp.swift`
  - `ios/HoopsClips/HoopsClips/Models/CloudAnalysisTypes.swift`
  - `ios/HoopsClips/HoopsClips/Services/AppConstants.swift`
  - `ios/HoopsClips/HoopsClips/Services/AppRuntimeConfig.swift`
  - `ios/HoopsClips/HoopsClips/Services/AuthService.swift`
  - `ios/HoopsClips/HoopsClips/Services/CloudAnalysisService.swift`
  - `ios/HoopsClips/HoopsClips/Services/SubscriptionManager.swift`
  - `ios/HoopsClips/HoopsClips/ViewModels/HighlightsViewModel.swift`
  - `ios/HoopsClips/HoopsClips/Views/PaywallView.swift`
  - `ios/HoopsClips/HoopsClips/Views/VideoPlayerView.swift`
  - `ios/HoopsClipsTests/HoopsClipsTests.swift`
  - `ios/backend/README.md`
  - `scripts/control-plane-harness.ts`
  - `services/control-plane/README.md`
  - `services/control-plane/package.json`
  - `services/control-plane/src/env.ts`
  - `services/control-plane/src/routes/public.ts`
  - `services/control-plane/src/types.ts`
  - `services/control-plane/wrangler.jsonc`

## Launch No-Go Summary

Read-only follow-up audits confirmed the current internal launch state:

- Installed TestFlight end-to-end proof is still blocked on a trusted online iPhone with the internal staging build installed.
- The staging Worker still does not expose `/v1/editing/version` live, even though the source route and proxy tests exist locally.
- `.github/workflows/cloud-edit-deploy-preflight.yml` exists on the launch stack but is not yet on `main`, so the GitHub Actions deploy workflow cannot be manually run from the default branch.
- GitHub has `production` and `staging` environments, but no staging deploy secret or variable names were observed.
- Local Wrangler auth is not available, and no local `CLOUDFLARE_API_TOKEN` is present.
- Editing Cloud Run `/version` responds, but the deployed response appears older than current source because GPT reranker readiness is not reflected live.
- Static launch config preflight remains green with warnings only; production cutover remains intentionally blocked.
- Release iOS config remains cloud-disabled, while internal staging config is the intended cloud-enabled TestFlight overlay.

Additional cheap validation observed by the audits:

```sh
python3 scripts/launch_backend_config_preflight.py --json
python3 services/editing/scripts/deploy_preflight.py --json
npm --prefix services/control-plane run deploy:staging:dry-run
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-editing-proxy.test.ts
PYTHONPATH=ios/backend:services/editing ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker -v
```

Observed results:

- Launch backend config preflight: `57 pass`, `12 warn`, `0 fail`.
- Editing deploy preflight: blocked only on Wrangler auth.
- Control-plane staging dry-run: passed.
- Control-plane typecheck: passed.
- Control-plane editing proxy test: `11 pass`.
- GPT reranker tests: `7 pass`.
- Direct Cloud Run `/version`: `200`.
- Worker `/v1/editing/version`: `404`.

## Stale Documentation To Reconcile

- `docs/phase_launch5_ios_kill_switch_status.md` should say the Worker proxy route is implemented in source but not deployed to staging.
- `docs/phase_edit7f_internal_testflight_upload.md` should be treated as historical upload evidence, not current installed TestFlight proof.
- `docs/phase_edit7e_testflight_upload_prep.md` contains historical storage object-key evidence and should be marked historical/operator-only if touched again.
- `docs/phase_launch1_testflight_smoke_readiness.md` remains current: installed TestFlight smoke and stale Worker route are still blockers.

## Recommended Sequencing

1. Keep PR #3 as draft until real TestFlight smoke and deploy-token blockers are resolved or explicitly accepted for internal beta.
2. Land PR #3 first if the remaining launch blockers are accepted for internal review, because it is current-base and clean aside from CI/status.
3. Preserve PR #2 as historical source work. Do not force-rebase it directly; create a fresh integration branch from updated `main` after PR #3 lands, then merge PR #2 into that branch and resolve conflicts with launch-readiness behavior as the baseline.
4. If PR #3 cannot land first and Phase 4h must ship immediately, create a replacement integration branch from `codex/phase-launch2-ci-deploy-token-unblock-readiness` and merge PR #2 there.
5. After PR #3 reaches `main`, rerun `Cloud Edit Deploy Preflight` from GitHub Actions with the `staging` environment populated.
6. Use the workflow to prove `preflight`, `deploy`, and `rollback` before claiming CI deploy unblock.

## Remaining Blockers

- Physical TestFlight smoke still requires a trusted online iPhone with the internal staging build installed.
- GitHub `staging` environment has no observed deploy secret or variable names.
- Local Wrangler auth is not valid, and no `CLOUDFLARE_API_TOKEN` is available locally.
- PR #2 integration is unresolved and conflict-prone if Phase 4h must ship with this stack.

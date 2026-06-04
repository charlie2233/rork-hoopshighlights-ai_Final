# Phase Launch Current-Head Evidence Handoff - 2026-06-04

This handoff records the current `codex/phase-launch-proof-next` evidence after
repairing the History screen build regression. It is not a launch-ready signoff.

## Current head

- Branch: `codex/phase-launch-proof-next`
- Head: `b8e02e7` (`ios: fix history playback smoke id build`)
- Local tracked state: clean
- Preserved unrelated untracked files:
  - `HoopsClips.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved`
  - `HoopsHighlightsAI.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved`

## Current-head workflow evidence

- Cloud Edit Deploy Preflight:
  - Run: `26924348734`
  - Head: `b8e02e7`
  - Result: `success`
  - Passed jobs: editing backend Python tests, secret-safe launch evidence
    snapshot, Worker typecheck and dry run
  - Skipped jobs: cloud deploy credential/deploy secret checks, so provider-auth
    launch readiness is still not proven
- iOS Internal TestFlight Upload:
  - Run: `26924349863`
  - Head: `b8e02e7`
  - Result: `success`
  - Passed job: no-secret internal staging codecheck
  - Skipped job: internal staging TestFlight archive, so signed archive/upload
    proof is still not complete
- Release Secrets Preflight:
  - Run: `26924347628`
  - Head: `b8e02e7`
  - Result: `failure`
  - Missing production variables:
    - `HOOPS_CLOUD_ANALYSIS_BASE_URL`
    - `HOOPS_CLOUD_EDIT_BASE_URL`

## Branch workflow refresh

After the evidence handoff and main-refresh documentation updates, the launch
branch workflows were rerun on branch commit `021994d`.

- Branch Cloud Edit Deploy Preflight:
  - Run: `26925293779`
  - Head: `021994d`
  - Result: `success`
  - Passed jobs: editing backend Python tests, secret-safe launch evidence
    snapshot, Worker typecheck and dry run
  - Skipped jobs: cloud deploy credential/deploy secret checks, so provider-auth
    launch readiness is still not proven
- Branch iOS Internal TestFlight Upload:
  - Run: `26925294949`
  - Head: `021994d`
  - Result: `success`
  - Passed job: no-secret internal staging codecheck
  - Skipped job: internal staging TestFlight archive, so signed archive/upload
    proof is still not complete
- Branch Release Secrets Preflight:
  - Run: `26925292785`
  - Head: `021994d`
  - Result: `failure`
  - Missing production variables:
    - `HOOPS_CLOUD_ANALYSIS_BASE_URL`
    - `HOOPS_CLOUD_EDIT_BASE_URL`

## Production cloud URL decision boundary

The current non-secret GitHub `production` environment variable check still
shows only:

- `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy`
- `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms`

The production environment still does not expose:

- `HOOPS_CLOUD_ANALYSIS_BASE_URL`
- `HOOPS_CLOUD_EDIT_BASE_URL`

These are GitHub environment variables, not masked secrets, but setting them is
still a release decision. `Release Secrets Preflight` requires
`HOOPS_CLOUD_LAUNCH_MODE=enabled` plus non-empty production cloud analysis/edit
URLs, and `ios/docs/runbooks/public-launch-cloud-gated.md` says the correct
decision is no-go if production cloud endpoints are not ready.

Do not set the internal staging Worker as either production URL unless the
release owner explicitly confirms that internal TestFlight Release builds should
point at that staging Worker for this gate. Until then, keep Release Secrets
Preflight red and keep signed archive/upload and installed TestFlight smoke
blocked.

## Provider-auth credential refresh

The cloud deploy provider-auth gate was advanced on branch commit `e26f05d`
without running a deploy.

- Cloud Edit Deploy Preflight `operation=credential-check`:
  - Run: `26927251153`
  - Head: `e26f05d`
  - Result: `success`
  - Passed jobs: `Verify cloud deploy credentials only`, secret-safe launch
    evidence snapshot
  - Skipped jobs: Worker dry run, backend Python tests, and cloud edit deploy
    secret verification, as expected for credential-check mode
- Cloud Edit Deploy Preflight `operation=preflight`:
  - Run: `26927305142`
  - Head: `e26f05d`
  - Status at handoff update: `in_progress`
  - Completed jobs at handoff update: secret-safe launch evidence snapshot
    `success`, Worker typecheck and dry run `success`
  - Pending job at handoff update: editing backend Python tests
  - No deploy operation was run

This means provider credential access is no longer merely skipped/unproven, but
provider-auth launch readiness is still not fully closed until the non-deploy
preflight finishes green and the release owner approves any later deploy step.

## Main-branch workflow refresh

The stale June 1 main-branch failures were refreshed with workflow-dispatch
runs on `main` after this branch had already collected current-head evidence.
These runs are useful freshness evidence for main, but they are not proof that
the current checkout commit has landed on main.

- Main Cloud Edit Deploy Preflight:
  - Run: `26924985793`
  - Head: `311d518`
  - Result: `success`
  - Passed jobs: Worker typecheck and dry run, editing backend Python tests
  - Skipped jobs: cloud deploy credential/deploy secret checks, so provider-auth
    launch readiness is still not proven
- Main iOS Internal TestFlight Upload:
  - Run: `26924987135`
  - Head: `311d518`
  - Result: `success`
  - Passed job: no-secret internal staging codecheck
  - Skipped job: internal staging TestFlight archive, so signed archive/upload
    proof is still not complete
- Submission preflight still failed both main workflow checks at refresh time
  because the latest main runs were for `311d518`, not the branch checkout
  commit `1428776`. Rerun the required workflows after the launch branch lands
  on main or collect equivalent current-checkout submission evidence before
  claiming readiness.

## Snapshot evidence

The secret-safe launch evidence snapshot from Cloud Edit Deploy Preflight run
`26924348734` reports:

- `gitHead=b8e02e7`
- `launchReady=false`
- `openBlockers=11`
- `history.emptyState` is present in the smoke selector inventory
- `history.detail.playback` is present in the smoke selector inventory
- `17` import/history smoke selectors are listed

## Submission preflight evidence

Command:

```bash
python3 scripts/submission_readiness_preflight.py \
  --skip-live \
  --archive-path /Users/hanfei/rork-hoopshighlights-ai_Final/artifacts/testflight/HoopClips.xcarchive \
  --json
```

Result:

- Overall status: `fail`
- Summary: `17` fail, `25` pass, `3` warn
- The requested archive path does not exist, so signed archive evidence is
  missing
- One available iPhone was detected for installed TestFlight smoke, but installed
  TestFlight smoke remains unproven until a signed build is uploaded and tested
- Team highlight accuracy evidence remains blocked by incomplete human-reviewed
  labels: `0/54` clips complete
- The label bundle still needs regeneration or completion before review because
  launch-required human label fields are missing or incomplete

## Still-open launch gates

- Add production cloud URL variables in the release environment:
  - `HOOPS_CLOUD_ANALYSIS_BASE_URL`
  - `HOOPS_CLOUD_EDIT_BASE_URL`
- Prove provider-auth deploy readiness with the secret-gated cloud credential
  check or deploy preflight job
- Produce a signed App Store Connect archive/upload proof
- Install the TestFlight build on a trusted device and smoke the real user path
- Complete human review for all launch label clips and rebuild the
  launch-grade team accuracy report
- Prove live backend status, cloud job-state reporting, render reliability, and
  finished MP4 preview/download/share/open-in-editor behavior with real evidence

## Label bundle refresh

The local label review bundle was regenerated from the current scripts on
2026-06-04 with:

```bash
python3 scripts/prepare_team_highlight_labeling_bundle.py \
  --manifest artifacts/team_highlight_accuracy_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output-dir artifacts/team_highlight_labeling_bundle \
  --json
```

After regeneration, submission preflight no longer reports the bundle as stale
or missing launch checklist markers. The accuracy gate still fails, correctly:
the regenerated bundle remains `0/54` clips complete and all launch-required
human label fields still need review before the accuracy report can count.

## Safe next actions

1. Set the two missing production cloud URL variables using secret-safe account
   handling, then rerun Release Secrets Preflight.
2. Trigger the cloud credential-check/preflight path with provider auth enabled,
   without printing secret values.
3. Build and upload the signed internal TestFlight archive, then run installed
   smoke on the detected iPhone.
4. Regenerate or complete the label review bundle, finish all human labels, and
   rebuild the launch-grade accuracy report.

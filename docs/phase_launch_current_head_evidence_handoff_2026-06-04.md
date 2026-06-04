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

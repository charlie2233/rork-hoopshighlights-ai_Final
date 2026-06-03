# Phase Main Sync Handoff (2026-06-03)

## Purpose

Record the current branch-to-main state before any `main` update so the launch-readiness branch can be landed deliberately and without confusing workflow evidence.

## Current Branch Evidence

- Working branch: `codex/phase-launch-proof-next`
- Latest pushed commit: `c8d64c9 chore: tighten readiness diagnostics before merge`
- Remote sync state from the last inspection: branch was `0` commits behind `origin/main` and `25` commits ahead.
- Local dirty state at inspection time only included preserved untracked root Xcode folders:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`
- Those root folders are unrelated local artifacts and must not be staged as part of launch-readiness work.

## Why Main Still Needs A Deliberate Update

The launch branch contains code-side fixes for the latest observed main workflow failures, but those failures remain authoritative for `main` until the branch is landed and the workflows rerun.

- Latest observed main `Cloud Edit Deploy Preflight` failure:
  - Run: `26766947519`
  - Created: `2026-06-01T16:11:23Z`
  - Root cause from logs: main expected `team_quick_scan_max_candidate_clips=160`, while the current launch config expects `320`.
  - Branch status: fixed on `codex/phase-launch-proof-next`; not proven on `main` until landed and rerun.
- Latest observed main `iOS Internal TestFlight Upload` failure:
  - Run: `26766947563`
  - Created: `2026-06-01T16:11:23Z`
  - Root cause from logs: main expected `CURRENT_PROJECT_VERSION=11`, while the current internal staging build is `14`.
  - Branch status: fixed on `codex/phase-launch-proof-next`; not proven on `main` until landed and rerun.

## Safe Main-Sync Gate

Before updating `main`, confirm all of the following:

- `git fetch origin` succeeds.
- `git status --short --branch` shows no tracked dirty files and only the known unrelated untracked root Xcode folders.
- `git rev-list --left-right --count origin/main...HEAD` still reports `0` behind.
- The branch tip is still the intended launch-readiness commit.
- The operator explicitly approves updating `main`.

If all checks pass and approval is explicit, the intended next action is a fast-forward style main update followed by rerunning the failed main workflows. Do not force-push `main`.

## Still Not Launch-Ready After Main Sync

Even after `main` is updated, launch readiness remains blocked until these gates are proven:

- Human-reviewed team/highlight labels are complete and the launch accuracy report is rebuilt from real reviewed labels.
- The direct editing service deploy reports the current source SHA.
- Secret-gated cloud deploy proof runs successfully instead of being skipped.
- An installed TestFlight build completes the full real-device smoke: import, team/edit intent, cloud analysis, GPT-led selections, review, render, preview, download, share/open.
- Public cloud cutover remains blocked until production auth, storage, observability, rollback, accuracy evidence, and installed TestFlight proof are all complete.

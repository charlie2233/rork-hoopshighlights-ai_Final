# Phase Launch95 Current Readiness Test Sweep

Date: 2026-05-31
Branch: `codex/phase-launch70-editing-analysis-progress`
Head: `bff6d08` (`Document direct editing staging deploy`)

## Goal

Capture the current launch-readiness state after the Spark review note, the direct editing staging deploy, and the local validation sweep. This document is evidence only; it does not mark HoopClips ready for App Store/TestFlight submission.

## Spark Review Triage

Reviewed the Spark notes against the current branch.

- The Photos import `Data.self` fallback concern is stale on this branch. `ImportedVideoFile` is file-backed and accepts `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`.
- The temp filename interpolation concern is stale. The current import path uses a UUID plus the resolved extension.
- The CloudEditService request-body test concern is stale. The focused simulator test suite for `CloudEditServiceTests` passed.
- The main-thread import concern looks mitigated for the current branch: UI state changes are routed through `MainActor`, while copy/transfer work uses background tasks.
- Remaining low-risk cleanup: the four file-backed `FileRepresentation` entries use the same import behavior and could be collapsed later, but this is not a launch blocker.

## Submission Preflight

Command:

```bash
python3 scripts/submission_readiness_preflight.py \
  --archive-path ios/archives/HoopsClips-Launch72.xcarchive \
  --json
```

Result: `28 pass / 6 fail / 0 warn`

Still failing:

- Launch-grade team highlight accuracy report is missing; 85% selected-team/highlight quality is unproven.
- A real iPhone is detected but unavailable for install/smoke testing. CoreDevice reports paired + Developer Mode enabled, but tunnel unavailable and DDI services unavailable.
- Latest main-branch Cloud Edit Deploy Preflight run is stale versus current checkout.
- Latest main-branch iOS Internal TestFlight Upload run is stale versus current checkout.
- Latest manually dispatched Cloud Edit Deploy Preflight run is stale versus current checkout.
- Installed TestFlight post-install smoke remains unproven.

Passing highlights:

- Staging backend/config preflight has no failures.
- Internal TestFlight export options are configured.
- Staging Worker and direct editing service return non-secret AI Edit kill-switch state.
- Live direct editing service is on an older git SHA, but no editing-service deploy-relevant files changed after that deploy.
- Required deploy/upload input names are present locally or in the GitHub staging environment without printing secret values.

## Team Accuracy Gate

Command:

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --label-status \
  --json
```

Current state from the latest label-status check:

- Cases: `3`
- Clips: `66`
- Complete clips: `0`
- Incomplete clips: `66`
- Remaining missing field: `needsLabel=false`
- Review page: `artifacts/team_highlight_accuracy_launch71_review.html`

The GPT draft labels exist, but human review is still required before this can count as launch-grade accuracy evidence.

## Local Validation

Commands run locally to conserve GitHub Actions minutes:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Result: `131` tests passed.

```bash
PYTHONPATH=ios/backend:services/editing \
  /tmp/hoopclips-py312-venv/bin/python -m unittest discover \
  -s ios/backend/tests -p 'test_*.py'
```

Result: `210` tests passed.

```bash
PYTHONPATH=ios/backend:services/editing \
  /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover \
  -s services/editing/tests -p 'test_*.py'
```

Result: `117` tests passed.

```bash
npm --prefix services/control-plane test
```

Result: `33` tests passed.

```bash
npm --prefix services/control-plane run typecheck
```

Result: passed.

Focused Build iOS Apps simulator test:

```text
HoopsClipsTests/CloudEditServiceTests
```

Result: `11` tests passed.

## Honest AI Status Copy

The app should use real job-stage language such as analyzing candidates, choosing team-specific highlights, checking duplicates, rendering, and preparing preview. It should not add fake thinking loops, fake ETA, artificial waits, or pretend backend work. This matches the cloud-first launch rule and keeps the product trustworthy while still making long-running AI work understandable.

## Current Blockers

1. Finish human review for all launch71 team-label clips and generate `artifacts/team_highlight_accuracy_launch71_report.json`.
2. Reconnect the physical iPhone so CoreDevice reports it available, then run the installed TestFlight smoke: install/import/upload/cloud analysis/review/export/AI Edit/render/preview/revision/share.
3. Rerun only the required GitHub Actions on the current branch/main when the branch is ready, to conserve Actions budget.
4. After the accuracy and device smoke gates pass, update the final launch report and decide whether to merge into `main`.

## Recommendation

Do not submit to Apple yet. The backend and local test surface are strong, but the launch plan still requires human-labeled accuracy proof, a physical-device TestFlight smoke, and current CI evidence.

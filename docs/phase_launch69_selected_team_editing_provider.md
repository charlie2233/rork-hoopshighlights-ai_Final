# Phase Launch69 Selected-Team Editing Provider

Date: 2026-05-30
Branch: `codex/phase-launch69-selected-team-editing-provider`
Base: `main` at `ec2bafe`

## Scope

Fix the remaining staging selected-team analysis timeout after the Launch68 heartbeat deploy.

Real staging evidence:

- Launch68 deployed SHA: `ec2bafef0702b480fb6e9113f3d49df94853c95c`
- Deploy run: `26693005243`
- Version probe: Worker and editing service both reported `ec2bafef0702b480fb6e9113f3d49df94853c95c`
- Accuracy collection job: `8ba54df62559416f8df7bc7439c34456`
- Final state: `failed_timeout`
- Failure reason: `Inference callback timed out after 3 accepted attempts.`
- Provider evidence: job `modelVersion` remained `videomae:MCG-NJU/videomae-base-finetuned-kinetics`, so the selected-team job was still accepted by the legacy inference path instead of the editing backend that now sends heartbeats.

## Root Cause

The control-plane queue dispatcher ordered providers as legacy inference first, editing fallback second. In test, legacy rejected selected-team dispatch with a fallback-compatible status. In real staging, legacy accepted the selected-team job and then never produced the callback, so fallback never happened.

## Changes

- Selected-team analysis now dispatches directly to the editing backend when editing is configured.
- Legacy inference remains first for non-selected-team/all-teams jobs.
- If selected-team analysis is requested without an editing provider, the queue dispatch fails closed instead of silently using the wrong provider.
- Updated the selected-team dispatch regression test to prove legacy inference is not called and editing receives the full Worker analysis request.

## Architecture

- Cloud backend still owns team filtering, analysis, callbacks, GPT-assisted editing, rendering, and storage.
- iOS behavior is unchanged.
- The legacy inference provider can continue serving compatible all-teams/non-team analysis.
- Selected-team analysis uses the editing backend because it owns the selected-team pipeline and heartbeat-capable `/v1/analyze` endpoint.

## Validation

Commands run:

```bash
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test -- --test-name-pattern 'routes selected-team analysis directly|preserves selected team|selected team|timeout|heartbeat'
cd services/control-plane && npx prettier --check src/queue/consumer.ts test/control-plane-status-transitions.test.ts
git diff --check
```

Results:

- Control-plane typecheck passed.
- Focused selected-team/timeout/heartbeat control-plane tests passed: 31 tests.
- Diff whitespace check passed.
- Prettier check passed for touched control-plane files.

Expected staging proof after deploy:

```bash
python3 scripts/staging_version_probe.py --expected-git-sha <deployed-sha> --json
python3 scripts/collect_team_highlight_accuracy_case.py --video-path /Users/hanfei/Downloads/326_1770329282.mp4 --case-id launch69_downloads_326_team --video-id downloads_326_1770329282 --team-mode team --duration-seconds 30 --output-dir artifacts/team_highlight_accuracy_launch69 --manifest artifacts/team_highlight_accuracy_launch69_manifest.json --poll-interval-seconds 5 --timeout-seconds 1800
```

# Phase 4h Family Gate Smoke Report

## Scope

- Branch: `codex/phase4h-family-gate-suppression-fix`
- Date: `2026-04-11`
- Endpoint: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Cloud Run revision: `hoopsclips-inference-staging-00034-xtc`
- Inference version: `phase4h-family-gate-suppression-fix`
- Shadow source: `runtimeFusionTemporalShadow`
- Smoke size: `12` completed Worker-path uploads, producing `18` clip windows.
- Eval artifact: `services/inference/evals/phase4h_smoke/shadow_eval_report.json`

The staging service was deployed with the requested family-gate settings from the branch:

- family temperature: `1.0`
- family top-1 threshold: `0.42`
- family top-2 margin threshold: `0.02`
- spotter rescue max delta: `0.08`

## Smoke Gate Result

| Gate | Target | Observed | Result |
| --- | --- | ---: | --- |
| No crashes / null shadow payloads | `0` failures | `0` failures, `0` null shadow payloads | `PASS` |
| Proposal accepted count | `> 0` | `3` | `PASS` |
| Family gate open count | `> 0` | `3` | `PASS` |
| Shot head invocation count | `> 0` | `3` | `PASS` |
| No all-dunk/made collapse | no single positive subtype collapse | `Made Shot=3`, `Highlight=15`, subtype abstained | `PASS` |
| Miss-to-made drift | `0` | `0` | `PASS` |
| Single flat-label dominance | `<= 0.80` | `0.8333` (`Highlight`) | `FAIL` |

## Core Metrics

- Clip windows evaluated: `18`
- Proposal acceptance rate: `0.1667`
- Family gate open rate: `0.1667`
- Shot head invocation rate: `0.1667`
- Flat label distribution: `{"Highlight": 15, "Made Shot": 3}`
- EventFamily distribution: `{"other": 15, "shot_attempt": 3}`
- Outcome distribution: `{"uncertain": 15, "made": 3}`
- Raw eventFamily=other rate: `0.8333`
- Uncertainty rate: `1.0000`
- Miss-vs-made confusion: `{"expectedMadePredictedHighlight": 0, "expectedMadePredictedMiss": 0, "expectedMissPredictedHighlight": 0, "expectedMissPredictedMadeShot": 0}`
- Accepted shot outputs: `3` made outcomes, no concrete subtype emitted.

## Decision

**No-go for `codex/phase4h-acceptor-coverage-lift` creation from this smoke.**

The smoke proves the family-gate suppression fix is live and accepted proposals can reach the shot stack safely. It does not satisfy the smoke dominance guard because `Highlight` remains at `83.33%`, above the `80%` cap. This is still a coverage problem: acceptance improved enough to unblock the shot path, but not enough to justify starting the acceptance-lift branch as a passed-smoke follow-on.

## Next Step

Hold on branch creation and rerun a smaller smoke only after either:

- the smoke manifest is balanced to avoid repeated demo windows overwhelming the denominator, or
- acceptance coverage is lifted in a deliberately separate branch once the user approves proceeding despite this smoke no-go.

Do not run a medium `60-80` clip batch yet. The result justifies no detector-family change and no SpaceJam work, but it does not justify larger-batch promotion.

## Commands

```bash
gcloud builds submit services/inference --config services/inference/cloudbuild.yaml --substitutions _VERSION=phase4h-family-gate-suppression-fix

node --experimental-strip-types scripts/control-plane-shadow-batch.ts \
  --base-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --manifest /tmp/phase4h-smoke/manifest.json \
  --output-dir /tmp/phase4h-smoke/batch \
  --poll-timeout-seconds 240 \
  --poll-interval-seconds 2

PYTHONPATH=. uv run --with-requirements services/inference/requirements.txt python3 \
  services/inference/scripts/run_shadow_eval.py \
  --batch-results /tmp/phase4h-smoke/batch/0{1,2,3,4,5,6,7,8,9}-*.json /tmp/phase4h-smoke/batch/1{0,1,2}-*.json \
  --shadow-source runtimeFusionTemporalShadow \
  --output-dir /tmp/phase4h-smoke/report_18clips
```

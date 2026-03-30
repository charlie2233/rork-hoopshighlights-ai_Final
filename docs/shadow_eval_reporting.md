# Shadow Eval Reporting

Use the shadow-eval report when you want to measure a live staging batch or a local mixed batch without changing the runtime control-plane contract.

## What it records

- `jobId`
- `requestId`
- `uploadTraceId`
- `inferenceAttemptId`
- `modelVersion`
- flat label distribution
- `eventFamily` distribution
- `shotSubtype` distribution
- `outcome` distribution
- uncertainty rate
- miss-vs-made confusion
- mixed-batch label spread
- raw VideoMAE and X-CLIP top-k suggestions when present

## Input shape

The script accepts one or more JSON files. Each file may be:

- a job response with a top-level `clips` array
- a manifest wrapper with `result.clips`
- a flat array of clip rows

For best results, include the live staging fields on each clip row:

- `clipId`
- `label` or `finalLabel`
- `eventFamily`
- `shotSubtype`
- `outcome`
- `confidence`
- `confidenceBeforeMapping`
- `confidenceAfterMapping`
- `clipDurationSeconds`
- `wasMerged`
- `sourceEventCount`
- `rawTopLabels`
- `comparisonRawTopLabels`

If `expectedLabel` is present, the report also records miss-vs-made confusion against the expected label.

## Comparison mode

To compare a LoRA shadow batch against the phase3d baseline, pass the baseline batch separately:

```bash
python3 services/inference/scripts/run_shadow_eval.py \
  --baseline-results /tmp/phase3d/*.json \
  --batch-results /tmp/phase3d1-lora/*.json \
  --output-dir /tmp/phase3d1-lora/report
```

The report then includes:

- baseline summary metrics
- candidate summary metrics
- a direct delta section for flat-label spread, highlight dominance, uncertainty, and miss-vs-made confusion

This is the preferred workflow for shadowing encoder-adaptation or other rollout experiments against phase3d.

## Command

```bash
python3 services/inference/scripts/run_shadow_eval.py \
  --batch-results /tmp/hoops-shadow/*.json \
  --output-dir /tmp/hoops-shadow/report
```

The command writes:

- `shadow_eval_report.json`
- `shadow_eval_report.md`

## Interpretation

Shadow eval is the staging/local equivalent of a live watchability review. A healthy mixed batch should:

- show more than two flat labels
- keep miss clips out of `Made Shot`
- use `Highlight` only as a fallback, not as the dominant outcome
- keep uncertainty visible, but not overwhelming

If the batch still collapses to a single generic label, inspect the raw VideoMAE and X-CLIP suggestions first. If those are already generic, the next step is runtime model improvement rather than report tuning.

# SpaceJam Auxiliary Pretraining Plan

## Goal

Use SpaceJam only as an offline auxiliary-pretraining source for future recall-oriented work. This branch is not part of the Phase 4h rollout path and does not change the deployed runtime contract, shadow payload schema, acceptor thresholds, family-gate logic, or outcome mapping.

## Scope Guardrails

- Training-path only.
- No runtime, Worker, iOS, or label-contract changes.
- Clip modality only in v1.
- Ignore SpaceJam joints in v1.
- Keep all behavior behind the separate config at `services/inference/configs/spacejam_aux_pretrain_v1.json`.
- Use SpaceJam only for representation / proposal-oriented auxiliary pretraining, then fine-tune on HoopsClips data with the existing taxonomy.

## Conservative Label Mapping

- `Shoot` -> `shot_candidate_aux`
- `No Action` -> `coarse_non_event_aux`
- All other SpaceJam classes remain unmapped by default.

This keeps the auxiliary task intentionally coarse and avoids leaking ambiguous single-player action classes into the HoopsClips taxonomy.

## Training-Only Adapter

The adapter lives in [spacejam_aux_pretrain.py](/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/spacejam_aux_pretrain.py). It:

- reads JSON or JSONL SpaceJam manifests
- keeps only clip rows
- drops joint rows by default
- resolves local clip paths if a clip root is provided
- records summary counts for mapped rows, skipped labels, and unavailable videos

## Experiment Flow

1. Prepare a local SpaceJam manifest and clip directory outside the mainline datasets.
2. Point `services/inference/configs/spacejam_aux_pretrain_v1.json` at that manifest.
3. Run the experiment harness:

```bash
uv run --with-requirements services/inference/requirements.txt \
  python3 services/inference/scripts/run_spacejam_aux_pretrain_experiment.py \
  --config services/inference/configs/spacejam_aux_pretrain_v1.json \
  --output-dir services/inference/evals/spacejam_aux_pretrain_v1
```

4. If the manifest or clips are missing, the run aborts cleanly and writes a blocked report.
5. If the dataset is present, use the generated summary to decide whether to proceed with a separate offline pretraining job. Do not wire any resulting weights into the deployed Phase 4h runtime path from this branch.

## Metrics To Compare Before Any Follow-On Use

- proposal acceptance rate
- family gate open rate
- shot head invocation rate
- dominant flat-label share
- raw `eventFamily=other`
- Brier score / ECE-lite proxy

## Abort Conditions

Abort the experiment if any future offline run shows:

- worse calibration
- higher dominant flat-label share
- lower family-gate open rate
- worse uncertainty or collapse behavior

## Current State

- The adapter, config gate, and blocked-report harness are in place.
- The branch does not reroute or reopen PR #2.
- The branch does not modify the current Phase 4h rollout path.
- A truthful after-run comparison still requires a local SpaceJam clip export.

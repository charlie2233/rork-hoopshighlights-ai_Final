# Phase 3e Live Shadow Rollout Report

Date: 2026-03-31
Branch: `codex/phase3e-basketball-specific-runtime-encoder`

## Staging rollout

- Control plane Worker: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Durable inference service: `https://hoopsclips-inference-staging-568888872909.us-central1.run.app`
- Ready revision after rollout: `hoopsclips-inference-staging-00006-p9m`
- Runtime mode:
  - primary runtime fusion: `off`
  - temporal encoder shadow: `on`
  - distilled clip encoder shadow: `off`
  - VideoMAE LoRA live mode: `off`

## Operational fixes applied

- Created the missing GCP Secret Manager entries for:
  - `HOOPS_INFERENCE_R2_ACCESS_KEY_ID`
  - `HOOPS_INFERENCE_R2_SECRET_ACCESS_KEY`
- Granted `roles/secretmanager.secretAccessor` to `568888872909-compute@developer.gserviceaccount.com`
- Updated staging Cloud Run capacity to avoid `429` dispatch failures:
  - `minScale=1`
  - `maxScale=2`
  - `containerConcurrency=1`

## End-to-end smoke

### API smoke

- Smoke job id: `19a99cd48a4940ba84c7d2fc5fe8714c`
- Request ids:
  - presign: `f0029aa2-c980-450e-8500-1362170bf7ea`
  - finalize: `d1d4e88a-e21f-4af5-aa3d-50ea35115f08`
  - poll: `9da595d9-f1a5-415a-a39c-66e3ab5d6825`
- Upload trace id: `7509befe7dc747cbb0e8d009c5a4060c`
- Inference attempt id: `c1daa643096042709f99904ef74c4ada`
- Final status: `completed`
- Final flat label: `Highlight`
- Live shadow namespace present: `runtimeFusionTemporalShadow`

### Simulator smoke

- Automation mode used:
  - `HOOPS_AUTOMATION_ENABLED=1`
  - `HOOPS_AUTOMATION_AUTH_MODE=guest`
  - `HOOPS_AUTOMATION_SAMPLE_VIDEO_PATH=/tmp/phase3d1-batch/clips/demo_02_8.0.mp4`
  - `HOOPS_AUTOMATION_AUTO_ANALYZE=1`
- Simulator job id: `d74f17a9958d406aaed2cb54a91b627a`
- Request id: `3b77f6f4-49e6-4d5e-b9f2-a91198d41159`
- Upload trace id: `4302f3454d314920bffe42338e53842c`
- Inference attempt id: `5f7141c52e2d433e9d1e0d06dc223475`
- Final status: `completed`
- Review UI rendered the staging trace card and clip summary on the booted simulator.

## Mixed live shadow batch

- Batch size: `8` jobs / `8` clips
- Candidate namespace: `runtimeFusionTemporalShadow`
- Flat label distribution:
  - `Highlight`: `7`
  - `Fast Break`: `1`
- Event family distribution:
  - `other`: `7`
  - `transition`: `1`
- Outcome distribution:
  - `missed`: `6`
  - `uncertain`: `2`
- Shot subtype distribution:
  - `layup`: `7`
  - `jumper`: `1`
- Uncertainty rate: `0.8750`
- Median clip duration: `4.0s`
- P90 clip duration: `4.5s`
- Highlight dominance rate: `87.5%`
- Miss-vs-made confusion:
  - `expectedMissPredictedMadeShot`: `0`

## Comparison vs phase3d1 baseline

- Baseline flat labels:
  - `Highlight`: `6`
  - `Fast Break`: `2`
- Current flat labels:
  - `Highlight`: `7`
  - `Fast Break`: `1`
- Spread score delta: `-0.1250`
- Highlight share delta: `+0.1250`
- Uncertainty delta: `-0.1250`

## Decision

This branch does not meet the acceptance bar.

Reasons:

- Mixed live batch still produced only `2` flat labels.
- `Highlight` still dominates the batch.
- Event family is still dominated by `other`.
- Outcome separation improved enough to avoid miss-to-made drift, but not enough to make the live labels useful.

Next branch:

- `codex/phase3e2-data-expansion-and-hard-negative-mining`

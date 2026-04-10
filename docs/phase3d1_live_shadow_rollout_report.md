# Phase 3d1 Live Shadow Rollout Report

Date: 2026-03-30
Branch: `codex/phase3d1-lora-encoder-adaptation`
Source commit for deploy candidate: `e9b0af0`

## Goal

Roll out the LoRA-adapted VideoMAE stack to a durable staging endpoint, keep the control-plane contract unchanged, and evaluate the adapted model in shadow mode before any further model work.

## Durable staging endpoint

- Inference service: [https://hoopsclips-inference-staging-568888872909.us-central1.run.app](https://hoopsclips-inference-staging-568888872909.us-central1.run.app)
- Cloud Run service: `hoopsclips-inference-staging`
- Region: `us-central1`
- Image: `us-central1-docker.pkg.dev/hoopsclips-9d38f/hoopsclips/hoopsclips-inference-staging:e9b0af0`
- Image digest: `sha256:e4f5c033af0dfb3d50813d43ccaa2540814f96ad7e1144a5a3cb33c2dde89dea`
- Worker URL: [https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev](https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev)
- Worker version: `107bd150-897b-49db-8866-a003c37aec72`

## Deployment notes

- The durable endpoint uses Cloud Run instead of the previous ephemeral quick tunnel.
- The control plane still dispatches with the existing push-queue flow and callback contract.
- Shadow-only runtime settings were used:
  - `HOOPS_INFERENCE_RUNTIME_MODEL_MODE=shadow`
  - `HOOPS_INFERENCE_VIDEOMAE_LORA_MODE=shadow`
- The inference service is operating without direct runtime R2 credentials in staging. It consumes the signed `sourceUrl` already provided by the control plane.
- The first Cloud Run revision failed on Secret Manager access. This was fixed by granting `roles/secretmanager.secretAccessor` on:
  - `HOOPS_INFERENCE_CALLBACK_SECRET`
  - `HOOPS_INFERENCE_INGRESS_SECRET`
  to service account `568888872909-compute@developer.gserviceaccount.com`

## Service verification

- `/version`: `200`
- `/readyz`: `200`
- `readyz` reported:
  - `ffmpeg=available`
  - `ffprobe=available`
  - `callback=configured`
  - `ingress=configured`
  - `r2=unconfigured`

## End-to-end smoke job

Sample file:

- `backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4`

Result:

- `jobId`: `8c17d233c0f94b7f9b3cf35d6a8ab71b`
- `uploadKey`: `uploads/8c17d233c0f94b7f9b3cf35d6a8ab71b/make_2_3.20s.mp4`
- `uploadTraceId`: `9f496305c1bd40318b3430e24cfea18e`
- `inferenceAttemptId`: `8ccbfd2cb1ea4acaa5cd9c7371ba9bf9`
- `presign requestId`: `5aaac68b-b5a5-4e9f-a00b-6b4c85e7b626`
- `finalize requestId`: `6ba6800a-5e53-4295-8c6b-052aea9147f6`
- `poll requestId`: `113cdc2c-f560-4d1b-8710-9f7c433b1591`
- final status: `completed`
- model version: `videomae:MCG-NJU/videomae-base-finetuned-kinetics`
- returned clips: `1`
- returned flat label: `Highlight`
- returned duration: `4.5s`

## Hands-on simulator staging flow

Build:

- Scheme: `HoopsClips`
- Configuration: `Staging`
- Simulator: `iPhone 17 Pro (iOS 26.0)`
- Staging URL injected at build time: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`

Automation launch:

- `HOOPS_AUTOMATION_ENABLED=1`
- `HOOPS_AUTOMATION_AUTH_MODE=guest`
- `HOOPS_AUTOMATION_SAMPLE_VIDEO_PATH=.../make_2_3.20s.mp4`
- `HOOPS_AUTOMATION_AUTO_ANALYZE=1`

Latest completed app-driven job:

- `jobId`: `fea8d63c2ace4c38abe58050bcedf584`
- `requestId`: `BA557344FFB341D4A59A5F96219D7977`
- `uploadTraceId`: `32facd2622f54789be27985244ad6948`
- `inferenceAttemptId`: `a7de861a2bd740cead6801df9210771c`
- model version: `videomae:MCG-NJU/videomae-base-finetuned-kinetics`
- status: `completed`

Simulator screenshots captured:

- Review trace view: `/tmp/phase3d1-sim-current.png`
- Review trace after confirmation: `/tmp/phase3d1-sim-review-dragged.png`

The Review tab rendered live staging trace metadata and kept-clip totals against the real Cloud Run-backed job path.

## Mixed live batch

Batch composition:

- `backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4`
- `backend/.external/HoopCut_FH/main/static/clips/miss_2_3.13s.mp4`
- `backend/.external/HoopCut_FH/main/static/clips/miss_1_0.00s.mp4`
- five local 4-second slices from `backend/.external/HoopCut_FH/provided_test/DEMO_VID.MOV`

Artifact paths:

- Batch job payloads: `/tmp/phase3d1-batch/results`
- Shadow report JSON: `/tmp/phase3d1-batch/shadow-report/shadow_eval_report.json`
- Shadow report Markdown: `/tmp/phase3d1-batch/shadow-report/shadow_eval_report.md`

Shadow summary:

- jobs: `8`
- clips: `8`
- flat label distribution: `{"Fast Break": 2, "Highlight": 6}`
- eventFamily distribution: `{"other": 6, "transition": 2}`
- outcome distribution: `{"uncertain": 8}`
- shotSubtype distribution: `{"jumper": 1, "layup": 3, "null": 2, "unknown": 2}`
- uncertainty rate: `1.0`
- median duration: `4.0s`
- p90 duration: `4.5s`
- miss-vs-made confusion:
  - `expectedMissPredictedMadeShot = 0`
  - `expectedMissPredictedHighlight = 0`
- Highlight dominance rate: `0.75`
- unique flat labels: `2`
- spread score: `0.25`

## Comparison vs phase3d shadow baseline

Phase 3d baseline from `docs/phase3d_runtime_model_improvement_report.md`:

- flat labels: `{"Highlight": 8}`
- eventFamily: `{"other": 8}`
- outcome: `{"missed": 5, "uncertain": 3}`
- uncertainty rate: `0.375`

Phase 3d1 live shadow result:

- flat labels: `{"Fast Break": 2, "Highlight": 6}`
- eventFamily: `{"other": 6, "transition": 2}`
- outcome: `{"uncertain": 8}`
- uncertainty rate: `1.0`

Interpretation:

- There is a small improvement in flat-label spread and event-family spread.
- `Made Shot` false positives stayed suppressed.
- The adapted stack still failed the rollout bar because:
  - flat labels remained limited to `2`
  - `Highlight` still dominated at `75%`
  - `eventFamily` was still mostly `other`
  - uncertainty regressed materially from `0.375` to `1.0`

## Decision

Do not promote the LoRA-adapted VideoMAE path out of shadow.

The branch should stop here and move to a stronger basketball-specific encoder/runtime path rather than continuing threshold or adapter-only tuning on the generic encoder stack.

Recommended next branch:

- `codex/phase3e-basketball-specific-runtime-encoder`

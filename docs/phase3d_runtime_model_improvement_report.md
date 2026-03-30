# Phase 3d Runtime Model Improvement Report

## Scope

This phase trained and integrated a lightweight late-fusion runtime basketball labeler over:

- structured basketball signals
- raw VideoMAE outputs
- raw X-CLIP outputs
- clip metadata

The live control-plane contract remained unchanged. Teacher outputs stayed offline and training-only.

## Runtime model integration

Runtime fusion shipped on branch `codex/phase3d-runtime-model-improvement` with:

- canonical dataset/schema cleanup and weighted runtime-training export
- held-out calibration for `eventFamily`, `outcome`, and `shotSubtype`
- runtime fusion bundle `services/inference/models/runtime_fusion_v1.json`
- inference-side rollout modes: `off`, `shadow`, `primary`

During live staging verification, one additional bug was fixed: `runtimeFusionShadow` metadata was being preserved inside `action_metadata` but dropped by the callback serializer. The serializer now lifts shadow/live runtime metadata from either the top-level clip metadata or nested `action_metadata`, and the shadow-eval script now prefers shadow payloads when present.

## Live staging rollout

Staging control plane:

- Worker URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Worker version during verification: `8771a457-0f01-41ed-9446-babef0c3fc02`

Staging inference target during verification:

- tunnel URL: `https://sequences-supply-stay-expense.trycloudflare.com`
- runtime mode: `shadow`
- runtime model version: `runtime-fusion-v1`

Smoke example:

- `jobId`: `1d15ab245bd74376a53eb15ea1727978`
- `requestIds`: presign `8154364c-d2b8-4ec3-ae05-212631865330`, finalize `07cc6e2d-494d-4301-82b5-1ab02f430493`, poll `61fa2711-83f4-4c0a-a1d6-e62a754b08f5`
- `uploadTraceId`: `e04dc5f3f3a443eda8b9c7d4ea9fc95e`
- `inferenceAttemptId`: `d9a8722e39d842d795e64b4c05cffe4e`

The smoke completed successfully and returned live `runtimeFusionShadow` metadata in the job payload.

## Mixed live shadow batch

Batch composition:

- `backend/.external/HoopCut_FH/main/static/clips/make_2_3.20s.mp4`
- `backend/.external/HoopCut_FH/main/static/clips/miss_2_3.13s.mp4`
- `backend/.external/HoopCut_FH/main/static/clips/miss_1_0.00s.mp4`
- five FFmpeg-sliced segments from `backend/.external/HoopCut_FH/provided_test/DEMO_VID.MOV`

Batch size:

- jobs: `8`
- clips: `8`

Shadow-eval summary:

- flat label distribution: `{"Highlight": 8}`
- eventFamily distribution: `{"other": 8}`
- shotSubtype distribution: `{"jumper": 5, "layup": 1, "unknown": 2}`
- outcome distribution: `{"missed": 5, "uncertain": 3}`
- uncertainty rate: `0.3750`
- median duration: `4.50s`
- p90 duration: `4.75s`
- miss-vs-made confusion: `expectedMissPredictedMadeShot = 0`
- miss-vs-highlight confusion: `expectedMissPredictedHighlight = 2`

## Interpretation

What improved:

- runtime shadow outputs no longer map miss clips to `Made Shot` by default
- outcome separation is partially visible in shadow (`missed` vs `uncertain`)
- live trace metadata remains intact end to end

What did not improve enough:

- mixed-batch flat label spread remained collapsed to `Highlight`
- `eventFamily` still collapsed to `other` on the live shadow batch
- the fusion head did not recover usable display-label diversity from the available runtime features alone

This means phase 3d improved safety and instrumentation, but it did not meet the acceptance bar for label spread or live runtime promotion.

## Acceptance outcome

Accepted:

- live staging shadow deploy worked
- control-plane contract stayed backward-compatible
- staging smoke flow remained healthy
- miss clips stopped mapping to `Made Shot` by default on the reviewed batch

Rejected:

- mixed live batch did not spread beyond two flat labels
- `Highlight` still dominated the batch completely
- `eventFamily` and subtype separation were not strong enough for promotion to `primary`

## Next branch

Follow-up branch opened due fusion-head plateau:

- `codex/phase3d1-lora-encoder-adaptation`

Recommended scope for that branch:

- parameter-efficient fine-tuning of the video encoder or relabel model
- keep the current runtime fusion head as the consumer of improved encoder features
- preserve the same control-plane contract and shadow-eval path for validation

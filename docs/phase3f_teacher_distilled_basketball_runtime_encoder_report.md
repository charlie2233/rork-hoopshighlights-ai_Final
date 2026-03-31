# Phase 3f: Teacher-Distilled Basketball Runtime Encoder

## Scope

Branch: `codex/phase3f-teacher-distilled-basketball-runtime-encoder`

Base state: `cc62f09`

This phase added the basketball-specific student-model training and rollout path while keeping the live control-plane contract unchanged. The branch compared a perception-first temporal student against a teacher-distilled clip student, deployed the temporal student to the durable staging Cloud Run service in shadow mode, and verified the staging Worker and iOS Review flow end to end.

## Repo Changes

Key commits on this branch:

- `5701774` Add external dataset bridge for basketball supervision
- `7c56933` Add perception supervision data builder
- `a703a52` Add perception-first temporal student runtime and trainer
- `968c473` Add teacher-distilled clip student runtime and trainer
- `bf32dd9` Add teacher supervision dataset builder
- `55b3ad5` Wire temporal student shadow rollout

Relevant files:

- `/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/datasets/dataset_bridge.py`
- `/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/perception_supervision.py`
- `/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/temporal_student.py`
- `/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/training/teacher_distilled_student.py`
- `/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/datasets/teacher_supervision.py`
- `/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/app/pipeline.py`
- `/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/cloudbuild.yaml`
- `/Users/hanfei/rork-hoopshighlights-ai_Final/services/inference/models/temporal_student_v1.json`

The control-plane and iOS contracts stayed additive. No public Worker route shape or Review trace field changed.

## Offline Candidate Comparison

Offline comparison artifact:

- `/tmp/phase3f-candidates/comparison_report.json`

Winner:

- `temporalStudent`

Offline summary:

- `phase3e2Baseline`
  - eventFamilyAccuracy: `1.0`
  - outcomeAccuracy: `1.0`
  - shotSubtypeAccuracy: `1.0`
  - flatLabelSpread: `6`
  - uncertaintyRate: `0.4286`
- `temporalStudent`
  - eventFamilyAccuracy: `1.0`
  - outcomeAccuracy: `0.6667`
  - shotSubtypeAccuracy: `1.0`
  - flatLabelSpread: `3`
  - highlightDominance: `0.0`
  - otherDominance: `0.0`
  - missVsMadeConfusion: `0`
  - uncertaintyRate: `0.0`
- `teacherDistilledStudent`
  - eventFamilyAccuracy: `0.7143`
  - outcomeAccuracy: `0.5714`
  - shotSubtypeAccuracy: `0.5714`
  - flatLabelSpread: `3`
  - uncertaintyRate: `0.7143`

Important caveat:

- the temporal-student anchor set was small, so live staging remained the real decision gate

## Durable Staging Rollout

Cloud Build:

- build id: `1f36fa92-e491-4e18-b391-32124f38d80e`
- status: `SUCCESS`

Cloud Run:

- latest ready revision: `hoopsclips-inference-staging-00009-cxd`
- durable service URL: `https://hoopsclips-inference-staging-568888872909.us-central1.run.app`
- Cloud Run service URL: `https://hoopsclips-inference-staging-npya43jiia-uc.a.run.app`

Health verification:

- `GET /readyz` returned ready with `ffmpeg`, `ffprobe`, `callback`, `ingress`, and `r2` configured
- `GET /version` returned `phase3f-teacher-distilled-basketball-runtime-encoder`

Shadow configuration deployed:

- `HOOPS_INFERENCE_RUNTIME_MODEL_MODE=off`
- `HOOPS_INFERENCE_TEMPORAL_ENCODER_MODE=shadow`
- `HOOPS_INFERENCE_TEMPORAL_ENCODER_BUNDLE_PATH=/app/services/inference/models/temporal_student_v1.json`
- `HOOPS_INFERENCE_DISTILLED_CLIP_ENCODER_MODE=off`

The staging Worker did not require a contract change or queue change. A real smoke run through the Worker proved it was dispatching to the new durable inference revision.

## Live Smoke Validation

Smoke artifact:

- `/tmp/phase3f-smoke.json`

Completed smoke job:

- jobId: `e770b99d60364e70aef131b65bc42b26`
- uploadTraceId: `84ab0c7e673d41f3af36602940a2c6e8`
- inferenceAttemptId: `af99677caed448e5abde1182e495982e`
- requestIds:
  - presign: `9f92b6ee-7a98-44fd-a2bf-3a7723286e7c`
  - finalize: `876636a6-e81f-40ad-a3c2-979b51972513`
  - poll: `5902fc3f-ad1e-497d-9c39-aaa8548bada9`
- finalStatus: `completed`
- modelVersion: `videomae:MCG-NJU/videomae-base-finetuned-kinetics`
- final label: `Highlight`
- clipDurationSeconds: `3.0`

The `3.0s` duration is not a regression against the hard minimum policy because the uploaded source video itself is `3.0s` long.

## Mixed Live Shadow Batch

Batch artifacts:

- `/tmp/hoopsclips-phase3f/live-batch`
- `/tmp/hoopsclips-phase3f/shadow-report/shadow_eval_report.json`
- `/tmp/hoopsclips-phase3f/shadow-report/shadow_eval_report.md`

Completed live batch size:

- `8`

Per-job summary:

| clip | jobId | requestId | uploadTraceId | inferenceAttemptId | flat label | duration |
| --- | --- | --- | --- | --- | --- | --- |
| hoopsclips-phase3e2-replay-demo_00_06 | `d5627db1202b48de84bfcfc1a39f3c97` | `6134294b-9d6d-4512-b7f3-60872ea3f0a0` | `090b1ca592144645acd79168a13a80eb` | `5635cfd8334a4c2c9f378dfedbf38605` | `Highlight` | `6.0` |
| hoopsclips-phase3e2-replay-demo_04_10 | `773f45e8ebdc4f01b6468c1f39cd5d57` | `503b7e4e-1dc1-46ef-a30d-69d92e8aa053` | `6d1f99e21cb347bbaffa6c0fda63765d` | `0ea1fd0933bd44c5a0ce2102e75e849a` | `Highlight` | `6.0` |
| hoopsclips-phase3e2-replay-demo_08_14 | `ce6d1d1c0581402cae6742fb2ad1bcda` | `a64e9ce2-0cbe-4e80-bc05-3caa10589693` | `7da8c1502f3e40d28d44185796aedf47` | `42bc73d4194846d08b5481da3e229d93` | `Highlight` | `5.75` |
| hoopsclips-phase3e2-replay-demo_12_18 | `3a525cba17e3405db52db90cf4e413d3` | `9f99c4e0-e0ea-4ec9-8401-f4314841e285` | `b09224903bb047b3b7160d4c6b279a5e` | `7e970253a24f43e6a6bc443e94116673` | `Highlight` | `6.0` |
| hoopsclips-phase3e2-replay-demo_15_20 | `738f307de87f4aa69c81133fd9e9c576` | `204cf98e-7bdb-4794-af48-f448ec2d1228` | `95d3a7aa77474376aff446ef5062044c` | `576a1a1f05424ffda297b5f366ecf701` | `Highlight` | `5.0` |
| hoopsclips-phase3e2-replay-make_2 | `f39e12179ee64390a92bdf7d7f13c436` | `a2004740-791f-4572-86ef-a4386d3c2856` | `ed41a458f0874450a3b80bad2dc69fe8` | `4229e5061afe421694e11c38d90ae6b7` | `Highlight` | `4.5` |
| hoopsclips-phase3e2-replay-miss_1 | `f23728a93767420da747f943c9521785` | `987f6d72-4f5f-4ef1-ad03-61ecddce9c84` | `12c6f58b811d4e6ea738a67776b581f2` | `95505a706d0e4f2b8b4941182ce50348` | `Fast Break` | `4.2` |
| hoopsclips-phase3e2-replay-miss_2 | `e96969b68946426db9a44684d24f4060` | `7a65d693-1c63-4318-a558-2a35589ca6a0` | `4a68b8367f314e228456f7ba56339c26` | `f1abda9910bd4c338ba2a3bdd1a5d9b6` | `Fast Break` | `5.25` |

Shadow-eval summary:

- candidate namespace: `runtimeFusionTemporalShadow`
- flatLabelDistribution:
  - Highlight: `6`
  - Fast Break: `2`
- eventFamilyDistribution:
  - other: `6`
  - transition: `2`
- outcomeDistribution:
  - uncertain: `8`
- shotSubtypeDistribution:
  - null: `8`
- uncertaintyRate: `0.75`
- Highlight dominance: `0.75`
- eventFamily other dominance: `0.75`
- duration median: `5.5`
- duration p90: `6.0`
- unique flat labels: `2`
- miss-vs-made confusion: `0`

Comparison against the verified phase3e2 baseline:

- flat label spread delta: `+0.0000`
- Highlight share delta: `+0.0000`
- eventFamily other share delta: `+0.0000`
- uncertainty delta: `-0.2500`

Net result:

- uncertainty improved relative to phase3e2
- live label spread did not improve
- `Highlight` and `eventFamily=other` still dominate the mixed batch

## Simulator Smoke

The Staging iOS app was rebuilt, installed on the booted simulator, launched with `SIMCTL_CHILD_HOOPS_AUTOMATION_*`, and allowed to auto-upload and analyze a live sample clip against the staging Worker.

Artifacts:

- build log: `/tmp/phase3f-xcodebuild.log`
- screenshot: `/tmp/phase3f-ios-smoke.png`

Observed on the Review screen:

- staging debug trace rendered
- requestId, uploadTraceId, inferenceAttemptId, and modelVersion were visible
- the Review screen showed a completed result with `1` kept clip and `0:04.5` total time

This confirmed the app-side staging flow still works end to end with the phase3f inference rollout.

![Phase 3f iOS staging smoke](/tmp/phase3f-ios-smoke.png)

## Acceptance Outcome

This phase did **not** meet the live acceptance bar.

Expected:

- mixed live batch shows meaningful spread beyond `2` flat labels
- `Highlight < 50%`
- `eventFamily other < 40%`
- miss clips do not drift into `Made Shot`
- outcome separation is visibly better even when subtype remains imperfect

Observed:

- unique flat labels: `2`
- Highlight share: `75%`
- eventFamily other share: `75%`
- uncertainty improved but remained high at `75%`
- miss-to-Made Shot drift stayed at `0`
- outcome separation did not become visible on the mixed live batch

Decision:

- Candidate A won offline but failed the live acceptance bar.
- Candidate B did not justify a live shadow rollout because it was already worse offline.
- The correct next step is `codex/phase3f2-domain-expansion-and-perception-retraining`.

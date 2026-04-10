# Phase 3f2: Domain Expansion and Perception Retraining

Date: 2026-03-31
Branch: `codex/phase3f2-domain-expansion-and-perception-retraining`
Verified commit: `ff67672`

## Rollout

- Inference service deployed to durable Cloud Run endpoint:
  - URL: `https://hoopsclips-inference-staging-568888872909.us-central1.run.app`
  - Revision: `hoopsclips-inference-staging-00010-st5`
  - Version: `phase3f2-domain-expansion-and-perception-retraining-ff67672`
- Control plane redeployed to staging Worker:
  - URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
  - Version ID: `1f51f057-ab2a-4160-8619-1085312f4e98`
- Control-plane contract unchanged.
- Shadow path remained enabled through `runtimeFusionTemporalShadow`.

## Validation

### Local

- Targeted inference suite passed:
  - `PYTHONPATH=/Users/hanfei/rork-hoopshighlights-ai_Final services/inference/.venv/bin/python -m unittest services.inference.tests.test_dataset_bridge services.inference.tests.test_hard_negative_mining services.inference.tests.test_perception_supervision services.inference.tests.test_teacher_supervision services.inference.tests.test_temporal_student`

### Live smoke

- Smoke job completed end to end:
  - `jobId`: `288dc6a88b3e45739eb2c2f61fd8ae15`
  - `uploadTraceId`: `d131e3113fb64a359c864c175d23fb9f`
  - `inferenceAttemptId`: `d052f66c47714563b2e9a28d8e21aae0`
  - `finalStatus`: `completed`
  - returned label: `Highlight`
  - returned duration: `4.5s`

### iOS staging flow

- Staging simulator build succeeded with explicit `HOOPS_CLOUD_ANALYSIS_BASE_URL` override.
- Automated upload flow reached Review and rendered live trace metadata.
- Screenshot: `/tmp/phase3f2-ios-smoke-late.png`

## Mixed live shadow batch

Batch artifacts:
- Results: `/tmp/phase3f2-batch/results`
- Shadow report: `/tmp/phase3f2-batch/shadow-report/shadow_eval_report.json`
- Human-readable report: `/tmp/phase3f2-batch/shadow-report/shadow_eval_report.md`

Per-clip IDs:

| file | jobId | uploadTraceId | inferenceAttemptId | finalLabel | duration |
| --- | --- | --- | --- | --- | --- |
| `demo_00_0.0.json` | `9271caad3639423d951232b53a0ad5cf` | `7035d09a46034f4fb3100af454b9176e` | `4d297630495042498e2d996dc2c2784e` | `Highlight` | `4.0s` |
| `demo_01_4.0.json` | `52384221ef65413086bbe9470b858b89` | `e6568917d2e34a67a5ff2ab3e48b81f7` | `c7cba23c53434429a048da7cab83b4d1` | `Highlight` | `4.0s` |
| `demo_02_8.0.json` | `39d4e4e146ee4acb91d04780d2bf0c75` | `490948fa6c3e4ca4ba2ddc2e164e536a` | `ec507ae17beb41b8ba80cc906d89111f` | `Highlight` | `4.0s` |
| `demo_03_12.0.json` | `f91fb7fca8214aa59e2df2e463527011` | `e87c6047318844d7a94e30001b780ffd` | `3640d5bdf7b04dd29b83b6f2335af3e4` | `Highlight` | `4.0s` |
| `demo_04_16.0.json` | `0521076e7b1741d38e9398b76ebf9937` | `ecf6db43d7d947a588e774364f87621e` | `7c133cf18592482e9d8f63b3d2955bfd` | `Highlight` | `4.0s` |
| `make_2_3.20s.json` | `d60722452ce54be995a461b193f320cb` | `6a9c5a90dd394f08b60cfd7d1b3889eb` | `fa44c267b41d4250b84235b008ee2d5d` | `Highlight` | `4.5s` |
| `miss_1_0.00s.json` | `510533e6e0d84e9e8ab5c04505b59f3f` | `bbe02f15b5104db799cfa7a86b559ef6` | `aef71a2086764abc9171ee6585c27b6a` | `Fast Break` | `4.2s` |
| `miss_2_3.13s.json` | `bb755c4084864c7ca2b5a3f10977624e` | `b39fe52cd3ec4088817d200b9875280b` | `b332c8c8e4ad4ae1ae5c5f9d500ac29a` | `Highlight` | `4.75s` |

Shadow summary:

- `flatLabelDistribution = {'Fast Break': 1, 'Highlight': 7}`
- `eventFamilyDistribution = {'other': 7, 'transition': 1}`
- `outcomeDistribution = {'uncertain': 8}`
- `shotSubtypeDistribution = {'null': 8}`
- `uncertaintyRate = 0.875`
- `missVsMadeConfusion = {'expectedMadePredictedHighlight': 0, 'expectedMadePredictedMiss': 0, 'expectedMissPredictedHighlight': 0, 'expectedMissPredictedMadeShot': 0}`
- `highlightDominance = 0.875`
- `eventFamilyOtherDominance = 0.875`
- `durationSummary = {'count': 8, 'medianSeconds': 4.0, 'p90Seconds': 4.5}`

## Acceptance result

Status: failed

Reasons:

- Flat-label spread still collapsed to 2 labels only.
- `Highlight` dominated `87.5%` of the mixed batch, missing the `< 50%` target.
- `eventFamily=other` dominated `87.5%` of the mixed batch, missing the `< 40%` target.
- Outcome separation did not improve materially: all 8 clips remained `uncertain`.
- Safety did hold on miss-vs-made: no miss clip drifted into `Made Shot`.
- Staging infrastructure and app flow remained healthy throughout the rollout.

## Conclusion

This branch succeeded operationally:

- durable staging endpoint is healthy
- control plane is still stable
- smoke job passed
- simulator upload passed
- mixed live shadow batch completed

This branch did not solve the model-quality problem. Domain expansion plus perception retraining improved neither label spread nor `eventFamily` dominance enough to justify promotion beyond shadow mode.

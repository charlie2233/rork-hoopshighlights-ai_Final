# Phase 3e2: Data Expansion and Hard-Negative Mining

## Scope

Branch: `codex/phase3e2-data-expansion-and-hard-negative-mining`

Base state: `432eab0`

This phase expanded human-verified and teacher-backed training data around live failure cases, added stronger hard-negative support to the runtime training pipeline, redeployed the updated runtime fusion bundle in staging shadow mode, and validated the result against live staging traffic without changing the public control-plane contract.

## Repo Changes

- Expanded the canonical annotation schema and dataset normalization for new hard-negative and source-domain coverage.
- Added stronger dataset bridging for SportsMOT and TrackID3x3 style sources.
- Updated the runtime training bundle and checked in `services/inference/models/runtime_fusion_v1.json`.
- Switched staging inference rollout to use the runtime fusion shadow path instead of the temporal encoder shadow path.
- Fixed a Python package import cycle that broke Cloud Run startup by converting eager package imports to lazy `__getattr__` imports.

Relevant commits:

- `4847e16` Add dominance metrics to eval reports
- `b481005` Expand hard-negative runtime training pipeline
- `c2e3a80` Switch staging shadow rollout to runtime fusion
- `1c4f48b` Fix inference package import cycles

## Offline Training and Eval

Runtime training data build:

- records: `24`
- active: `22`
- lora_records: `24`
- eligible: `17`

Offline probe:

- eventFamily: `0.89`
- outcome: `0.89`
- shotSubtype: `0.67`
- uncertainty: `0.45`
- highlightDominance: `0.4545`
- otherDominance: `0.3182`

Offline probe flat-label distribution:

- Highlight: `10`
- Fast Break: `3`
- Steal: `3`
- Dunk: `2`
- Made Shot: `2`
- Layup: `1`
- Block: `1`

Runtime model training output:

- feature count: `73`
- calibrated eventFamily threshold: `0.75`
- calibrated outcome threshold: `0.75`
- calibrated shotSubtype threshold: `0.6793`

## Staging Rollout

First Cloud Build attempt:

- build id: `9d8b00cc-1023-4537-b944-a1604703d5c2`
- status: `FAILURE`
- failure: Cloud Run revision `hoopsclips-inference-staging-00007-7vm` failed startup with an import cycle involving `services.inference.datasets.runtime_training`

Fix:

- lazy imports in `services/inference/datasets/__init__.py`
- lazy imports in `services/inference/training/__init__.py`

Second Cloud Build attempt:

- build id: `d924d336-3b2a-4b71-a44e-19b0169b2c0b`
- status: `SUCCESS`
- latest created revision: `hoopsclips-inference-staging-00008-4lv`
- latest ready revision: `hoopsclips-inference-staging-00008-4lv`

Durable staging inference endpoint:

- `https://hoopsclips-inference-staging-568888872909.us-central1.run.app`

Ready check:

- `GET /readyz` returned `{"status":"ready","service":"hoopsclips-inference-staging","ffmpeg":"available","ffprobe":"available","callback":"configured","ingress":"configured","r2":"configured"}`

## Live Smoke Validation

### API-path smoke

The first staging smoke after rollout used the updated runtime fusion shadow path. The original helper script timed out at a 30 second poll limit, but the job itself completed successfully a few seconds later and verified that the rollout was live.

- jobId: `5a76ed94317f42cd82d9d2bc93177d5b`
- requestId: `67877b98-bf4b-43ba-86cb-06975e9a5954`
- uploadTraceId: `f2a38b18e9ba4fb8b2cd3926252c8d85`
- inferenceAttemptId: `f1f48255f4364a98981e0c1bdbf156e9`
- final label: `Highlight`
- eventFamily: `shot_attempt`
- shotSubtype: `layup`
- outcome: `uncertain`
- duration: `4.5`
- runtimeModelMode: `shadow`
- runtimeModelVersion: `runtime-fusion-v1`
- temporalEncoderMode: `off`

### Simulator smoke

The first simulator launch stalled on the auth screen because `simctl launch` launch arguments were incorrectly used instead of `SIMCTL_CHILD_*` environment variables. Relaunching with `SIMCTL_CHILD_HOOPS_AUTOMATION_*` fixed the issue and completed the staging Review flow.

Simulator artifacts:

- screenshot: `/tmp/phase3e2-ios-smoke-automation.png`

Validated live simulator job:

- jobId: `26ce5ebd239c4b6781d47e76767eb38c`
- requestId: `B329D0ED8017455493D6C54B07FCB2D8`
- uploadTraceId: `93a90024970a40fc82c4574ff4fa5e41`
- inferenceAttemptId: `a07a314c91ae4adeadbd4c10913e2cc4`
- modelVersion: `videomae:MCG-NJU/videomae-base-finetuned-kinetics`
- final label: `Highlight`
- eventFamily: `shot_attempt`
- shotSubtype: `layup`
- outcome: `uncertain`
- duration: `4.5`
- runtime fusion shadow flat snapshot: `Fast Break`

The app Review screen rendered the staging debug trace and a completed cloud analysis result against the live Worker endpoint.

## Mixed Live Batch

Batch artifact directory:

- `/tmp/hoopsclips-phase3e2/live-batch`

Shadow report artifacts:

- `/tmp/hoopsclips-phase3e2/shadow-report/shadow_eval_report.md`
- `/tmp/hoopsclips-phase3e2/shadow-report/shadow_eval_report.json`

Completed live batch size: `8`

Per-job summary:

| clip | jobId | requestId | uploadTraceId | inferenceAttemptId | flat label | eventFamily | outcome | duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| demo_00_06 | `64657e960f0c45c7b1f5eda75c299066` | `82972379-4a1a-4e3e-b59f-4092c9cbad34` | `3776b229fd76462bbe29a1340fc4ff4e` | `440942b377ca4ff392c9521ef94a6e49` | Highlight | shot_attempt | uncertain | 6.0 |
| demo_04_10 | `7f8fd7a48f30494a8ce4bc34ce2f79ad` | `6ceb3151-dcbf-4466-bba2-9da10dc7dd7c` | `222f7b107fd34c3096011df5c8e61961` | `1fde1c0cefed4cb3b7b16b27eeea1332` | Highlight | shot_attempt | uncertain | 6.0 |
| demo_08_14 | `b1c4d933d44f4f4397007b716ef13bb5` | `b4583992-3fd2-45ff-82a5-8623ccc94fb3` | `a98159e2435c4afdb3a5b1c7059fd024` | `5d54b3e4798e448ea81c9c13ee8b9370` | Highlight | shot_attempt | uncertain | 5.75 |
| demo_12_18 | `07cb8870c895463b8830285979302740` | `d16a271d-9fe5-4ddd-8fbe-f51f1ed52792` | `bbf354f202fa4711aa73377225d02129` | `bba5289f474848f3971516b200810599` | Highlight | other | uncertain | 6.0 |
| demo_15_20 | `f087baa27b60438b9bc5ba786085e02a` | `e84ef668-f41d-4620-bc15-6e6140b98353` | `df0574d715cc437ea314d1e18a080d87` | `bd0547e06a3c4c86a514ad5e5220b6a3` | Highlight | other | uncertain | 5.0 |
| make_2 | `b2a78ad5b79c49f1bdebd3278fdb9f37` | `6a961f35-f346-4dd9-90fe-d8fbb55131f4` | `eb9da3c8097b494a9e68ebd235fdb342` | `38ff6b4cf17c4b418ed551f839c0c74c` | Highlight | shot_attempt | uncertain | 4.5 |
| miss_1 | `d24bf410738f4a6eae38571816b6226d` | `e7ae215b-67b0-4fa7-ab14-6b4198b77627` | `17d41c051719494bb6bc61d3cd30345e` | `8b1c1e9bb6084e41b0f16670747bf9ea` | Fast Break | transition | uncertain | 4.2 |
| miss_2 | `97583991762444528be9e2d11184fadf` | `97491aa8-9581-4f19-990e-99ba166d9be3` | `b003832792b0423c9cfd0d3319860cc4` | `9e008a17f2c048238aca240ee3570443` | Fast Break | transition | uncertain | 5.25 |

## Shadow Eval Summary

Candidate live shadow metrics:

- flatLabelDistribution:
  - Highlight: `6`
  - Fast Break: `2`
- eventFamilyDistribution:
  - other: `6`
  - transition: `2`
- outcomeDistribution:
  - uncertain: `8`
- shotSubtypeDistribution:
  - layup: `2`
  - jumper: `1`
  - null: `2`
  - unknown: `3`
- uncertaintyRate: `1.0`
- flatLabelDominanceRate: `0.75`
- eventFamilyOtherDominanceRate: `0.75`
- duration median: `5.5`
- duration p90: `6.0`
- unique flat labels: `2`
- dominant flat label: `Highlight`
- dominant flat-label share: `0.75`

Comparison against the phase 3d live shadow baseline:

- baseline flat labels: `Highlight=8`
- candidate flat labels: `Highlight=6`, `Fast Break=2`
- highlight share delta: `-0.25`
- eventFamily other share delta: `-0.25`
- uncertainty delta: `+0.625`
- unique flat label count delta: `+1`

Safety:

- miss-vs-made confusion remained `0`
- no miss clip drifted into `Made Shot`

## Acceptance Outcome

This phase did **not** meet the live acceptance bar.

Expected:

- mixed live batch shows meaningful spread beyond 2 flat labels
- Highlight `< 50%`
- eventFamily other `< 40%`
- uncertainty materially improves from phase 3e

Observed:

- flat labels: `2`
- Highlight share: `75%`
- eventFamily other share: `75%`
- uncertainty: `100%`

Net result:

- hard-negative mining and data expansion improved live spread slightly
- safety improved or held on miss-vs-made
- the runtime still collapses too heavily into `Highlight` / `other`
- the branch is useful as a data-quality foundation, but not sufficient as the runtime-quality fix

## Follow-up Recommendation

Do not continue threshold-only or prompt-only tuning from this state.

The next branch should use the expanded data assets from this phase to pursue a stronger runtime learner that materially reduces `Highlight` and `other` dominance while preserving the current control-plane contract and frozen clip windowing policy.

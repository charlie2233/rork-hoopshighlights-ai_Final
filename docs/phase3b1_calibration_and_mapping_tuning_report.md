# Phase 3b1 Calibration And Mapping Tuning Report

Date: 2026-03-28
Branch: `codex/phase3b1-calibration-and-mapping-tuning`
Base commit: `9e879ac`
Implementation commit: `401a641`

## Goal

Determine whether the current `VideoMAE + X-CLIP` stack contains enough latent basketball signal to recover useful labels through:

1. hierarchical calibration
2. basketball-specific X-CLIP prompt redesign
3. temporal aggregation across adjacent windows
4. margin-based abstain behavior

## Live staging deployment

- Control plane Worker: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Current staging Worker version: `8460a055-b7ce-4c51-b618-5889218e86e8`
- External inference service: `https://potato-rca-funk-complex.trycloudflare.com`
- Inference service version: `phase3b1-calibration-and-mapping-tuning`
- VideoMAE model: `MCG-NJU/videomae-base-finetuned-kinetics`
- X-CLIP model: `microsoft/xclip-base-patch32`
- X-CLIP prompt set version: `xclip-bball-v2`

## What changed in this branch

1. Fixed the real model path so VideoMAE and X-CLIP both execute instead of silently degrading around adapter bugs.
2. Added separate calibration logic for `eventFamily`, `shotSubtype`, and `outcome`.
3. Replaced generic X-CLIP prompts with contrastive basketball prompts plus confuser prompts.
4. Added temporal aggregation across adjacent windows before final hierarchical mapping.
5. Added abstain behavior so family-level predictions can stay confident while subtype and outcome remain uncertain.
6. Preserved the current app-facing flat display labels for backward compatibility.

## Staging simulator smoke

The Staging app was rebuilt and launched on the booted `iPhone 17 Pro` simulator with launch automation enabled against the live staging Worker URL.

Observed result:

- Review opened automatically after hydration
- the `Staging Debug Trace` card rendered
- the trace card showed `requestId`, `uploadTraceId`, `inferenceAttemptId`, and `modelVersion`
- one live clip rendered in Review
- the cloud path completed without falling back locally

This confirms the current branch still works end to end in the iOS staging app.

## Mixed live batch

Source mix:

- 3 windows from `DEMO_VID.MOV`
- 7 windows from `326_1770329282.mp4`
- 3 short tracked clips:
  - `make_2_3.20s.mp4`
  - `miss_1_0.00s.mp4`
  - `miss_2_3.13s.mp4`

### Summary

- clip count: `13`
- display-label distribution:
  - `Made Shot`: `6`
  - `Highlight`: `7`
- eventFamily distribution:
  - `shot`: `6`
  - `other`: `7`
- shotSubtype distribution:
  - `jumper`: `6`
  - `null`: `7`
- outcome distribution:
  - `made`: `6`
  - `uncertain`: `7`
- uncertainty rate: `53.8%`
- below-min clip rate (`< 3.5s`): `0.0`
- median duration: `4.75s`
- p90 duration: `4.75s`
- prompt set version observed: `xclip-bball-v2`

### Clip-level audit

| sample | jobId | requestId | uploadTraceId | inferenceAttemptId | raw VideoMAE top-k | raw X-CLIP top-k | eventFamily | shotSubtype | outcome | confidence before mapping | confidence after mapping | final display label | clip duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `demo_00_07` | `10024f5adc734e25875c3506e7238a72` | `ad073ddc-e7fb-4e1c-b2a4-7a3cd25d5588` | `e3b7facb7708412dab84a39cd4943b10` | `a576fc7269c64901a612a2e74c4e9316` | jumper (0.56); uncertain (0.11); uncertain (0.05) | steal (0.17); three (0.12); miss (0.10); jumper (0.08) | `shot` | `jumper` | `made` | `0.3006` | `0.7489` | `Made Shot` | `4.75s` |
| `demo_07_14` | `c3c9012a4f4b4c0da68e6ede595305a8` | `1ab0de73-9b96-4f34-b7ff-7298f8ca9f50` | `8d083ad3a8b341d5a22e47a86deb56af` | `50ea8cc7dd7d4d4ba3895ac7b1d98e24` | uncertain (0.46); jumper (0.11); uncertain (0.08) | miss (0.15); three (0.12); jumper (0.11); steal (0.09) | `shot` | `jumper` | `made` | `0.2516` | `0.4963` | `Made Shot` | `4.75s` |
| `demo_14_20` | `9bb0b84d45bd4647918c7f907e8b03a1` | `5dd53ac6-519d-4980-a6df-3c961a23daf8` | `ae918d5bb92d4b27ab8d2f09ab9b4417` | `91b68359769c43169b0ef0398ffbd3e9` | jumper (0.41); uncertain (0.09); uncertain (0.08) | miss (0.14); three (0.14); jumper (0.11); steal (0.09) | `shot` | `jumper` | `made` | `0.2486` | `0.7148` | `Made Shot` | `4.75s` |
| `game_00_15` | `52ef940f7ebb41749b652b57b8b8ba34` | `358766ed-73c1-47b6-85e2-d26c5daa6ec3` | `8e23819e788c4066bcae74d526bafaa1` | `fe5aa5d3da4d4e6296f4eadb2e65a3e4` | uncertain (0.21); uncertain (0.05); uncertain (0.03) | dunk (0.09); miss (0.08); miss (0.07); layup (0.06) | `other` | `None` | `uncertain` | `0.1865` | `0.4600` | `Highlight` | `4.75s` |
| `game_15_30` | `2bef09f6ec054d66ae5b1c8dce55ebad` | `e8633ea1-21bf-406a-bb6a-f06b8af8f63a` | `29f0f4b90d02472bbc9aac8dd1dce322` | `fc02be1519334c25b24164aec3c1d812` | uncertain (0.19); uncertain (0.09); uncertain (0.02) | uncertain (0.16); miss (0.08); dunk (0.08); uncertain (0.07) | `other` | `None` | `uncertain` | `0.2691` | `0.4600` | `Highlight` | `4.75s` |
| `game_30_45` | `6649f12e34d44204a5294e990455bc74` | `4a070e1c-1d07-4cfc-b254-d4d2f3e12eb8` | `a70ad6def6e24bdb8206099d7f6d184b` | `9ef1cc6b386f4b3f9d74091e8c530153` | uncertain (0.26); uncertain (0.20); dunk (0.06) | putback (0.06); steal (0.06); layup (0.06); layup (0.06) | `other` | `None` | `uncertain` | `0.2228` | `0.4600` | `Highlight` | `4.75s` |
| `game_45_60` | `64b68cdcc0db4c778f181f754ed679c5` | `fb91fc7c-712b-4c60-80fd-32e7075d1055` | `015314f532dc40ceb09ce56dfae0da5b` | `d98132edd2de4292a17e47c417c8698c` | uncertain (0.37); jumper (0.07); uncertain (0.06) | steal (0.09); fast break (0.07); uncertain (0.07); miss (0.06) | `other` | `None` | `uncertain` | `0.2453` | `0.4600` | `Highlight` | `4.75s` |
| `game_60_75` | `bc73b2317f564cfd80d244883cd79d09` | `d2cbe7fc-b7c2-42a9-8ff5-5ceb04fd39c7` | `28972901d6b34d85bec33998917f8ce9` | `4fc2c87de51e49dd896346de811c6cd3` | uncertain (0.38); uncertain (0.08); uncertain (0.06) | steal (0.09); three (0.07); miss (0.06); fast break (0.06) | `other` | `None` | `uncertain` | `0.2421` | `0.4600` | `Highlight` | `4.75s` |
| `game_75_90` | `8a1a94847c6a44ff9a81bc576d5013b2` | `f0a03185-1b71-4f84-8541-c98843056d22` | `79af08d0816d47a182cbf634d922958d` | `2376ce17bf08485a8923b6d5fe51f4a4` | uncertain (0.19); uncertain (0.14); uncertain (0.09) | miss (0.07); steal (0.07); dunk (0.06); fast break (0.06) | `other` | `None` | `uncertain` | `0.1913` | `0.4600` | `Highlight` | `4.75s` |
| `game_90_105` | `2c1bfce7094d4d6f941f10d4218385ac` | `d361a872-58cd-474d-9417-94566b30391c` | `d4f268f9d7734d1689540b144894a7ab` | `ee3db8d41a0d475993b3fdbce4cef754` | uncertain (0.43); uncertain (0.09); uncertain (0.05) | fast break (0.07); steal (0.07); dunk (0.06); steal (0.06) | `other` | `None` | `uncertain` | `0.2648` | `0.4600` | `Highlight` | `4.75s` |
| `make_2_3.20s` | `26329f6eb42e40678eee2e264518f733` | `f92d1aff-80e4-4dfc-bbe6-a0634629ce53` | `751f9c9648954f5a867b978868abfe6b` | `23c99465580645f2835b4cb0055f91ea` | jumper (0.27); uncertain (0.18); uncertain (0.12) | steal (0.13); miss (0.12); jumper (0.10); three (0.06) | `shot` | `jumper` | `made` | `0.1785` | `0.6158` | `Made Shot` | `4.75s` |
| `miss_1_0.00s` | `66e3ccdabaf24289a5d442e3c6782b65` | `c6c24240-2f02-4c44-8e5a-9091c8de744c` | `b12d444001fd4ca3996823b1e9f2a56b` | `1c780f813b6e4476a91bd82e02d2a712` | jumper (0.46); uncertain (0.27); uncertain (0.01) | miss (0.14); jumper (0.10); three (0.08); steal (0.08) | `shot` | `jumper` | `made` | `0.2652` | `0.6763` | `Made Shot` | `4.20s` |
| `miss_2_3.13s` | `215930aaacde405aa45ea2c88ec04a65` | `ad95f259-4f9a-4eaa-9ae4-d5f45a51af5c` | `c66fe722138b40839b8cc946606e87eb` | `0edb4a35085b4d418438a1322152fd49` | jumper (0.27); uncertain (0.21); uncertain (0.14) | steal (0.14); miss (0.12); jumper (0.08); three (0.07) | `shot` | `jumper` | `made` | `0.1977` | `0.5808` | `Made Shot` | `4.75s` |

## Where the stack still fails

### Raw outputs were diverse, but hierarchical mapping still suppressed them

Examples where the raw X-CLIP suggestions contained basketball-specific alternatives but the final output stayed generic `Highlight`:

1. `game_30_45`
   - X-CLIP raw: `putback`, `steal`, `layup`, `three`
   - final: `Highlight`
2. `game_45_60`
   - X-CLIP raw: `steal`, `fast break`, `miss`, `three`
   - final: `Highlight`
3. `game_90_105`
   - X-CLIP raw: `fast break`, `steal`, `dunk`
   - final: `Highlight`

### Raw outputs were already generic and largely unrecoverable

Examples where VideoMAE remained mostly generic and left the branch without enough evidence to recover subtype or outcome:

1. `game_00_15`
   - VideoMAE raw: `uncertain`, `uncertain`, `uncertain`
2. `game_15_30`
   - VideoMAE raw: `uncertain`, `uncertain`, `uncertain`
3. `game_60_75`
   - VideoMAE raw: `uncertain`, `uncertain`, `uncertain`

### Concrete remaining failure modes

1. The tracked miss clips still map to `Made Shot`.
2. The batch produces only `Made Shot` or `Highlight` at the app-facing layer.
3. Subtype separation remains effectively `jumper` vs `null`.
4. Outcome separation remains `made` vs `uncertain`, with no real `missed` recovery.
5. Family separation is still mostly `shot` vs `other`.

## Stop-condition check

Configured stop conditions for this phase:

1. fewer than `4` display labels on a mixed live batch
2. uncertainty above about `50%`
3. weak subtype separation after calibration and prompt redesign

Observed result:

1. fewer than `4` display labels: `true` (`2` labels total)
2. uncertainty above `50%`: `true` (`53.8%`)
3. subtype separation still weak: `true`

All stop conditions were hit.

## Decision

Calibration, prompt redesign, and temporal aggregation improved the live path in two useful ways:

1. the staging stack is definitely running the real VideoMAE + X-CLIP models
2. the system no longer collapses the entire mixed batch into one flat label

That is still not enough. The current stack does not contain enough recoverable basketball structure to deliver useful live labels through calibration and mapping alone.

Next branch:

- `codex/phase3c-structured-basketball-signals`

That follow-up should move beyond calibration-only recovery and add basketball-specific structured signals before the mapping layer.

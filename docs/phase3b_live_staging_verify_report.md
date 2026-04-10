# Phase 3b Live Staging Verify Report

Date: 2026-03-28
Branch: `codex/phase3b-live-staging-verify`
Base commit: `43d954d`

## Staging endpoints

- Control plane Worker: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Control plane Worker version: `41332f14-1a3c-43dc-a5ec-a169f8c3aeb3`
- External inference service: `https://fundamentals-mod-bosnia-tribe.trycloudflare.com`
- Inference service version: `phase3b-live-staging-verify`

## Live redeploy result

This branch was redeployed to live staging without changing the public control-plane contract:

1. Updated staging `INFERENCE_SHARED_SECRET`
2. Updated staging `INFERENCE_BASE_URL`
3. Redeployed the Cloudflare Worker from this branch
4. Confirmed the inference service `/readyz` and `/version` endpoints on the new tunnel URL
5. Ran a real staging smoke and a 13-run live batch against the Worker URL above

The staging Worker continued to use the same authoritative Durable Object, Queue, R2, and D1 bindings.

## Single live smoke

Smoke trace: `phase3b-live-smoke-001`

- jobId: `62d86ce93ea14435aace0f6dceb754e1`
- presign requestId: `4072cf4c-96f1-45c0-a592-37aa19049404`
- finalize requestId: `e23eb190-1878-4277-930b-f669b92f0985`
- callback requestId: `b313ede0-ae3d-4794-9650-e21e4310614b`
- final poll requestId: `1b5f20ec-8aa2-42b4-b4ac-407055dd6e67`
- uploadTraceId: `220778c4f90a42e881a9d3eb8def78eb`
- inferenceAttemptId: `bceb52ea524f4bac8851b0eced7de049`
- modelVersion: `videomae:MCG-NJU/videomae-base-finetuned-kinetics`
- final display label: `Fast Break`
- eventFamily: `transition`
- outcome: `uncertain`
- clip duration: `5.25s`

This verifies the current branch is live in staging and the external inference path is active.

## iOS staging smoke

The Staging simulator build was rebuilt with:

- `HOOPSAppEnvironment = staging`
- `HOOPSCloudAnalysisBaseURL = https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`

Validation:

- The app launched with `HOOPS_AUTOMATION_*` enabled
- The Review tab auto-opened after clip hydration
- The `Staging Debug Trace` card rendered with `requestId`, `uploadTraceId`, `inferenceAttemptId`, and `modelVersion`
- The Review stats showed live hydrated clips on the same run path

This confirms the app still points at the live staging endpoint and the trace/debug surface remains intact.

## 13-run live batch

Source mix used in this verification:

- 3 windows from `DEMO_VID.MOV`
- 7 windows from `326_1770329282.mp4`
- 3 short tracked clips:
  - `make_2_3.20s.mp4`
  - `miss_1_0.00s.mp4`
  - `miss_2_3.13s.mp4`

### Clip-level audit

| sample | jobId | requestId | uploadTraceId | inferenceAttemptId | raw VideoMAE top-k | raw X-CLIP suggestions | eventFamily | shotSubtype | outcome | confidence before mapping | confidence after mapping | final display label | clip duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `demo_00_07` | `177adc3432aa44b5992575d46dc51d18` | `ab0ea0fd-9d53-43d1-878c-26b8a1d3f0e1` | `2f669485deb54ac89d7324efdd11d98d` | `5b5a88949e4c4c8089e07857582cbfc6` | `fast break (0.39)` | `fast break (0.33)` | `transition` | `null` | `uncertain` | `0.39` | `0.39` | `Fast Break` | `5.25s` |
| `demo_07_14` | `133f81b8e7f8460a9d90c9de7aba386c` | `7874e9f1-e535-45c4-b753-d670b751baa6` | `793cba630c5b4c708aa2cfb3c8d15655` | `682a745e677e4ae18abdbcd8d5754ac4` | `fast break (0.39)` | `fast break (0.33)` | `transition` | `null` | `uncertain` | `0.39` | `0.39` | `Fast Break` | `5.25s` |
| `demo_14_20` | `825320f536914fee92f27a5802090708` | `829b2bb0-0c91-4f4f-8827-352a4ee4972e` | `96389d2fc155493cb775a9edfda380e4` | `7b7383bf3a6a4bafbf5be26bdc3f1ef7` | `fast break (0.39)` | `fast break (0.33)` | `transition` | `null` | `uncertain` | `0.39` | `0.39` | `Fast Break` | `5.25s` |
| `game_00_15` | `2ddc92d17f2444918ba0204e2888c4c7` | `278448b1-d29a-4847-9f28-a9529651fc2e` | `1330bece4e764f1f903c11a7856b0583` | `e8b958edbb7543a1aabc0222f14988bd` | `uncertain (0.24)` | `uncertain (0.22)` | `other` | `null` | `uncertain` | `0.24` | `0.24` | `Highlight` | `4.75s` |
| `game_15_30` | `faa670124d4945669322ea1b79b83c52` | `665ba761-8b78-4cf5-8c0d-7dd795d72fce` | `c63185c574e8450588bd14c674459e7e` | `0b14b39c0ac54e9c8864c699bb1b1db2` | `uncertain (0.24)` | `uncertain (0.22)` | `other` | `null` | `uncertain` | `0.24` | `0.24` | `Highlight` | `4.75s` |
| `game_30_45` | `e72548056108423b8baaab359a98b918` | `55157a23-1b46-4c28-800d-d39a63138524` | `19798692846046d7a70479f22a082607` | `199a93be4c1040e8b6b0302dba017273` | `uncertain (0.24)` | `uncertain (0.22)` | `other` | `null` | `uncertain` | `0.24` | `0.24` | `Highlight` | `4.75s` |
| `game_45_60` | `3eb201fbf89844df9e17bbfa3e1502ce` | `400d3df5-f38f-44e4-80b6-f59a450e9c28` | `6b21d86e879142509f4ae75321cfa245` | `2b3ff996035f49299eccededb62ad803` | `uncertain (0.24)` | `uncertain (0.22)` | `other` | `null` | `uncertain` | `0.24` | `0.24` | `Highlight` | `4.75s` |
| `game_60_75` | `910b6a2869b94737866ed1827e0bec62` | `e4ad3143-3ccd-4ff8-bda6-7a7c26b7f620` | `7017300e637e4796854efccdb630c896` | `16bc2d0c93974d51bdb337806cca1482` | `uncertain (0.24)` | `uncertain (0.22)` | `other` | `null` | `uncertain` | `0.24` | `0.24` | `Highlight` | `4.75s` |
| `game_75_90` | `ad87b6825fae47e19a35487e49228ce8` | `650b7f45-8dd2-48e0-a48d-1b70f47c6953` | `25b780a4cc714846bdcfbb59dceaae95` | `0cbf0d52a7ce4d089d6c6ca4a693c1a6` | `uncertain (0.24)` | `uncertain (0.22)` | `other` | `null` | `uncertain` | `0.24` | `0.24` | `Highlight` | `4.75s` |
| `game_90_105` | `9cac59115d2e4c9093d7e9c955c434ce` | `7ece6265-b52c-4518-a0ae-388b8f2af0a4` | `71d793eff0794487baeb575547f9cc45` | `198734360f7b4b1787aad62015a921ad` | `uncertain (0.24)` | `uncertain (0.22)` | `other` | `null` | `uncertain` | `0.24` | `0.24` | `Highlight` | `4.75s` |
| `make_2_3.20s` | `3f00171d481b4a43a7f287c0bba2203c` | `3a861d66-309c-4610-86c8-c1b54ff300e4` | `dde65c92b0ad4f8f955c2ea4b38d80b7` | `d19ef6a5323149c4b548c6e51f2ccfae` | `fast break (0.39)` | `fast break (0.33)` | `transition` | `null` | `uncertain` | `0.39` | `0.39` | `Fast Break` | `5.25s` |
| `miss_1_0.00s` | `2a7e34ce23ab4d548e70df3e3ac72da0` | `08a7ed2d-3562-4adc-9f93-8cf6745e738c` | `18115c26d5f740578f7d259568e30c48` | `2f45b730027a4deabd7a7e9d8bde30da` | `fast break (0.39)` | `fast break (0.33)` | `transition` | `null` | `uncertain` | `0.39` | `0.39` | `Fast Break` | `4.20s` |
| `miss_2_3.13s` | `7c86aa4a3f0541b7bb076d68dc9e210c` | `ec809964-3108-42d0-aeb7-dd862b3deb6c` | `83a80cb0dd36496c81e1e98816a34db3` | `3742d932fcfe467c81956cc6f30df33d` | `fast break (0.39)` | `fast break (0.33)` | `transition` | `null` | `uncertain` | `0.39` | `0.39` | `Fast Break` | `5.25s` |

## Live audit summary

### Display-label distribution

- `Fast Break`: `6`
- `Highlight`: `7`

### Event-family distribution

- `transition`: `6`
- `other`: `7`

### Shot-subtype distribution

- `null`: `13`

### Outcome distribution

- `uncertain`: `13`

### Duration summary

- clip count: `13`
- below-min clip rate (`< 3.5s`): `0.0`
- median duration: `4.75s`
- p90 duration: `5.25s`
- merged clip count: `0`

### Uncertainty summary

- uncertainty rate: `1.0`
- every live clip returned `outcome = uncertain`
- no live clip emitted a concrete shot subtype

## Where the current collapse happens

This branch removed the previous blind collapse to `Made Shot`, but live collapse still remains on the real service path.

Observed collapse point by stage:

1. Proposal stage
   - Not the primary problem in this batch.
   - The service still returned one clip per sample with watchable durations.
2. Base classifier
   - Main collapse point.
   - Raw VideoMAE top-1 produced only two states across the 13-run batch:
     - `fast break` with confidence `0.39`
     - `uncertain` with confidence `0.24`
3. Relabel layer
   - Did not add diversity.
   - Raw X-CLIP suggestions mirrored the same two states:
     - `fast break` with confidence `0.33`
     - `uncertain` with confidence `0.22`
4. Final mapping layer
   - No longer maps everything to `Made Shot`.
   - It preserves `fast break -> Fast Break`.
   - It still compresses `uncertain -> Highlight`, which keeps the app-facing contract stable but also hides the absence of basketball-specific structure.

## Confusion notes and obvious failure modes

- The tracked make/miss clips did not separate into `made` vs `missed`.
- The full-court windows did not surface `layup`, `jumper`, `three`, `steal`, `block`, or `miss`.
- The batch is no longer a single generic class, but it is still not basketball-specific enough for the intended taxonomy.
- No examples were found where raw outputs were richly diverse and the final mapping collapsed them later. In this live batch, the collapse is already present in the raw model outputs.

## Acceptance checks

- No blind collapse to a single display label on a mixed batch: `pass`
  - The batch split across `Fast Break` and `Highlight`.
- At least 4 display labels appear on a mixed batch unless data disproves it: `fail`
  - Only `2` display labels appeared in the 13-run live batch.
- Uncertainty is used on ambiguous clips: `pass`
  - Uncertainty was applied on all `13` clips.
- App Review UI still renders clips and trace metadata: `pass`
  - The Review screen rendered the staging trace card and live clip counts on the Staging build.
- No regressions in staging smoke flow: `pass`
  - Presign, direct upload, queue dispatch, external inference, callback, and poll completion all succeeded.

## Decision

Live label spread improved relative to phase 2b because the service no longer collapses a mixed batch to `Made Shot`, but the result is still not acceptable for basketball taxonomy quality.

Recommended follow-up branch:

- `codex/phase3b1-calibration-and-mapping-tuning`

This follow-up should target:

1. Basketball-specific calibration thresholds
2. Stronger mapping of `uncertain` vs `other`
3. Better separation between transition, shot, and defensive-event families
4. Preserving uncertainty internally without overusing generic `Highlight` externally

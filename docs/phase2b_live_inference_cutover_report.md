# Phase 2b Live Inference Cutover Report

Date: 2026-03-28
Branch: `codex/phase2b-live-inference-cutover`

## Staging endpoints

- Control plane Worker: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- External inference service: `https://practitioner-gradually-introduced-ist.trycloudflare.com`
- Worker version validated in staging: `8e3dac01-9dc2-4b3f-9e66-1cc29f7797de`

## Live cutover result

The Cloudflare staging control plane was cut over from stub inference to the external Python inference service without changing the public job contract. Live staging uploads now complete through:

1. `POST /uploads/presign`
2. direct R2 upload
3. `POST /jobs`
4. Cloudflare Queue dispatch
5. external `POST /v1/analyze`
6. `POST /internal/inference/callback`
7. `GET /jobs/:id` terminal completion

## Verified clean runs

### Clean live run 2

- Job ID: `337bbefd15714884bb4662232b346e3b`
- Trace ID: `phase2b-live-cutover-clean-2`
- Upload trace ID: `ec44d2be89294d019f9a6a24a923236c`
- Inference attempt ID: `af210bb29f4b4357a0a7aa8c9ef65c6e`
- Presign request ID: `195191d5-655b-49de-b8a7-8a792fd5b1c3`
- Queue/finalize request ID: `5d3b95c8-86e8-4942-ac26-b423bb2e6a1f`
- Callback request ID: `c4095682-80b3-457f-a41f-4441cee8bdc2`
- Poll request ID: `fdff28cd-0f0d-4f27-9982-d6988a5f31b9`
- Final status: `completed`

### Clean live run 3

- Job ID: `1c40f33e36924ee09e774c7a1a9674dd`
- Trace ID: `phase2b-live-cutover-clean-3`
- Upload trace ID: `362f5fce96c24d18adce4915bacccdae`
- Inference attempt ID: `e7622182b32541d8b5fd07939036fa8d`
- Presign request ID: `0356953f-d626-48b0-9474-fd5bf51ba66e`
- Queue/finalize request ID: `f8e734ac-6e75-4cc9-83b4-41ba302c339f`
- Callback request ID: `f071d9b2-6fbe-41c2-bd91-7b78831b17a9`
- Poll request ID: `e26383fe-3f68-4f3f-bd9f-53788a081765`
- Final status: `completed`
- Returned clips:
  - `Made Shot`, `4.75s`
  - `Made Shot`, `4.50s`

## iOS staging smoke

The staging simulator build was launched with `HOOPS_AUTOMATION_*` enabled against the live staging Worker URL. The Review tab rendered:

- the staging debug trace card with `requestId`, `uploadTraceId`, `inferenceAttemptId`, and `modelVersion`
- two returned clip cards in Review

Observed app automation job:

- Job ID: `bfd4f36084f84f66b70edf129a644f01`
- Request ID: `524B43FAA3D54DB281C7920FDA2D973A`
- Upload trace ID: `ffaaceb8f40347e4827497fdaee9c473`
- Inference attempt ID: `d30e9670175c47979069441ff20ebfc0`

## 15-run staging batch

Source set:

- 5 clipped windows from `DEMO_VID.MOV`
- 3 clipped windows from `lebron_shoots.mp4`
- 3 clipped windows from `make_2_3.20s.mp4`
- 3 clipped windows from `miss_2_3.13s.mp4`
- 1 full clip from `miss_1_0.00s.mp4`

Observed metrics from live staging results:

- Run count: `15`
- Returned clip count: `15`
- Below-min clip rate (`< 3.5s`): `0.0`
- Median returned clip duration: `4.75s`
- p90 returned clip duration: `4.75s`
- Merged clip count: `0`
- Timeout retry count: `0`
- Failed timeout count: `0`
- Per-label duration distribution:
  - `Made Shot`: `count=15`, `median=4.75s`, `min=4.2s`, `max=4.75s`

### Watchability spot-check

Spot-checked live outputs in the simulator Review UI and via returned clip windows:

| Clip set | Contains setup | Contains finish/outcome | Feels complete | Would keep/export |
| --- | --- | --- | --- | --- |
| `phase2b-live-cutover-clean-2` clip 1 | yes | yes | yes | yes |
| `phase2b-live-cutover-clean-2` clip 2 | yes | yes | yes | yes |
| `phase2b-live-cutover-clean-3` clip 1 | yes | yes | yes | yes |
| `phase2b-live-cutover-clean-3` clip 2 | yes | yes | yes | yes |

## Follow-up risks

1. The external inference service is currently exposed through a Cloudflare quick tunnel. It is good enough for staging validation, but it is not a durable deploy target.
2. The current baseline model path is live, but label diversity is still poor. All 15 batch clips were classified as `Made Shot`, including source clips intended to exercise miss/make variety.
3. App-facing result hydration now preserves clip duration and merge metadata, but the Review UI is still optimized for stable legacy fields; richer clip metadata is currently better surfaced through staging debug traces and batch JSON.
4. The first staging simulator build still emits existing Swift 6/main-actor warnings unrelated to this cutover.

# Phase Launch: Live Backend Status Snapshot

Date: 2026-06-03
Branch: `codex/phase-launch-proof-next`
Head at check time: `2615f143c4f471e7cdcff2183b8ba4c2e5ab6f3c`
Worker base URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`

## Secret-free live check

Command shape used:

```bash
/usr/bin/curl \
  -sS \
  -A 'HoopClipsLaunchPreflight/1.0' \
  -H 'Accept: application/json' \
  https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version
```

No auth headers, tokens, cookies, upload URLs, signed URLs, or object keys were sent or recorded.

## Result

`/v1/editing/version` returned HTTP `200` on 2026-06-03 at approximately 12:27 UTC.

Non-secret response evidence:

- `service`: `hoopclips-editing`
- `backendModelVersion`: `editing-cloud-v1`
- `gitSha`: `3eeb6f16d5f33ca2b9902169dfcc13e2cdc0ada7`
- `renderer`: `cloud_ffmpeg`
- `rendererVersion`: `ffmpeg-renderer-v1`
- `ffmpegAvailable`: `true`
- `ffprobeAvailable`: `true`
- `drawtextAvailable`: `true`
- `aiEditEnabled`: `true`
- `aiEditLiveRenderEnabled`: `true`
- `aiEditRevisionEnabled`: `true`
- `aiEditTemplatePackEnabled`: `true`
- `aiEditFreeWatermarkRequired`: `true`
- `aiEditProExportsEnabled`: `false`
- `aiClipGptEditorEnabled`: `true`
- `aiClipGptPlanEditEnabled`: `true`
- `aiClipGptRevisionEnabled`: `true`
- `gptHighlightRerankerEnabled`: `true`
- `gptHighlightReranker.enabled`: `true`
- `gptHighlightReranker.configured`: `true`
- `gptHighlightReranker.model`: `gpt-4.1`

Request ID from the Worker response:

```text
d7aa7c87-407e-49a6-bad6-0a75e0c81213
```

## Non-app-path route checks

The generic `/health` and `/v1/health` routes returned HTTP `404` with `Route not found.`. The iOS app and CI smoke path use `/v1/editing/version` for this backend status proof, so this snapshot treats those generic routes as unsupported routes rather than as the launch-path status endpoint.

## Remaining blockers

This confirms the internal staging Worker reports live editing/GPT/render capability, but it does not close:

- GitHub `production` environment variables missing `HOOPS_CLOUD_ANALYSIS_BASE_URL` and `HOOPS_CLOUD_EDIT_BASE_URL`.
- Apple signing/TestFlight archive upload readiness.
- Installed TestFlight smoke on a trusted physical iPhone.
- Human-reviewed 54-clip launch accuracy labels and rebuilt accuracy report.

Do not treat this snapshot as public cloud cutover approval. It is internal TestFlight backend status evidence only.

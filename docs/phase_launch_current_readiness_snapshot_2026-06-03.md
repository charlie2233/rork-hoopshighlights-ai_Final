# Phase Launch Current Readiness Snapshot - 2026-06-03

This snapshot records the current internal TestFlight readiness evidence for
`codex/phase-launch-proof-next` without treating unresolved launch gates as
complete.

## Branch state

- Branch: `codex/phase-launch-proof-next`
- HEAD: `1ea244c chore: clarify cloud render required copy`
- Upstream: `origin/codex/phase-launch-proof-next`
- Divergence after sync: `0 ahead / 0 behind`
- Tracked working tree: clean
- Preserved unrelated untracked root folders:
  - `HoopsClips.xcodeproj/`
  - `HoopsHighlightsAI.xcodeproj/`

## Current safe CI evidence

- `Cloud Edit Deploy Preflight` run `26888070725`: `success` on `1ea244c`
- `iOS Internal TestFlight Upload` codecheck run `26888073178`: `success` on `1ea244c`

The signed archive/upload path was not retried in this snapshot because Apple
signing remains externally blocked.

## Live backend evidence

The staging Worker version endpoint returned HTTP 200 from:

`https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev/v1/editing/version`

Non-secret response fields confirmed:

- Service: `hoopclips-editing`
- Backend model version: `editing-cloud-v1`
- Backend git SHA: `3eeb6f16d5f33ca2b9902169dfcc13e2cdc0ada7`
- Renderer: `cloud_ffmpeg`
- Renderer version: `ffmpeg-renderer-v1`
- `ffmpegAvailable`: `true`
- `ffprobeAvailable`: `true`
- `drawtextAvailable`: `true`
- `aiEditEnabled`: `true`
- `aiEditLiveRenderEnabled`: `true`
- `aiEditRevisionEnabled`: `true`
- `aiEditTemplatePackEnabled`: `true`
- `aiClipGptEditorEnabled`: `true`
- `aiClipGptPlanEditEnabled`: `true`
- `aiClipGptRevisionEnabled`: `true`
- `gptHighlightRerankerEnabled`: `true`
- GPT highlight reranker configured: `true`
- GPT highlight reranker model: `gpt-4.1`

This proves the internal staging backend endpoint is currently reachable and
advertises the expected cloud editing and GPT reranker capabilities. It does
not prove production cutover.

## Production environment variable evidence

Visible non-secret GitHub `production` environment variables currently include:

- `HOOPS_PRIVACY_POLICY_URL=https://rork.com/privacy`
- `HOOPS_TERMS_OF_SERVICE_URL=https://rork.com/terms`

The following required production cloud URL variables are still not visible:

- `HOOPS_CLOUD_ANALYSIS_BASE_URL`
- `HOOPS_CLOUD_EDIT_BASE_URL`

Latest `Release Secrets Preflight` evidence:

- Run `26884199422`: `failure` on `86fdc33`

Do not rerun or claim this gate green until the production cloud URL values are
provided or confirmed by the release owner.

## Human-reviewed accuracy evidence

Current label bundle status:

- Schema: `team-highlight-label-status-v1`
- Overall status: `incomplete`
- Cases: `2`
- Clips: `54`
- Complete clips: `0`
- Incomplete clips: `54`

Current missing launch fields across all 54 clips:

- `needsLabel=false`
- `reviewedByHuman=true`
- `expected.teamId`
- `expected.isHighlight`
- `expected.eventType`
- `expected.outcome`

This means the GPT/team-highlight accuracy gate is still unproven. The label
bundle must be human-reviewed before the launch readiness report can claim real
clip-selection quality.

## Remaining launch blockers

- Human-reviewed label coverage is still `0/54`.
- Production cloud URL variables are still missing from visible GitHub
  `production` environment variables.
- Release Secrets Preflight remains failed at run `26884199422`.
- Apple signing and current signed archive/TestFlight upload remain externally
  blocked.
- Installed TestFlight smoke on a trusted device remains unproven.

## Current conclusion

HoopClips has current safe CI proof and a reachable internal staging backend
with cloud edit/GPT capabilities enabled. Internal TestFlight readiness is still
not complete because the production environment, human-reviewed accuracy
evidence, Apple signing, and installed-device smoke gates remain unresolved.

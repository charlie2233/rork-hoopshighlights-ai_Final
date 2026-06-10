# HoopClips current-tip launch evidence - 2026-06-10

This document captures the launch evidence for the current `main` tip after the
navigation title cleanup, TestFlight signing fix, and staging cloud redeploy.

## Current checkout

- Branch: `main`
- Commit: `06a7775c0b46505c1eec453ceab0f7602532cd7d`
- Short commit: `06a7775c Archive TestFlight build without development signing`
- Repo hygiene before this evidence pass:
  - `git status --short --branch`: `## main...origin/main`
  - `git diff --stat`: no output
  - `git diff --check`: no output

## iOS unit tests

- Lane: XcodeBuildMCP `test_sim`
- Project: `/Users/hanfei/rork-hoopshighlights-ai_Final/ios/HoopsClips.xcodeproj`
- Scheme: `HoopsClips`
- Simulator: `iPhone 17`
- Test selector: `-only-testing:HoopsClipsTests`
- Result: `SUCCEEDED`
- Count: `181 passed, 0 failed, 0 skipped`
- Diagnostics: `warnings: []`, `errors: []`
- Build log:
  `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-06-10T07-44-29-676Z_pid5998_325fc96c.log`
- Result bundle:
  `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-10T07-44-29-676Z_pid5998_c4ed679b.xcresult`

Notes:

- This confirms the `CloudAnalysisService` await-warning cleanup is clean on
  current `main`.
- The focused unit lane includes the app language store, cloud analysis copy,
  cloud edit request/response, duplicate suppression, render status, runtime
  config, telemetry redaction, and import-policy tests.

## Simulator screenshot pass

Build and launch:

- XcodeBuildMCP `build_sim`: `SUCCEEDED`, diagnostics `warnings: []`, `errors: []`
- XcodeBuildMCP `build_run_sim`: `SUCCEEDED`, diagnostics `warnings: []`, `errors: []`
- App bundle: `atrak.charlie.hoopsclips`
- Simulator: `A46E2157-77ED-42CE-959D-65C068681A47`

Screenshots captured:

- Rookie guide overlay:
  `/var/folders/zd/0b3nmw551mdgk8ybwgcbt1380000gn/T/screenshot_optimized_656699c4-d663-4125-8a4f-2c3958e1096e.jpg`
- Player:
  `/var/folders/zd/0b3nmw551mdgk8ybwgcbt1380000gn/T/screenshot_optimized_9fb021e0-90f3-41f9-88e1-d677396cfd92.jpg`
- Review:
  `/var/folders/zd/0b3nmw551mdgk8ybwgcbt1380000gn/T/screenshot_optimized_250bbc00-4369-47f6-a3d1-0d07143b013b.jpg`
- Export:
  `/var/folders/zd/0b3nmw551mdgk8ybwgcbt1380000gn/T/screenshot_optimized_140728d4-4f47-4cf9-b0c4-6d1ab4f33836.jpg`
- History:
  `/var/folders/zd/0b3nmw551mdgk8ybwgcbt1380000gn/T/screenshot_optimized_86db6de4-a864-4147-b662-85c3e71cd55b.jpg`
- Settings:
  `/var/folders/zd/0b3nmw551mdgk8ybwgcbt1380000gn/T/screenshot_optimized_fe77ed78-7690-43a2-8c78-3dee41ca6921.jpg`

Visual QA result:

- Native page titles are no longer clipped or too far left on Player, Review,
  Export, History, or Settings.
- Rookie guide overlay is readable in the English pass and does not stack copy
  into unusable columns.
- Export empty state does not show the duplicated status-card progress content.

Remaining screenshot QA:

- A Chinese-language rookie guide screenshot pass is still recommended before
  public launch, because copy length and wrapping can differ materially.

## TestFlight upload proof

- Workflow: `iOS Internal TestFlight Upload`
- Run ID: `27259751307`
- URL:
  `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/27259751307`
- Event: `workflow_dispatch`
- Commit: `06a7775c0b46505c1eec453ceab0f7602532cd7d`
- Conclusion: `success`
- App target build number in current project: `18`
- Marketing version: `1.0.0`
- Bundle ID: `atrak.charlie.hoopsclips`

Successful workflow steps included:

- Verify internal staging build settings
- Materialize App Store Connect API key
- Build signed internal staging archive
- Verify archive metadata
- Upload to internal TestFlight
- Print next-step summary
- Remove App Store Connect API key

Notes:

- Build `18` does not need to be bumped for this pass because the current-main
  workflow upload succeeded.
- Earlier failed upload attempts were superseded by commit `06a7775c`, which
  archives without development signing and lets export/upload signing handle the
  distribution step.

## Staging cloud deploy proof

- Workflow: `Cloud Edit Deploy Preflight`
- Run ID: `27260636955`
- URL:
  `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/27260636955`
- Event: `workflow_dispatch`
- Commit: `06a7775c0b46505c1eec453ceab0f7602532cd7d`
- Conclusion: `success`

Successful workflow jobs included:

- Worker typecheck and dry run
- Editing backend Python tests
- Secret-safe launch evidence snapshot
- Verify cloud edit deploy secrets
- Verify editing deploy preflight
- Verify Wrangler token authentication
- Verify staging Worker secret names
- Verify staging deployment read scope
- Verify staging deploy dry run with CI token
- Deploy staging editing service
- Verify direct editing version after deploy
- Deploy staging Worker
- Verify Worker editing version after deploy

## Current cloud endpoint proof

Direct editing `/version`:

```json
{
  "backendModelVersion": "editing-cloud-v1",
  "gitSha": "06a7775c0b46505c1eec453ceab0f7602532cd7d",
  "service": "hoopclips-editing"
}
```

Direct editing feature flags:

```json
{
  "aiClipGptEditorEnabled": true,
  "aiClipGptPlanEditEnabled": true,
  "aiClipGptRevisionEnabled": true,
  "aiEditEnabled": true,
  "aiEditFreeWatermarkRequired": true,
  "aiEditLiveRenderEnabled": true,
  "aiEditProExportsEnabled": false,
  "aiEditRevisionEnabled": true,
  "aiEditTemplatePackEnabled": true,
  "gptHighlightRerankerEnabled": true
}
```

Direct editing GPT reranker:

```json
{
  "configured": true,
  "enabled": true,
  "model": "gpt-4.1"
}
```

Direct editing `/readyz`:

```json
{
  "authConfigured": true,
  "environment": "staging",
  "renderStorage": {
    "downloadTtlSeconds": 900,
    "provider": "r2",
    "providerReady": true,
    "uploadRootWritable": true
  },
  "service": "hoopclips-editing",
  "status": "ok"
}
```

Worker `/v1/editing/version`:

```json
{
  "backendModelVersion": "editing-cloud-v1",
  "gitSha": "06a7775c0b46505c1eec453ceab0f7602532cd7d",
  "service": "hoopclips-editing"
}
```

Worker feature flags:

```json
{
  "aiClipGptEditorEnabled": true,
  "aiClipGptPlanEditEnabled": true,
  "aiClipGptRevisionEnabled": true,
  "aiEditEnabled": true,
  "aiEditFreeWatermarkRequired": true,
  "aiEditLiveRenderEnabled": true,
  "aiEditProExportsEnabled": false,
  "aiEditRevisionEnabled": true,
  "aiEditTemplatePackEnabled": true,
  "gptHighlightRerankerEnabled": true
}
```

Worker GPT reranker:

```json
{
  "configured": true,
  "enabled": true,
  "model": "gpt-4.1"
}
```

Notes:

- A Python `urllib` request returned `403`, but the same Worker URL with the
  workflow-equivalent `curl` request returned HTTP `200` and current JSON.
- The CI deploy workflow also verified Worker `/v1/editing/version` immediately
  after the deploy.

## Real cloud render smoke

Source:

- File: `/tmp/hoopclips-live-smoke-real/troy-buzzer-smoke.mp4`
- Source object key:
  `uploads/c11b2c648bb844fabe2b5ca328eec2a1/troy-buzzer-smoke.mp4`
- Source fixture basis: Troy vs El Dorado real-game clip, short buzzer-beater
  window from the user's 57-minute source video.

Post-deploy smoke summary:

- Summary file:
  `/tmp/hoopclips-live-smoke-real/real-troy-current-smoke-1781077292/real_troy_postdeploy_smoke_summary.json`
- Install ID: `real-troy-current-smoke-1781077292`
- Edit job ID: `edit_17ea5d9d1a6e4cc48598bbc4a1601eb2`
- Base render job ID: `render_eb3ff351f6344728ad09ff6e637ca1c5`
- Revision ID: `rev_7aeb51677bc3421da20236b9cbc6a824`
- Revision render job ID: `render_3f92f8650b39467d8bbfad8e19d08e7e`

Base media proof:

```json
{
  "audioCodec": "aac",
  "duration": "13.822005",
  "format": "mov,mp4,m4a,3gp,3g2,mj2",
  "height": 1280,
  "size": "1129425",
  "videoCodec": "h264",
  "width": 720
}
```

Revision media proof:

```json
{
  "audioCodec": "aac",
  "duration": "13.822005",
  "format": "mov,mp4,m4a,3gp,3g2,mj2",
  "height": 1280,
  "size": "1138712",
  "videoCodec": "h264",
  "width": 720
}
```

Notes:

- This smoke proves Worker to Cloud Run to R2-backed render flow on real
  basketball footage, including a revision render.
- Synthetic smoke fixtures are now stale for GPT-enabled staging because the GPT
  reranker correctly rejects non-basketball synthetic clips with an empty clip
  list. The real Troy clip is the stronger launch smoke.

## Real iPhone TestFlight smoke

Status: not final-proofed.

Current local device check:

```text
charlie's iPhone / charlie的iPhone
Identifier: E5786BB6-0095-5509-8B85-110C0B5CE6D3
State: unavailable
Model: iPhone 15 Pro (iPhone16,1)
```

Required phone flow still to capture on TestFlight build `18`:

- Install/open TestFlight build
- Import video
- Cloud analysis
- Review clips
- Export
- AI Edit render
- Preview
- More Hype revision
- Revised preview
- Share/open-in

Evidence to capture from the phone smoke:

- Screenshots or screen recording
- Analysis job ID
- Edit job ID
- Render job ID
- Revision ID
- Revised render job ID
- Worker version SHA
- Cloud Run version SHA
- App build number

## Remaining launch blockers

1. Real iPhone TestFlight full smoke is still missing final proof because the
   connected device currently reports `unavailable`.
2. Production cutover still needs an explicit release-owner decision after the
   real phone smoke passes.
3. Accuracy is accepted risk for this launch pass, but formal 85% labeled
   accuracy proof is still not completed.

## Recommended next improvements

1. Add an in-app smoke checklist/debug sheet that can copy build number, Worker
   SHA, Cloud Run SHA, analysis job ID, render job ID, and revision ID.
2. Add bilingual screenshot QA for the rookie guide so English and Chinese copy
   wrapping are both caught before upload.
3. Add a real-basketball smoke fixture path to replace the old synthetic smoke
   scripts when GPT reranking is enabled.

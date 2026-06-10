# HoopClips current-tip launch evidence - 2026-06-10

This document captures the current launch evidence for `main` after the build-19 TestFlight refresh and current-tip staging cloud redeploy.

## Current checkout

- Branch: `main`
- Commit: `8dea6baab81f2cb66f0cc86c6f6d926b73e85352`
- Short commit: `8dea6baa Align TestFlight archive metadata check with build 19`
- App build number: `19`
- Marketing version: `1.0.0`
- Bundle ID: `atrak.charlie.hoopsclips`

Repo hygiene before the current evidence update:

- `git status --short --branch`: `## main...origin/main`
- Intentional launch-proof changes since build 18:
  - app target `CURRENT_PROJECT_VERSION` bumped to `19`
  - internal staging verifier expected build bumped to `19`
  - TestFlight archive metadata verifier expected `CFBundleVersion` bumped to `19`

## iOS unit tests

- Tool: XcodeBuildMCP `test_sim`
- Project: `/Users/hanfei/rork-hoopshighlights-ai_Final/ios/HoopsClips.xcodeproj`
- Scheme: `HoopsClips`
- Simulator: `iPhone 17`
- Selector: `-only-testing:HoopsClipsTests`
- Result: `SUCCEEDED`
- Count: `181 passed, 0 failed, 0 skipped`
- Diagnostics: `warnings: []`, `errors: []`
- Build log:
  `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/test_sim_2026-06-10T07-56-52-806Z_pid5998_9e77d34a.log`
- Result bundle:
  `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-06-10T07-56-52-806Z_pid5998_fcef3cb3.xcresult`

This verifies the `CloudAnalysisService` await-warning cleanup remains clean after the build-19 bump.

## Simulator screenshot pass

Build and launch evidence:

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

- Native page titles are no longer clipped or too far left on Player, Review, Export, History, or Settings.
- Rookie guide overlay is readable in the English pass and does not stack copy into unusable columns.
- Export empty state does not show duplicated status-card progress content.

Remaining screenshot QA recommendation:

- Add an automated Chinese-language rookie guide screenshot pass before public launch.

## TestFlight upload proof

Current successful upload:

- Workflow: `iOS Internal TestFlight Upload`
- Run ID: `27262373169`
- URL: `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/27262373169`
- Event: `workflow_dispatch`
- Commit: `8dea6baab81f2cb66f0cc86c6f6d926b73e85352`
- Conclusion: `success`
- Job: `Build internal staging TestFlight archive`
- Job duration: `7m4s`
- App build: `19`

Successful steps included:

- Verify internal staging build settings
- Materialize App Store Connect API key
- Build signed internal staging archive
- Verify archive metadata
- Upload to internal TestFlight
- Print next-step summary
- Remove App Store Connect API key

Superseded attempts:

- `27261937838` failed because internal staging verifier still expected build `18` after the app was bumped to `19`.
- `27262035365` failed because archive metadata verifier still expected `CFBundleVersion=18` after the archive correctly resolved to `19`.
- Both verifier mismatches are now fixed on current `main`.

Latest doc-only push codecheck:

- Workflow: `iOS Internal TestFlight Upload`
- Run ID: `27263364914`
- Commit: `80d5fe176a1a88e9496d51f0906cbdd3c64f8da5`
- Conclusion: `success`
- Notes: archive/upload job was skipped on push; no-secret internal staging codecheck passed, including internal staging config verification, export-options validation, and Debug test build without signing.

## Staging cloud deploy proof

Current successful deploy:

- Workflow: `Cloud Edit Deploy Preflight`
- Run ID: `27262781244`
- URL: `https://github.com/charlie2233/rork-hoopshighlights-ai_Final/actions/runs/27262781244`
- Event: `workflow_dispatch`
- Commit: `8dea6baab81f2cb66f0cc86c6f6d926b73e85352`
- Conclusion: `success`

Successful jobs included:

- Secret-safe launch evidence snapshot
- Worker typecheck and dry run
- Editing backend Python tests
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

Latest doc-only push codecheck:

- Workflow: `Cloud Edit Deploy Preflight`
- Run ID: `27263364902`
- Commit: `80d5fe176a1a88e9496d51f0906cbdd3c64f8da5`
- Conclusion: `success`
- Notes: deploy jobs were skipped on push; Worker typecheck/dry run and editing backend Python tests passed.

## Current cloud endpoint proof

Independent endpoint checks after deploy:

Worker `/v1/editing/version`:

```json
{
  "backendModelVersion": "editing-cloud-v1",
  "gitSha": "8dea6baab81f2cb66f0cc86c6f6d926b73e85352",
  "matchesHead": true,
  "service": "hoopclips-editing"
}
```

Direct editing `/version`:

```json
{
  "backendModelVersion": "editing-cloud-v1",
  "gitSha": "8dea6baab81f2cb66f0cc86c6f6d926b73e85352",
  "matchesHead": true,
  "service": "hoopclips-editing"
}
```

Current feature flags from both Worker and direct editing:

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

GPT reranker:

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

## Real cloud render smoke

Source:

- Local file: `/tmp/hoopclips-live-smoke-real/troy-buzzer-smoke.mp4`
- Source object key: `uploads/2bf987c8305345d8a08965cf6d849892/troy-buzzer-smoke.mp4`
- Fixture basis: real Troy vs El Dorado basketball clip from the user's source video.

Current-main post-deploy smoke:

- Summary file: `/tmp/hoopclips-live-smoke-real/real-troy-current-main-smoke-1781079768/real_troy_current_main_smoke_summary.json`
- Install ID: `real-troy-current-main-smoke-1781079768`
- Worker URL: `https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev`
- Version SHA during smoke: `8dea6baab81f2cb66f0cc86c6f6d926b73e85352`
- Backend model version: `editing-cloud-v1`
- GPT reranker: enabled, configured, model `gpt-4.1`
- Edit job ID: `edit_b467334a661b4c448cd132eeec8bdb67`
- Base render job ID: `render_d65f4db091604de1b0436689e799f43e`
- Revision ID: `rev_28c443f360d64acb8d736d695453eb4d`
- Revision render job ID: `render_b6b0cf2368b84b9e8195e375881d49cf`

Base render downloaded MP4:

- Path: `/tmp/hoopclips-live-smoke-real/real-troy-current-main-smoke-1781079768/base.mp4`
- Container: `mov,mp4,m4a,3gp,3g2,mj2`
- Duration: `13.822005s`
- Size: `1011528` bytes
- Video: H.264, `720x1280`, `9:16`, `30/1`, `yuv420p`
- Audio: AAC LC, stereo, `44100 Hz`

Revision render downloaded MP4:

- Path: `/tmp/hoopclips-live-smoke-real/real-troy-current-main-smoke-1781079768/revised.mp4`
- Container: `mov,mp4,m4a,3gp,3g2,mj2`
- Duration: `13.822005s`
- Size: `1020977` bytes
- Video: H.264, `720x1280`, `9:16`, `30/1`, `yuv420p`
- Audio: AAC LC, stereo, `44100 Hz`

Notes:

- This smoke proves Worker to Cloud Run to R2-backed render flow on real basketball footage after the current-tip deploy.
- It also proves the revision render path by producing a More Hype revised MP4.
- Synthetic smoke fixtures remain a poor GPT-enabled launch signal because GPT can correctly reject synthetic non-basketball clips.

## Real iPhone TestFlight smoke

Status: not final-proofed.

Current local device check from this evidence pass:

```text
charlie's iPhone / charlie的iPhone
Identifier: E5786BB6-0095-5509-8B85-110C0B5CE6D3
State: available (paired)
Model: iPhone 15 Pro (iPhone16,1)
```

Mac-side app install/launch proof:

- HoopClips bundle launch succeeded on the paired iPhone:
  `Launched application with atrak.charlie.hoopsclips bundle identifier.`
- Installed HoopClips app metadata on the phone:
  - Name: `HoopClips`
  - Bundle ID: `atrak.charlie.hoopsclips`
  - Version: `1.0.0`
  - Bundle Version: `16`
- TestFlight app is installed:
  - Bundle ID: `com.apple.TestFlight`
  - Version: `4.2.1`
  - Bundle Version: `628.1`
- TestFlight launch succeeded on the paired iPhone:
  `Launched application with com.apple.TestFlight bundle identifier.`

Current phone-smoke blocker:

- The phone currently has HoopClips build `16`, not uploaded build `19`.
- The user needs to update HoopClips inside TestFlight to build `19` before the full smoke can count as current launch proof.
- XcodeBuildMCP device workflows are not enabled in this session; only simulator workflows are available through the MCP tool.

Required phone flow still to capture on TestFlight build `19`:

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

1. Real iPhone TestFlight full smoke is still missing final proof. The phone is paired/available, TestFlight is installed, and build `19` is uploaded, but the phone currently has HoopClips build `16`; update to build `19` first.
2. Production cutover still needs an explicit release-owner go/no-go after the real phone smoke passes.
3. Accuracy is accepted risk for this launch pass, but formal 85% labeled accuracy proof is still not completed.

## Recommended next improvements

1. Add an in-app smoke checklist/debug sheet that can copy build number, Worker SHA, Cloud Run SHA, analysis job ID, render job ID, and revision ID.
2. Add bilingual screenshot QA for the rookie guide so English and Chinese copy wrapping are both caught before upload.
3. Replace synthetic smoke scripts with a real-basketball GPT smoke fixture path for GPT-reranker-enabled staging.

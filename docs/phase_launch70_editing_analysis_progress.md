# Phase Launch70 Editing Analysis Progress

## Goal

Keep selected-team cloud analysis alive with real backend progress while the editing service performs long-running team-aware analysis. This phase does not move analysis/rendering into iOS.

## Live Failure That Triggered This Patch

- Branch before this phase: `codex/phase-launch69-selected-team-editing-provider`
- Commit before this phase: `537e07518a1a13ed0de68ee39e5dfac35dbba2cd`
- Command:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch69_downloads_326_team \
  --video-id downloads_326_1770329282 \
  --team-mode team \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch69 \
  --manifest artifacts/team_highlight_accuracy_launch69_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 1800
```

- Result: failed.
- Job ID: `8d0781a768cf45fd87c95dffe9d2e5ae`
- Failure: `failed_timeout`, `Inference callback timed out after 3 accepted attempts.`
- Cloud Run request log proof: `hoopclips-editing-staging` accepted `POST /v1/analyze` at `2026-05-30T20:27:33Z`.

This proved the selected-team request reached the editing provider. The remaining issue was that the Worker had no observable progress before its stale-processing timeout.

## Changes

- Editing `/v1/analyze` now sends real `processing` callbacks through the existing Worker callback endpoint before and during analysis.
- Editing still sends the existing heartbeat endpoint, but progress callbacks use the same route as final success/failure callbacks for better liveness coverage.
- Editing emits safe structured analysis events:
  - `analysis.dispatch.started`
  - `analysis.heartbeat.sent` / `analysis.heartbeat.failed`
  - `analysis.progress_callback.sent` / `analysis.progress_callback.failed`
  - `analysis.source.materialized`
  - `analysis.run.started`
  - `analysis.run.completed`
  - `analysis.callback.sent` / `analysis.callback.failed`
- Worker recovery now has a configurable selected-team timeout:
  - `SELECTED_TEAM_PROCESSING_TIMEOUT_SECONDS`
  - default/staging value: `1800`
- Normal all-team/legacy processing keeps the existing `PROCESSING_TIMEOUT_SECONDS` behavior.

## Safety

- No source URLs, object keys, presigned URLs, R2 credentials, or secrets are emitted in the new logs.
- GPT/analysis remains cloud-owned.
- iOS receives only real job status/progress from the Worker.
- No fake thinking, fake ETA, or artificial waits were added.

## Validation

Local verification before deploy:

```bash
python3 -m py_compile services/editing/editing_app/main.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_analyze_endpoint_accepts_worker_dispatch_and_posts_callback -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover services/editing/tests -v
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test -- --test-name-pattern 'processing callbacks|selected-team editing jobs|heartbeat|timeout|selected team'
npm --prefix services/control-plane test
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover -s scripts -p 'test_*.py' -v
npm --prefix services/control-plane run deploy:staging:dry-run
cd services/control-plane && npx prettier --check src/env.ts src/recovery.ts test/control-plane-timeout-recovery.test.ts ../../scripts/control-plane-harness.ts
cd services/control-plane && npx prettier --check --trailing-comma none wrangler.jsonc
git diff --check
```

- `py_compile`: passed.
- Focused editing `/v1/analyze` progress callback test: passed.
- Full editing-service suite: 116 tests passed.
- Control-plane typecheck: passed.
- Focused control-plane timeout/selected-team suite: 33 tests passed.
- Full control-plane suite: 33 tests passed.
- Launch script suite: 115 tests passed after keeping `wrangler.jsonc` parseable without trailing commas.
- Worker staging dry run: passed and showed `SELECTED_TEAM_PROCESSING_TIMEOUT_SECONDS=1800`.
- Prettier check: passed for TypeScript and `wrangler.jsonc` with no trailing commas.
- `git diff --check`: passed.

## CI Attempt

- GitHub Actions run: `26694624663`
- Result: failed before deploy.
- Passed: Worker typecheck/dry run and editing backend Python tests.
- Failed: launch script tests rejected the first `wrangler.jsonc` formatting because trailing commas made the repo's JSONC preflight parser fail.
- Local fix: removed trailing commas, reran the exact failing test plus the full launch script suite and staging dry run successfully.

- GitHub Actions run: `26694736663`
- Result: passed.
- Deployed staging editing service and staging Worker for commit `5fb981dfcbd75492adea2270ed9ed99298602317`.
- Staging version probe passed for direct editing `/version` and Worker `/v1/editing/version`.

## Live Launch70 Finding

Real selected-team collection was rerun after deploy:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch70_downloads_326_team \
  --video-id downloads_326_1770329282 \
  --team-mode team \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch70 \
  --manifest artifacts/team_highlight_accuracy_launch70_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 2400
```

- Job ID: `7ab4ef8e55ca46fb9e9a5318d4cc8e3f`
- Editing service accepted and completed analysis.
- Editing logs showed `analysis.run.completed`.
- Editing callbacks and heartbeats failed before reaching the Worker.
- Route probe without a service User-Agent returned Cloudflare `error code: 1010`.
- Route probe with `User-Agent: HoopClipsEditingService/1.0` reached the Worker and returned the expected invalid-secret JSON.

This means the selected-team backend was no longer stuck in analysis; Cloudflare Browser Integrity rejected default Python `urllib` callback requests before the Worker route could authenticate them.

## Follow-Up Patch

- Editing callback and heartbeat requests now send `User-Agent: HoopClipsEditingService/1.0`.
- Safe callback failure logging now includes failure codes such as `callback_http_403` and `heartbeat_http_403`, without logging secrets, credentials, object keys, source URLs, or full presigned URLs.
- Added a regression test that verifies both callback and heartbeat requests include the service User-Agent and inference callback secret header.

Additional local validation:

```bash
python3 -m py_compile services/editing/editing_app/main.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_worker_callbacks_use_service_user_agent services.editing.tests.test_editing_service.EditingServiceTests.test_analyze_endpoint_accepts_worker_dispatch_and_posts_callback -v
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover services/editing/tests -v
```

- `py_compile`: passed.
- Focused callback/User-Agent tests: passed.
- Full editing-service suite: 117 tests passed.

## Callback Fix Deploy

To avoid another full GitHub Actions deploy run, only the editing Cloud Run service was redeployed with the existing Cloud Build config:

```bash
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG="$(git rev-parse HEAD)"
```

- Commit: `bdbd3f2c408f67b484896f5f5a025e55bf990b90`
- Cloud Build ID: `5fc61324-aca8-45f1-9f90-b7ff165f511f`
- Result: `SUCCESS`
- Cloud Run revision: `hoopclips-editing-staging-00034-xj4`
- Traffic: 100% to `hoopclips-editing-staging-00034-xj4`
- Note: deploy printed an IAM policy warning, but the existing service URL remained reachable.

Version proof:

```bash
python3 scripts/staging_version_probe.py --expected-git-sha "$(git rev-parse HEAD)" --json
```

- Direct editing `/version`: passed for `bdbd3f2c408f67b484896f5f5a025e55bf990b90`.
- Worker `/v1/editing/version`: passed for `bdbd3f2c408f67b484896f5f5a025e55bf990b90`.

## Live Launch70 Success

The same real selected-team collection was rerun after the callback fix deploy:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch70_downloads_326_team \
  --video-id downloads_326_1770329282 \
  --team-mode team \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch70 \
  --manifest artifacts/team_highlight_accuracy_launch70_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 2400
```

- Result: passed.
- Job ID: `36d008a66e454da899a8037721a53d78`
- Final job status: `completed`
- Detected teams: 2
- Selected team: `team_black` / `black`
- Clip count: 3
- Local artifact paths:
  - `artifacts/team_highlight_accuracy_launch70/launch70_downloads_326_team/analysis_result.json`
  - `artifacts/team_highlight_accuracy_launch70/launch70_downloads_326_team/manual_labels_template.json`
  - `artifacts/team_highlight_accuracy_launch70_manifest.json`

Safe Cloud Run event proof for job `36d008a66e454da899a8037721a53d78`:

- `analysis.dispatch.started`
- `analysis.heartbeat.sent` at `Preparing cloud analysis input`
- `analysis.progress_callback.sent` at `Preparing cloud analysis input`, progress `0.64`
- `analysis.source.materialized`
- `analysis.heartbeat.sent` at `Analyzing in cloud`
- `analysis.progress_callback.sent` at `Analyzing in cloud`, progress `0.72`
- `analysis.run.started`
- `analysis.run.completed`, `clipCount=3`
- `analysis.callback.sent`, `status=succeeded`

Selected-team analysis now has proven real backend progress callbacks and a final completion callback through the Worker. Manual labels are still needed to score the clips for the target 85%+ team/highlight accuracy gate.

## Candidate Recall Follow-Up

Live Launch70 diagnostics showed selected-team jobs were completing but under-producing the review pool before team filtering:

- black selected-team run: `preTeamFilterSegments=6`, `teamMatchedCandidateSegments=3`, `finalSegments=3`
- white selected-team run: `preTeamFilterSegments=6`, `teamMatchedCandidateSegments=3`, `finalSegments=3`
- all-teams run: `candidateSegments=1`, `finalSegments=1`

This made the accuracy gate impossible to prove from the current sample because there were only 7 total clips across the available real cloud cases.

Patch:

- Native candidate generation now keeps the strong hysteresis event segments but backfills with top non-overlapping candidate windows up to the configured candidate pool.
- This preserves deterministic CV/audio/FFmpeg-backed candidate generation and does not move analysis into iOS.
- GPT/team scan gets more cloud-generated candidates to judge, including uncertain moments that can remain reviewable.
- Explicit team-aware analysis now routes through the editing provider for both `mode: "team"` and `mode: "all"`.
- Normal analysis requests without `teamSelection` still keep the legacy inference-first provider order.

Local validation for the recall patch:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality.PipelineQualityTests.test_native_candidate_backfill_keeps_review_pool_when_hysteresis_finds_few_sequences
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests
/Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/pipeline.py ios/backend/tests/test_pipeline_quality.py
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
cd services/control-plane && npx prettier --check src/queue/consumer.ts test/control-plane-status-transitions.test.ts
npm --prefix services/control-plane run deploy:staging:dry-run
git diff --check
```

- Focused recall test: passed.
- Pipeline quality suite: 51 tests passed.
- Team quick-scan suite: 38 tests passed.
- Backend unittest discovery: 206 tests passed.
- `py_compile`: passed.
- Control-plane typecheck: passed.
- Control-plane tests: 33 tests passed.
- Prettier check: passed.
- Worker staging dry run: passed.
- `git diff --check`: passed.

Status:

- Not deployed yet.
- Next launch proof should deploy this backend change, rerun the three accuracy collection cases, and then generate a real `--team-accuracy-report` from human labels.

## Candidate Recall Deploy And Prescan Finding

The candidate-recall and all-teams routing patch was deployed through the existing GitHub workflow because local Wrangler was missing `CLOUDFLARE_API_TOKEN`:

```bash
gh workflow run "Cloud Edit Deploy Preflight" \
  --repo charlie2233/rork-hoopshighlights-ai_Final \
  --ref codex/phase-launch70-editing-analysis-progress \
  -f operation=deploy
```

- GitHub Actions run: `26696508062`
- Result: passed.
- Worker typecheck, routing tests, Worker dry run, editing backend tests, launch script tests, deploy credential checks, direct editing version check, staging Worker deploy, and Worker editing version check all passed.
- Deployed commit: `9b27207f78b3304d554c3480b0113437fe9cef07`.

Version probe after deploy:

```bash
python3 scripts/staging_version_probe.py --expected-git-sha "$(git rev-parse HEAD)" --json
```

- Direct editing `/version`: passed for `9b27207f78b3304d554c3480b0113437fe9cef07`.
- Worker `/v1/editing/version`: passed for `9b27207f78b3304d554c3480b0113437fe9cef07`.

The first post-deploy real black-team collection did not pass the pre-analysis team picker:

- Case: `launch71_downloads_326_team_black`
- Job ID: `a5e1e20628844eaf8cbdf3eeecf9c746`
- Team scan response: `status=unavailable`, `detectedTeams=[]`
- Editing service request proof: `POST /v1/team-scan` returned `200` at `2026-05-30T22:24:23Z`.

Diagnosis:

- The candidate recall patch increased the real team-scan candidate context available to GPT.
- The interactive team picker was still using the full quick-scan budget and a 24 second OpenAI timeout.
- The request returned a clean `unavailable` result rather than a team list, so launch proof cannot claim selected-team readiness from that run.

Follow-up patch:

- Full cloud analysis keeps the richer candidate pool.
- The pre-analysis team picker now uses a bounded real GPT vision prescan budget:
  - 12 candidate clips
  - 4 frames per candidate
  - 8 rich candidates
  - 56 max candidate frames
  - 60 second minimum OpenAI timeout
- Both local API team-scan endpoints and the editing service `/v1/team-scan` use the same prescan settings.
- The full analysis path can still use the normal richer settings for final team attribution and highlight filtering.

Local validation for the prescan patch:

```bash
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest services.editing.tests.test_editing_service
/Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/config.py ios/backend/app/api.py ios/backend/app/team_quick_scan.py services/editing/editing_app/main.py
git diff --check
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests
```

- Team quick-scan suite: 39 tests passed.
- Editing service suite: 56 tests passed.
- `py_compile`: passed.
- `git diff --check`: passed.
- Backend unittest discovery: 207 tests passed.

## Prescan Fix Deploy And Live Launch71 Proof

The prescan patch was committed and pushed separately:

- Commit: `ce7c8012b9dad5a461974118552fb5c45964a980`
- Branch: `codex/phase-launch70-editing-analysis-progress`

To avoid another GitHub Actions deploy run, only the editing Cloud Run service was redeployed:

```bash
gcloud builds submit . \
  --project=hoopsclips-9d38f \
  --config=services/editing/cloudbuild.yaml \
  --substitutions=_IMAGE_TAG="$(git rev-parse HEAD)"
```

- Cloud Build ID: `1c4983c0-9769-433c-8e17-b2da54c77d63`
- Result: `SUCCESS`
- Cloud Run revision: `hoopclips-editing-staging-00037-v2m`
- Traffic: 100% to `hoopclips-editing-staging-00037-v2m`
- Note: deploy printed the same IAM policy warning as prior deploys; the service remained reachable.

Version proof:

```bash
python3 scripts/staging_version_probe.py --expected-git-sha "$(git rev-parse HEAD)" --json
```

- Direct editing `/version`: passed for `ce7c8012b9dad5a461974118552fb5c45964a980`.
- Worker `/v1/editing/version`: passed for `ce7c8012b9dad5a461974118552fb5c45964a980`.

The real launch video cases were rerun after the prescan deploy:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch71_downloads_326_team_black \
  --video-id downloads_326_1770329282 \
  --team-mode team \
  --selected-color-label black \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch71 \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 2400
```

- Result: passed.
- Job ID: `f6e237fd51cc471a8f880a06af0e626d`
- Detected teams: 2
- Selected team: `team_black` / `black`
- Clip count: 25
- Prescan timing proof: editing `POST /v1/team-scan` returned `200` in about 31 seconds.

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch71_downloads_326_team_white \
  --video-id downloads_326_1770329282 \
  --team-mode team \
  --selected-color-label white \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch71 \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 2400
```

- Result: passed.
- Job ID: `df46dd0daa3c451abece0079cd44606a`
- Detected teams: 2
- Selected team: `team_white` / `white`
- Clip count: 11

```bash
python3 scripts/collect_team_highlight_accuracy_case.py \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --case-id launch71_downloads_326_all \
  --video-id downloads_326_1770329282 \
  --team-mode all \
  --duration-seconds 30 \
  --output-dir artifacts/team_highlight_accuracy_launch71 \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --poll-interval-seconds 5 \
  --timeout-seconds 2400
```

- Result: passed.
- Job ID: `5c9a4f3b187248b7b8056aef54f2bf2c`
- Team mode: `all`
- Clip count: 30
- This exercised the staging Worker route deployed by GitHub Actions run `26696508062`.

Local artifact paths:

- `artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_team_black/analysis_result.json`
- `artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_team_black/manual_labels_template.json`
- `artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_team_white/analysis_result.json`
- `artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_team_white/manual_labels_template.json`
- `artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_all/analysis_result.json`
- `artifacts/team_highlight_accuracy_launch71/launch71_downloads_326_all/manual_labels_template.json`
- `artifacts/team_highlight_accuracy_launch71_manifest.json`

Remaining accuracy gate:

- The backend now produces a launch-grade review pool across selected black, selected white, and all-teams modes.
- Human/manual labels are still required before claiming the 85% selected-team/highlight accuracy gate.
- A local review helper now creates an HTML page from the manifest and source video path. It only seeks within the original local video and edits manual-label JSON in the browser; it does not analyze, render, export, upload, or include raw upload/source URLs.
- Launch71 review page:

```bash
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
```

- Result: passed.
- Output: `artifacts/team_highlight_accuracy_launch71_review.html`
- Cases: 3
- Redaction check: no `uploadUrl`, `sourceObjectKey`, `sourceUrl`, `downloadUrl`, or `X-Amz-Signature` in the generated HTML.
- Run the label/report flow after manual review:

```bash
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --eval-output artifacts/team_highlight_accuracy_launch71_eval.json \
  --report-output artifacts/team_highlight_accuracy_launch71_report.json \
  --json
python3 -m scripts.evaluate_team_highlight_accuracy artifacts/team_highlight_accuracy_launch71_eval.json --json > artifacts/team_highlight_accuracy_launch71_report.json
python3 scripts/submission_readiness_preflight.py --team-accuracy-report artifacts/team_highlight_accuracy_launch71_report.json
```

## Launch72 Honest Analysis Status UI

Scope:

- Updated the iOS analysis progress card to show a second line of stage-specific copy derived from the real import/cloud analysis status.
- Added titles for real stages including uploading, choosing teams/jersey colors, finding candidate clips, queued cloud work, frame/action scoring, and finalizing Review.
- Kept the copy honest: no fake countdowns, artificial waits, or pretend backend work.

Validation:

```bash
git diff --check
```

- Result: passed.

```bash
# Build iOS Apps / XcodeBuildMCP
# Project: ios/HoopsClips.xcodeproj
# Scheme: HoopsClips
# Configuration: Debug
# Simulator: iPhone 17 Pro, iOS 26.0
build_sim -quiet
```

- Result: passed.
- Build log: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/logs/build_sim_2026-05-30T22-52-18-056Z_pid49862_de3c2d14.log`

## Launch72 Local Test Expansion

```bash
python3 -m py_compile \
  scripts/build_team_highlight_label_review_page.py \
  scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page
python3 -m unittest \
  scripts.test_build_team_highlight_label_review_page \
  scripts.test_build_team_highlight_eval_payload \
  scripts.test_build_launch_team_accuracy_report \
  scripts.test_submission_readiness_preflight \
  scripts.test_team_highlight_accuracy_eval
```

- Result: passed.
- Test count: 74.

Additional local backend validation:

```bash
PYTHONPATH=ios/backend \
  /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python \
  -m unittest discover ios/backend/tests
PYTHONPATH=ios/backend:services/editing \
  /tmp/hoopclips-editing-test-venv/bin/python \
  -m unittest services.editing.tests.test_editing_service
```

- Results: passed.
- Test counts: 207 backend tests, 56 editing-service tests.

Local archive:

```bash
xcodebuild \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath ios/archives/HoopsClips-Launch72.xcarchive \
  archive \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  CODE_SIGN_STYLE=Automatic \
  -allowProvisioningUpdates \
  -quiet
```

- Result: passed after injecting the local development team value from the local xcconfig without printing it.
- Archive: `ios/archives/HoopsClips-Launch72.xcarchive`
- The archive path is intentionally ignored by git via `ios/.gitignore`.

Local IPA export attempt:

```bash
cp ios/exportOptions.testflight-internal.plist /tmp/hoopclips-exportOptions.local.plist
/usr/libexec/PlistBuddy -c 'Set :destination export' /tmp/hoopclips-exportOptions.local.plist
xcodebuild \
  -exportArchive \
  -archivePath ios/archives/HoopsClips-Launch72.xcarchive \
  -exportPath ios/build/HoopsClips-Launch72-export \
  -exportOptionsPlist /tmp/hoopclips-exportOptions.local.plist \
  -allowProvisioningUpdates \
  -quiet
```

- Result: failed locally with `No Accounts` and no `iOS Distribution` signing certificate.
- Impact: local archive proof is valid, but IPA export/upload still needs the configured GitHub TestFlight workflow or a local App Store Connect account/distribution certificate.
- Safety: the checked-in `ios/exportOptions.testflight-internal.plist` was not run directly because it has `destination=upload` and submission is still blocked.

Preflight with local archive:

```bash
python3 scripts/submission_readiness_preflight.py \
  --archive-path ios/archives/HoopsClips-Launch72.xcarchive \
  --json
```

- Result: failed as expected until remaining gates are satisfied.
- Current summary before committing this doc update: 27 pass, 7 fail, 0 warn.
- Upload artifact check passed with the local archive.
- Remaining fails: missing launch-grade team accuracy report, unavailable connected iPhone, current-commit main CI/preflight reruns, current-commit iOS TestFlight upload proof, and installed TestFlight post-install smoke.

## Launch72 Review-Notes Triage

External read-only review notes inspected:

- `/Users/hanfei/Desktop/HoopClips-Review-Notes-2026-05-30_full.txt`
- `/Users/hanfei/.codex/attachments/a9654658-09e9-4f2e-a6ee-2fcf12f30cda/pasted-text.txt`

Findings checked against the current launch worktree:

- Photo import temp filename interpolation bug: not present in this branch. Current code uses `imported_video_\(UUID().uuidString).\(fileExtension)`.
- CloudEditService locker rerender request body regression: stale for this branch. Focused tests passed and verified `installId`, `forceNew`, and `idempotencyKey` payloads.
- Begin video import main-actor concern: current Photos import path keeps file-backed transfer/copy off the main actor and returns UI state updates through `MainActor.run` where needed.
- Minor ContentView indentation/style: not launch-blocking and not touched in this branch.

Focused iOS test:

```bash
# Build iOS Apps / XcodeBuildMCP
# Project: ios/HoopsClips.xcodeproj
# Scheme: HoopsClips
# Configuration: Debug
# Simulator: iPhone 17 Pro, iOS 26.0
test_sim -only-testing:HoopsClipsTests/CloudEditServiceTests -quiet
```

- Result: passed.
- Test count: 11.
- Result bundle: `/Users/hanfei/Library/Developer/XcodeBuildMCP/workspaces/rork-hoopshighlights-ai_Final-b63ced5e161c/result-bundles/test_sim_2026-05-30T23-11-38-260Z_pid49862_5027249a.xcresult`

GPT-led clipping quality evidence:

```bash
PYTHONPATH=ios/backend:services/editing \
  /tmp/hoopclips-editing-test-venv/bin/python \
  -m unittest services.editing.tests.test_gpt_reranker
```

- Result: passed.
- Test count: 61.
- Coverage includes no-full-video GPT payloads, structured output validation, keyframe sampling, selected-team filtering, uncertain clip review preservation, blocks/steals/defensive-stop handling, defensive context expansion, GPT fallback behavior, and patch validation.

Device status:

```bash
xcrun devicectl list devices
```

- Result: `charlie的iPhone` detected but still `unavailable`, so installed TestFlight smoke remains blocked.

## Launch72 Label Review Helper Hardening

The manual team/highlight review page was tightened so the launch-grade label pass is less error-prone:

- Added an overall and per-case label completion summary.
- Replaced free-text expected team/event/outcome fields with constrained selects.
- Added explicit basketball defensive events and outcomes, including block, steal, forced turnover, defensive stop, and blocked-shot outcome labels.
- Marked complete clip cards visually once reviewed, team, highlight, event, and outcome are filled.
- Warns before downloading a case label JSON while clips are still incomplete.
- Keeps the page as a local review helper only: no upload, analysis, rendering, export, source URL, object key, or presigned URL handling.

Validation:

```bash
python3 -m py_compile \
  scripts/build_team_highlight_label_review_page.py \
  scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
rg -n 'onclick="seekClip\("' artifacts/team_highlight_accuracy_launch71_review.html
rg -n 'X-Amz-Signature|uploadUrl|sourceObjectKey|sourceUrl|downloadUrl|presignedUrl|resultObjectKey|uploadHeaders' \
  artifacts/team_highlight_accuracy_launch71_review.html
```

- `py_compile`: passed.
- Focused review-page test: 2 tests passed.
- Review page generation: passed for 3 cases.
- Generated review page contains 66 clip cards and 1 local video tag.
- Completion controls are present: label progress, incomplete-download warning, selected-team options, and defensive labels.
- Leak checks: no unsafe `seekClip` inline quoting and no signed URLs/object keys/source/upload URL fields found in the generated HTML.
- Browser plugin note: safe-desktop Browser startup required `SAFE_MCP_ACTION_PIN`, so visual browser automation was not available in this session; verification used generated HTML checks instead.

## Launch72 Manual Label Gate Hardening

The evaluator payload builder was tightened so the 85% launch report cannot be built from ambiguous manual labels:

- Reviewed label rows now require `expected.outcome`, matching the review page controls and the outcome-quality gates.
- Reviewed label rows now validate `expected.isHighlight` through an explicit boolean parser.
- String values such as `"false"` are preserved as `False` instead of being coerced truthy by Python.
- `build_launch_team_accuracy_report.py --label-status` now summarizes every manifest case before report generation, including complete/incomplete clip counts and missing field counts.
- This remains metadata-only validation; it does not inspect video pixels, call providers, upload, render, or expose secrets.

Validation:

```bash
python3 -m py_compile \
  scripts/build_team_highlight_eval_payload.py \
  scripts/build_launch_team_accuracy_report.py \
  scripts/test_build_team_highlight_eval_payload.py \
  scripts/test_build_launch_team_accuracy_report.py
python3 -m unittest \
  scripts.test_build_team_highlight_eval_payload \
  scripts.test_build_launch_team_accuracy_report \
  -v
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --label-status \
  --json
```

- `py_compile`: passed.
- Focused eval payload/report suite: 14 tests passed.
- Launch71 label status result: incomplete, 0 / 66 clips complete.
- Missing fields across Launch71: `needsLabel=false`, `expected.teamId`, `expected.isHighlight`, `expected.eventType`, and `expected.outcome` on all 66 clips.

## Launch72 Device Smoke Blocker Detail

The connected-device preflight now includes safe CoreDevice detail when an iPhone is detected but unavailable:

- It still fails the gate until an available physical iPhone can run the installed TestFlight smoke.
- It now surfaces non-secret fields such as pairing state, tunnel state, Developer Mode status, DDI service availability, and last connection date.
- This helps distinguish an unavailable device/tunnel problem from an app build or signing problem.

Current local device diagnostic:

```bash
xcrun devicectl device info details --device E5786BB6-0095-5509-8B85-110C0B5CE6D3
system_profiler SPUSBDataType | rg -n -C 5 'iPhone|Apple Mobile|E5786BB6|charlie'
```

- `charlie的iPhone` is paired.
- Developer Mode is enabled.
- `tunnelState=unavailable`.
- `ddiServicesAvailable=false`.
- USB system profile did not show the iPhone, so this looks like a physical connection/CoreDevice tunnel issue rather than a HoopClips build issue.

Validation:

```bash
python3 -m py_compile \
  scripts/submission_readiness_preflight.py \
  scripts/test_submission_readiness_preflight.py
python3 -m unittest \
  scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_connected_ios_device_reports_unavailable_tunnel_detail \
  scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_connected_ios_device_fails_when_detected_iphone_is_unavailable \
  scripts.test_submission_readiness_preflight.SubmissionReadinessPreflightTests.test_connected_ios_device_passes_when_detected_iphone_is_available_paired \
  -v
```

- `py_compile`: passed.
- Focused device-preflight tests: 3 passed.

## Launch72 Manual Label Apply Handoff

The launch-grade accuracy flow now has an explicit handoff from the local review page downloads back into the manifest label files:

- Added `scripts/apply_team_highlight_manual_labels.py`.
- Default mode is dry-run; it only overwrites manifest label files when `--apply` is passed.
- It looks for review-page downloads named `{caseId}_manual_labels.json`, or accepts explicit `--label caseId=/path/to/file.json` mappings.
- The review page now also supports a single `Download all labels` bundle named `team_highlight_manual_labels_bundle.json`.
- The apply helper accepts that bundle with `--bundle`.
- The review page now saves a local browser draft as labels are filled and restores matching case/clip drafts on reload, so the 66-clip review is less likely to lose work before bundle download.
- It validates case ID, clip count, label IDs, prediction clip IDs, completion fields, and rejects URL/object-key fields or signed URL markers.
- It blocks incomplete labels by default so the launch report cannot be generated from partial manual review.
- This is metadata-only; it does not inspect, upload, analyze, render, compose, or export video.

Validation:

```bash
python3 -m py_compile \
  scripts/build_team_highlight_label_review_page.py \
  scripts/test_build_team_highlight_label_review_page.py \
  scripts/apply_team_highlight_manual_labels.py \
  scripts/test_apply_team_highlight_manual_labels.py
python3 -m unittest \
  scripts.test_build_team_highlight_label_review_page \
  scripts.test_apply_team_highlight_manual_labels \
  -v
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
rg -n 'X-Amz-Signature|uploadUrl|sourceObjectKey|sourceUrl|downloadUrl|presignedUrl|resultObjectKey|uploadHeaders' \
  artifacts/team_highlight_accuracy_launch71_review.html
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \
  --json
```

- `py_compile`: passed.
- Focused review/apply-helper suite: 7 tests passed.
- Regenerated Launch71 review page: 66 clip cards, bundle download code present.
- Review page local draft code present: `team-highlight-manual-label-draft-v1`, `hoopclips-team-label-draft`, restore, and clear actions.
- Review-page leak scan: no signed URLs, source/upload URLs, object keys, or upload headers found.
- Current Launch71 bundle apply dry-run: blocked because `~/Downloads/team_highlight_manual_labels_bundle.json` is not present yet.

Updated manual-label flow after reviewing all 66 clips:

```bash
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --bundle ~/Downloads/team_highlight_manual_labels_bundle.json \
  --apply \
  --json
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --label-status \
  --json
python3 scripts/build_launch_team_accuracy_report.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --eval-output artifacts/team_highlight_accuracy_launch71_eval.json \
  --report-output artifacts/team_highlight_accuracy_launch71_report.json \
  --json
python3 scripts/submission_readiness_preflight.py \
  --archive-path ios/archives/HoopsClips-Launch72.xcarchive \
  --team-accuracy-report artifacts/team_highlight_accuracy_launch71_report.json \
  --json
```

## Launch73 Review-Note Triage And Local Test Sweep

Reviewed `/Users/hanfei/Desktop/HoopClips-Review-Notes-2026-05-30_full.txt` as external review feedback, then verified against the current branch instead of applying it blindly.

Findings:

- Photos import claim is already fixed on this branch: `VideoImportTransfer.loadFileBackedVideo(from:)` uses a detached file-backed `Transferable`, `ImportedVideoFile` supports `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`, there is no `Data.self` fallback, and the temp filename uses `imported_video_\(UUID().uuidString).\(fileExtension)`.
- CloudEditService rerender payload claim did not reproduce. `CloudEditServiceTests` passed locally through the Build iOS Apps plugin, including `testLockerRerenderUsesRevisionEndpointForRevisionRows()` and `testLockerRerenderUsesBaseEndpointForBaseRows()`.
- The review note's low-confidence ContentView indentation/style item was not launch-functional and was left unchanged.
- No iOS local analysis, local rendering, local composition, or local AI edit ownership was added.

Validation commands:

```bash
Build iOS Apps plugin: test_sim HoopsClips Debug iPhone 17 Pro -only-testing:HoopsClipsTests/CloudEditServiceTests
python3 -m unittest discover -s scripts -p 'test_*.py'
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py'
PYTHONPATH=ios/backend /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py'
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
git diff --check
python3 scripts/submission_readiness_preflight.py --archive-path ios/archives/HoopsClips-Launch72.xcarchive --json
```

Results:

- `CloudEditServiceTests`: 11 tests passed.
- `scripts` unittest discovery: 126 tests passed.
- `services/editing/tests` discovery: 117 tests passed, including local render/revision/history coverage.
- `ios/backend/tests` discovery with `/tmp/hoopclips-py312-venv`: 207 tests passed.
- `services/control-plane` typecheck: passed.
- `services/control-plane` tests: 33 tests passed.
- `git diff --check`: passed.
- Full Build iOS Apps `test_sim` hit the plugin 120s timeout and the underlying `xcodebuild test-without-building` hung after `TEST BUILD SUCCEEDED`; the hung local process was stopped. Treat full iOS simulator suite as inconclusive for this pass, not as a source failure.
- Submission readiness preflight remained `28 pass / 6 fail / 0 warn`.

Remaining submission blockers from this pass:

- Missing launch-grade `--team-accuracy-report`; the 85% selected-team/highlight quality gate is still unproven until the 66 Launch71 clips are manually labeled and scored.
- Connected physical iPhone is detected but unavailable: paired, Developer Mode enabled, `tunnelState=unavailable`, `ddiServicesAvailable=false`.
- Current-checkout main CI/preflight reruns are stale for Cloud Edit Deploy Preflight, iOS Internal TestFlight Upload, and secret-gated deploy preflight.
- Installed TestFlight post-install smoke is still unproven.

## Clip156 Full-Pool GPT Review Alignment

The current launch branch had a quality mismatch: cloud analysis and `GPT_CANDIDATE_REVIEW_LIMIT` were already widened to a `60`-candidate high-recall pool, but GPT-led editing defaults still limited Free to `8` candidates and Pro/internal to `30`. That could hide late blocks, steals, defensive stops, selected-team uncertain clips, or stronger complete-context plays before GPT could judge them.

Changes:

- Free GPT clip review now defaults to `60` candidates with `3` keyframes per clip.
- Pro/internal GPT clip review now defaults to `60` candidates with `5...8` keyframes per clip.
- Free daily AI edit chances remain capped at `3`; this spends more semantic review per edit, not more free edits.
- Staging editing Cloud Build, secret-gated deploy workflow, static launch config preflight, editing README, and GPT-led editing docs now agree on the `60`-candidate GPT cap.
- No iOS local analysis, rendering, composition, export, or FFmpeg ownership was added.

Evidence doc:

- `docs/phase_clip156_full_pool_gpt_review_launch70.md`

Validation:

```bash
python3 -m py_compile services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py scripts/launch_backend_config_preflight.py scripts/test_launch_backend_config_preflight.py
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_and_pro_sampling_limits services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_free_sampling_reviews_full_analysis_pool_by_default services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_env_overrides_are_launch_bounded services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_sampling_caps_are_applied_before_openai_call -v
python3 -m unittest scripts.test_launch_backend_config_preflight -v
ruby -e 'require "yaml"; YAML.load_file("services/editing/cloudbuild.yaml"); YAML.load_file(".github/workflows/cloud-edit-deploy-preflight.yml"); puts "yaml parses"'
python3 -m unittest discover -s scripts -p 'test_*.py'
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-editing-test-venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py'
PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-py312-venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py'
python3 scripts/launch_backend_config_preflight.py --json
Build iOS Apps plugin: test_sim HoopsClips Debug iPhone 17 Pro -only-testing:HoopsClipsTests/CloudEditServiceTests
```

- Python compile: passed.
- Focused GPT reranker tests: 4 passed.
- Static backend config preflight tests: 7 passed.
- YAML parse check: passed.
- `scripts` unittest discovery: 126 passed.
- `services/editing/tests` discovery: 117 passed.
- `ios/backend/tests` discovery: 207 passed.
- Backend config preflight: 81 passed, 12 warned, 0 failed.
- Targeted `CloudEditServiceTests`: 11 passed through the Build iOS Apps plugin.

## Launch77 GPT Manual-Label Draft Helper

The Launch71 accuracy manifest still has `0 / 66` clips complete, so the 85% selected-team/highlight gate remains unproven. To reduce review time without weakening the gate, this pass added a GPT-assisted draft-label helper:

- `scripts/draft_team_highlight_manual_labels_with_gpt.py`
- `scripts/test_draft_team_highlight_manual_labels_with_gpt.py`
- Evidence doc: `docs/phase_launch77_gpt_manual_label_draft_helper.md`

The helper samples keyframes from existing candidate clip windows only, asks a vision-capable OpenAI Responses model for strict JSON draft labels, and writes a review-page-compatible label bundle. It intentionally keeps `needsLabel=true` and `humanReviewRequired=true`, so GPT cannot create launch evidence without human approval.

Validation:

```bash
python3 -m py_compile scripts/draft_team_highlight_manual_labels_with_gpt.py scripts/test_draft_team_highlight_manual_labels_with_gpt.py
python3 -m unittest scripts.test_draft_team_highlight_manual_labels_with_gpt -v
python3 scripts/draft_team_highlight_manual_labels_with_gpt.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --mock-response /tmp/hoopclips_label_draft_mock_response.json \
  --context-output /tmp/hoopclips_label_draft_context_redacted.json \
  --output /tmp/hoopclips_label_draft_bundle.json \
  --json
python3 scripts/apply_team_highlight_manual_labels.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --bundle /tmp/hoopclips_label_draft_bundle.json \
  --allow-incomplete \
  --json
rg -n 'X-Amz-Signature|uploadUrl|sourceObjectKey|sourceUrl|downloadUrl|presignedUrl|resultObjectKey|uploadHeaders|/Users/hanfei|file://|AuthKey|OPENAI|sk-' \
  /tmp/hoopclips_label_draft_context_redacted.json \
  /tmp/hoopclips_label_draft_bundle.json
```

- Python compile: passed.
- Focused draft-helper tests: 4 passed.
- Real Launch71 manifest + local video path with mock structured response: produced a 3-case, 66-clip draft bundle.
- Existing apply helper accepted the draft bundle only with `--allow-incomplete`; all 66 rows remained incomplete until human review marks them complete.
- Leak scan found no signed URLs, object keys, local file paths, API-key markers, or full presigned URLs in the redacted GPT context or draft bundle.

## Launch78 Review Page Draft Import

The review page can now import a `team-highlight-manual-label-bundle-v1` draft bundle directly, match cases/clips by ID, and prefill expected team/highlight/event/outcome fields. If the bundle is marked `humanReviewRequired=true` or comes from a draft source, imported clips stay unchecked so the reviewer must still approve every row before launch evidence can count.

Evidence doc:

- `docs/phase_launch78_review_page_draft_import.md`

Validation:

```bash
python3 -m py_compile scripts/build_team_highlight_label_review_page.py scripts/test_build_team_highlight_label_review_page.py
python3 -m unittest scripts.test_build_team_highlight_label_review_page scripts.test_draft_team_highlight_manual_labels_with_gpt -v
python3 scripts/build_team_highlight_label_review_page.py \
  --manifest artifacts/team_highlight_accuracy_launch71_manifest.json \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --output artifacts/team_highlight_accuracy_launch71_review.html \
  --json
rg -n 'Import draft bundle|importDraftBundle|applyDraftBundlePayload|bundle-import|X-Amz-Signature|uploadUrl|sourceObjectKey|sourceUrl|downloadUrl|presignedUrl|resultObjectKey|uploadHeaders' \
  artifacts/team_highlight_accuracy_launch71_review.html
```

- Python compile: passed.
- Focused review/draft helper tests: 6 passed.
- Review page regenerated for 3 Launch71 cases.
- Import controls and JS were present.
- Leak scan found no signed URL, source/upload URL, object-key, result-key, or upload-header markers.

## Launch79 Real GPT Label Draft Run

Secret Manager access was available locally, so the GPT draft helper was run against the real Launch71 66-clip manifest using the local source video. The OpenAI key was passed only through process environment variables and was not printed or written to repo files.

Evidence doc:

- `docs/phase_launch79_real_gpt_label_draft_run.md`

Results:

- Real GPT draft batches completed for all three cases:
  - `launch71_downloads_326_team_black`: 25 clips.
  - `launch71_downloads_326_team_white`: 11 clips.
  - `launch71_downloads_326_all`: 30 clips.
- Merged draft bundle: `/Users/hanfei/Downloads/team_highlight_manual_labels_bundle_draft.json`.
- The draft bundle was applied to ignored local Launch71 label templates with `--allow-incomplete --apply`.
- Regenerated `artifacts/team_highlight_accuracy_launch71_review.html`.
- Label status changed from all fields missing to only `needsLabel=false` missing:
  - 66 / 66 clips now have draft expected team, highlight, event, and outcome fields.
  - 0 / 66 clips are complete because human review is still required.
- Leak scan found no signed URL, source/upload URL, object-key, result-key, upload-header, API-key, or private-key markers in the draft bundle, regenerated review page, or applied local label templates.

## Launch103 Import, Titles, History Rename, And Local Validation

User-reported iOS fixes:

- Import state no longer stays on "Preparing video..." after the imported video has already persisted and loaded; successful load now clears the import UI and starts the real cloud team scan.
- Long imports now show honest status copy after 20 seconds and a five-minute failure guard instead of a short 90-second failure.
- Project thumbnail generation now runs off the main actor.
- App title/copy casing was normalized to `HoopClips`.
- The import hero pill changed from `Hoopclips` to `Get Exposure`.
- History rows now support tap-to-rename by tapping the project title.
- No iOS analysis, rendering, composition, export, Remotion, Canva, or GPT ownership was added.

Validation:

```bash
git diff --check
rg -n "Hoopclips" ios/HoopsClips/HoopsClips -g '*.swift'
xcodebuild test \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -destination 'platform=iOS Simulator,id=A46E2157-77ED-42CE-959D-65C068681A47' \
  -derivedDataPath /tmp/hoopclips-title-import-history-tests \
  -skipPackagePluginValidation \
  -only-testing:HoopsClipsTests/AppLanguageStoreTests
xcodebuild build \
  -project ios/HoopsClips.xcodeproj \
  -scheme HoopsClips \
  -configuration Debug \
  -destination 'id=00008130-000A001A1178001C' \
  -derivedDataPath /tmp/hoopclips-launch103-device-build \
  -allowProvisioningUpdates \
  -skipPackagePluginValidation
xcrun devicectl device install app \
  --device E5786BB6-0095-5509-8B85-110C0B5CE6D3 \
  /tmp/hoopclips-launch103-device-build/Build/Products/Debug-iphoneos/HoopsClips.app
PYTHONPATH=services/editing:ios/backend \
  /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python \
  -m unittest services.editing.tests.test_gpt_reranker services.editing.tests.test_editing_service -v
npm --prefix services/control-plane test -- test/control-plane-status-transitions.test.ts
npm --prefix services/control-plane run typecheck
```

Results:

- `git diff --check`: passed.
- Remaining `Hoopclips` Swift search: no results.
- Focused `AppLanguageStoreTests`: 3 tests passed.
- Real iPhone Debug build: passed.
- Real iPhone install: passed for bundle `atrak.charlie.hoopsclips`.
- Remote launch after install was blocked only because the iPhone was locked.
- Editing/GPT backend suite: 117 tests passed, including local render/revision/history coverage.
- Control-plane selected-team/status transitions: 33 tests passed.
- Control-plane typecheck: passed.
- A broader local `HoopsClipsTests` simulator command hung before "Testing started" and was stopped; treat it as inconclusive, not as a test failure.

Current implementation evidence checked in this pass:

- Photos import is file-backed only: `ImportedVideoFile` supports `.video`, `.movie`, `.mpeg4Movie`, and `.quickTimeMovie`; there is no `Data.self` fallback.
- Pre-analysis team choice is present: after import, cloud quick scan detects jersey-color teams, iOS shows color-labeled team options plus `All teams`, and analysis is blocked until the user confirms when teams are detected.
- Selected-team requests keep `includeUncertain=true` so uncertain plays stay reviewable.
- Free AI editing/render policy remains `3` daily renders in iOS defaults and the editing service policy.
- GPT-led editing tests cover strict structured outputs, no-full-video payloads, selected-team filtering, uncertain-review preservation, blocks/steals/defensive-stop handling, fallback behavior, and invalid patch rejection.

Remaining blockers:

- Launch-grade 85% selected-team/highlight accuracy is still unproven until the 66 Launch71 clips are human-reviewed and scored.
- Installed TestFlight post-install smoke remains unproven.
- Main-branch CI/deploy and iOS TestFlight upload proof need current successful evidence before submission.

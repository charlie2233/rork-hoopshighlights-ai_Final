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

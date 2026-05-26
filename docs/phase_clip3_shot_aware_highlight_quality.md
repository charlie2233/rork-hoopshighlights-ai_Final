# Phase Clip3: Shot-Aware Highlight Quality

Date: 2026-05-25
Branch: `codex/phase-clip3-shot-aware-highlight-quality`

## Goal

Improve GPT-led HoopClips highlight selection quality with a bias toward basketball-complete plays instead of cheap or tiny model payloads. The branch keeps the cloud-first architecture: backend CV/runtime systems create candidate clips, GPT judges only those existing candidates from compact metadata and sampled keyframes, and deterministic backend validators/renderers keep ownership of timestamps, FFmpeg, EditPlan validation, rendering, storage, and receipts.

## What Changed

- Raised quality-beta GPT sampling defaults:
  - Free: up to 8 candidate clips and 8 keyframes per clip.
  - Pro/internal: up to 30 candidate clips and 8 keyframes per clip.
  - Default sampled frame width is 768, JPEG quality is 4, max frame bytes is 300000, OpenAI image detail defaults to `high`, and structured output budget defaults to 3500 tokens.
- Added shot-aware keyframe roles beyond start/eventCenter/finish:
  - `preEvent`
  - `release`
  - `outcome`
  - `rim`
  - `midAction`
- Added candidate quality filters before GPT:
  - reject clips shorter than the backend minimum
  - reject clips whose event center is too close to clip start
  - reject clips without enough follow-through after the event center
- Tightened shot-like candidate context before GPT:
  - shot-like clips must be at least 3.0 seconds
  - shot-like clips need at least 1.2 seconds of lead-in and 0.75 seconds of follow-through before they are sampled for GPT
  - compact `qualityHints` now identify shot-like candidates and expose the stricter timing-window expectations
- Added an ordinary/non-GPT selector guard so shot-like clips also need minimum setup and follow-through context when GPT is disabled or falls back.
- Ranked deterministic backend candidates by plan eligibility and shot-context quality before raw planning/watchability/excitement scores, so a complete play beats a tiny or late pre-basket window even when the thin clip has a higher model score.
- Added an 85% template-minimum guard during EditPlan creation and validation, preventing tiny render slices while preserving near-minimum valid clips used by longer recap/revision templates.
- Added a shot-keyframe completeness gate before the GPT call. With quality-beta sampling, shot-like candidates must have setup, release, outcome, and rim keyframes extracted successfully before they can be sent to GPT.
- The GPT path now drops only the shot candidates missing those richer context frames and continues with remaining complete candidates instead of falling all the way back when at least one usable candidate remains.
- Made duplicate-group selection quality-aware so a higher-scored late/pre-basket duplicate cannot hide the lower-scored full-context duplicate that should actually render.
- Preserved cloud-owned event centers through analysis, provider adapters, iOS cloud analysis decoding, clip persistence, and cloud edit requests so GPT keyframes sample around the actual shot/peak instead of the clip midpoint.
- Expanded tight or offset shot-like provider windows around provider `eventCenter`/`eventTime`/`peakTime`/`shotTime` with setup and follow-through context before iOS ever sees the candidate.
- Made iOS normalization event-center aware: overlong cloud clips with a known event center now create an event-centered segment instead of arbitrary early chunks, and invalid event centers are clamped inside the normalized clip bounds before cloud edit handoff.
- Ranked iOS-to-cloud edit candidate handoff by cloud analysis quality before the 30-clip API cap, then restored chronological order in the payload. This keeps later high-value plays in GPT's candidate pool and demotes shot-like clips that start too close to the event.
- Added `qualityHints` to the compact GPT payload so the model sees timing-window expectations without receiving full video.
- Added strict GPT `qualitySignals` output:
  - `setupVisible`
  - `eventVisible`
  - `outcomeVisible`
  - `ballPathVisible`
  - `playerControlVisible`
  - `cleanCamera`
  - `fullPlayContext`
  - `reason`
- Added backend rejection of GPT-kept clips that still fail shot quality:
  - tiny clips
  - pre-basket-only shot windows
  - low highlight/watchability scores
  - unclear or non-basketball outcomes
  - missing event/outcome/clean camera
  - missing setup/full play context
  - made shots without visible ball path
  - made/missed shots without visible player control
- Updated Cloud Run staging substitutions and config preflight expectations to match the higher-quality defaults while keeping GPT launch switches disabled by default.

## Safety Rules Preserved

- GPT receives only sampled JPEG keyframes from existing candidate windows and compact metadata.
- GPT does not receive full source videos, presigned URLs, R2 credentials, storage keys, or source object keys.
- GPT cannot generate FFmpeg commands or renderer commands.
- GPT cannot invent clip IDs or exact timestamps.
- GPT is not asked to judge made-shot quality from only generic start/event/finish frames when richer shot-context roles are configured.
- Backend validators still produce and repair deterministic `EditPlan` JSON before rendering.
- iOS remains a control surface for upload, status, preview, download, share, and user commands. The only iOS-side addition is preserving and forwarding non-secret cloud clip metadata (`eventCenter`) into the cloud edit request.

## Cost Notes

Cost is deliberately not the main constraint for this phase. The defaults spend more on visual context to improve clipping quality:

- more keyframes per candidate
- larger frames
- high image detail
- more Pro/internal candidates
- larger structured-output budget

The knobs remain configurable through environment variables and kill switches:

- `HOOPS_AI_CLIP_GPT_EDITOR_ENABLED`
- `HOOPS_AI_CLIP_GPT_KEYFRAMES_PER_CLIP`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_FREE`
- `HOOPS_AI_CLIP_GPT_MAX_CANDIDATES_PRO`
- `HOOPS_GPT_HIGHLIGHT_RERANK_FRAME_WIDTH`
- `HOOPS_GPT_HIGHLIGHT_RERANK_JPEG_QUALITY`
- `HOOPS_GPT_HIGHLIGHT_RERANK_MAX_IMAGE_BYTES`
- `HOOPS_GPT_HIGHLIGHT_RERANK_IMAGE_DETAIL`
- `HOOPS_GPT_HIGHLIGHT_RERANK_MAX_OUTPUT_TOKENS`

## Validation

Commands run:

```sh
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py scripts/launch_backend_config_preflight.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py
python3 -m py_compile ios/backend/app/models.py ios/backend/app/classifier.py ios/backend/app/external_providers.py ios/backend/scripts/run_hoopcut_adapter.py ios/backend/tests/test_external_providers.py
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_external_providers -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/launch_backend_config_preflight.py
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath build/XcodeDerivedDataBuildForTestingAfterEventCenter -resultBundlePath build/HoopsClipsBuildForTestingAfterEventCenter.xcresult -skipPackagePluginValidation -skipMacroValidation build-for-testing -quiet
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath build/XcodeDerivedDataBuildForTestingAfterEventCenter -resultBundlePath build/HoopsClipsTestsAfterEventCenter.xcresult -skipPackagePluginValidation -skipMacroValidation test-without-building -quiet
```

Results:

- Python compile: passed.
- External provider focused suite: 3 tests passed, including tight shot-window expansion around provider event center.
- GPT reranker + edit-plan focused suite: 54 tests passed.
- Editing service focused suite: 37 tests passed, including local FFmpeg render/revision/download-history paths.
- iOS backend Python discovery: 48 tests passed.
- Services editing discovery: 57 tests passed.
- Scripts discovery: 34 tests passed.
- Launch backend config preflight: `pass=63 warn=12 fail=0`.
- iOS Debug `build-for-testing`: passed on iPhone 17 Pro simulator, iOS 26.0.1. Remaining warnings are the existing Swift concurrency/deprecation backlog outside the event-center handoff.
- iOS simulator tests: passed on iPhone 17 Pro simulator, iOS 26.0.1. Xcode result summary: `74` total tests, `71` passed, `3` skipped, `0` failed.
- Added iOS regression coverage for event-centered overlong cloud clip normalization and event-center bounds clamping.
- Added iOS regression coverage for candidate handoff ranking so a later high-quality clip is not dropped by the 30-clip cap and a complete shot outranks a higher-scored pre-basket-only window.
- Cleaned up Xcode 26 actor-isolation warnings in the no-secret codecheck path by marking analysis/test-only Codable helpers with explicit isolation where needed.

Additional validation after commit `1aad21d`:

```sh
python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/tests/test_gpt_reranker.py ios/backend/tests/test_edit_plan_agent.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker ios.backend.tests.test_edit_plan_agent -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service -v
git diff --check
xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath build/XcodeDerivedDataGenericCodecheck2 -resultBundlePath build/HoopsClipsGenericCodecheck2.xcresult CODE_SIGNING_ALLOWED=NO -skipPackagePluginValidation -skipMacroValidation -quiet
```

Results:

- Python compile: passed.
- GPT reranker + edit-plan focused suite: 57 tests passed.
- Editing service focused suite: 37 tests passed.
- `git diff --check`: passed.
- Generic iOS Debug `build-for-testing`: passed with signing disabled. The previous Xcode 26.4 Codable/test actor-isolation warnings for `AnalysisSettings`, `CreateCloudEditJobRequest`, `CloudEditVersionResponse`, and `CloudEditRenderStatusResponse` were no longer emitted. Remaining warnings are the existing `CloudAnalysisService` no-async-await and `VideoExportService` deprecation/Sendable backlog.
- Full iOS simulator `xcodebuild test` was started against the iPhone 17 Pro simulator for this pass, but it had not produced a readable result bundle after more than eight minutes. Treat the generic no-signing build-for-testing plus existing 74-test simulator pass above as the current iOS evidence until the simulator test runner is stable.

PR #10 CI after commit `0177890846230ccef9570e30349b09e7fb77096f`:

- Merge state: `CLEAN`.
- Cloud Edit Deploy Preflight run `26431727456`:
  - Worker typecheck and dry run: success, job `77806149088`.
  - Editing backend Python tests: success, job `77806149099`.
  - Verify cloud edit deploy secrets: skipped on this PR path, job `77806384152`.
- iOS Internal TestFlight Upload run `26431727445`:
  - No-secret internal staging codecheck: success, job `77806149212`.
  - Build internal staging TestFlight archive: skipped on this PR path, job `77806159114`.

## Launch Recommendations

- Deploy this branch to staging only after the Cloudflare/GCP deploy secret blockers are cleared.
- Run a live cloud smoke using a real basketball sample with GPT enabled:
  - upload/import
  - cloud analysis candidate generation
  - GPT rerank with keyframes
  - Review
  - Export AI Edit
  - render
  - preview
  - More Hype revision
  - revised render
  - download/share
- Inspect the AI Work Receipt for sampled clip/frame counts, GPT applied/fallback status, rejected tiny/pre-basket candidates, and selected clip order.
- Keep production rollout gated until staging proves live render reliability, privacy/log redaction, provider config, and installed TestFlight smoke.

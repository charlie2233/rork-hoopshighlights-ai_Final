# Phase Clip141: GPT Revision Proof Surface

Date: 2026-05-29
Branch: `codex/phase-clip141-gpt-revision-proof`

## Goal

Make GPT-led revision planning provable during the internal TestFlight smoke. Commands such as More Hype, NBA Style, and Shorter can already request a GPT `EditPlanPatch`, but a failed or disabled GPT patch fell back to deterministic revision behavior without a clear client-visible receipt. This phase adds explicit revision-planner metadata without changing the deterministic renderer or allowing GPT to bypass validation.

## Architecture

- Cloud editing service still owns GPT revision planning, EditPlan patch validation, repair, rendering, and storage.
- iOS remains a control surface. It displays the revision planner status and sends revision/render requests only.
- GPT still returns `EditPlanPatch` JSON only. It cannot output FFmpeg commands, URLs, storage keys, or raw renderer instructions.
- The backend validates and repairs every GPT patch before it can become the revised plan.

## Response Fields

`EditRevisionResponse` now includes:

- `revisionPlanner`: `gpt_patch` or `deterministic_patch`
- `gptRevisionPatchApplied`: whether the returned revised plan came from a validated GPT patch
- `gptRevisionPatchStatus`: `not_requested`, `disabled`, `fallback`, `applied`, or `rejected`
- `gptRevisionPatchFallbackReason`: safe non-secret fallback reason such as `missing_api_key`, `patch_validation_failed`, or `feature_flag_disabled`

These fields are mirrored in the iOS model and the control-plane TypeScript type. The iOS revision card shows a factual status line, for example GPT patch applied, deterministic patch, or GPT fallback reason.

## Safety

- No secrets, presigned URLs, object keys, or model payloads are exposed.
- Existing patch validation still rejects unsupported paths, unsafe render/storage strings, opponent clips for selected-team edits, and invalid plan bounds.
- If GPT patch generation is disabled, unconfigured, unavailable, invalid, or rejected, the service records the fallback reason and uses the deterministic patch path.

## Validation

Focused commands run:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py services/editing/editing_app/main.py services/editing/tests/test_editing_service.py services/editing/tests/test_gpt_reranker.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_revise_edit_job_returns_patch_and_revised_plan services.editing.tests.test_editing_service.EditingServiceTests.test_revise_edit_job_surfaces_gpt_patch_planner_when_applied services.editing.tests.test_editing_service.EditingServiceTests.test_revise_edit_job_surfaces_gpt_patch_fallback_reason
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_revision_patch_request_rejects_opponent_clip_for_selected_team services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_revision_patch_request_rejects_unsafe_gpt_output services.editing.tests.test_gpt_reranker.GPTHighlightRerankerTests.test_revision_patch_attempt_reports_disabled_and_missing_key_reasons
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests
(cd services/control-plane && npm test -- --test-reporter=spec)
(cd services/control-plane && npm run typecheck)
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip141-dd CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment build
xcodebuild -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-clip141-bft-dd CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment build-for-testing
git diff --check
python3 scripts/submission_readiness_preflight.py --json
```

Results:

- Python compile passed.
- Editing service focused revision tests passed: 3 tests.
- GPT reranker focused revision tests passed: 3 tests.
- Full `services/editing/tests` suite passed: 114 tests.
- Full `ios/backend/tests` suite passed: 198 tests.
- Control-plane tests passed: 28 tests.
- Control-plane typecheck passed.
- iOS Debug simulator build passed with code signing disabled.
- iOS Debug `build-for-testing` passed with code signing disabled.
- `git diff --check` passed.
- Build iOS Apps MCP `build_run_sim` reached build setup but failed to boot the simulator with `NSPOSIXErrorDomain Code=22`; the shell `xcodebuild` build and build-for-testing commands above succeeded afterward.

Submission readiness preflight result:

- Status: failed.
- Summary: 22 pass, 1 warn, 11 fail.
- Passing checks included backend/config preflight, bundle id/version/build/signing config, TestFlight export options, upload artifact, cloud deploy input names, latest main-branch deploy/upload workflow checks, submission automation, and iOS upload input names.
- Failing or unproven checks: current branch has uncommitted tracked/untracked changes before this phase commit, missing launch-grade team accuracy report, connected iPhone unavailable, staging Worker `/v1/editing/version` returned 404, direct editing service missing live GPT/render feature flag exposure, direct editing service git SHA is stale, secret-gated deploy preflight must be rerun for the current checkout, and existing launch docs still mark post-install smoke, Worker version route, Cloudflare credential proof, and live kill-switch proof as incomplete.

## Launch Notes

During the post-install TestFlight smoke, verify the revision response after More Hype or NBA Style:

1. If `gptRevisionPatchApplied=true`, GPT Edit Cool created the validated patch.
2. If `revisionPlanner=deterministic_patch`, inspect `gptRevisionPatchStatus` and `gptRevisionPatchFallbackReason`.
3. Continue to render the revised plan through the cloud renderer and verify preview, download, share/open-in, and log redaction.

Current launch blockers remain Cloudflare `CLOUDFLARE_API_TOKEN` proof/deploy, live Worker `/v1/editing/version`, connected iPhone availability for post-install TestFlight smoke, launch-grade team accuracy evidence, stale direct editing deploy, and live kill-switch proof through the Worker.

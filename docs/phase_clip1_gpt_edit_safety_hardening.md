# Phase Clip1 GPT Edit Safety Hardening

Date: 2026-05-23
Branch: `codex/phase-clip1-gpt-edit-safety-hardening`

## Scope

This branch tightens backend validation for GPT-authored `EditPlanPatch` JSON. It does not add iOS video analysis, local rendering, local composition, local export, Remotion, Canva, or any new renderer behavior.

Cloud remains responsible for GPT editing, deterministic `EditPlan` validation, rendering, storage, and policy. iOS remains the status, preview, download, share, and revision-control surface.

## Change

`apply_edit_plan_patch` now rejects GPT patch content that attempts to include:

- FFmpeg/FFprobe or shell-style command text.
- AVFoundation, local-render, on-device edit/render/export instructions.
- Direct URLs, `file://`, `data:video`, or cloud-storage URL schemes.
- Presigned URL markers.
- Storage-key fields such as `downloadUrl`, `sourceObjectKey`, `outputObjectKey`, and `renderLogObjectKey`.
- R2 credential-looking text.
- Storage-key-like paths under `uploads/`, `renders/`, or `render_logs/`.

The scanner checks nested dict keys and values so GPT cannot hide storage metadata in object keys.

## Tests

Added `test_gpt_patch_validator_rejects_local_render_urls_and_storage_keys` in `ios/backend/tests/test_edit_plan_agent.py`.

Covered cases:

- Local render instruction: `render locally with AVFoundation`.
- Shell/tool command variants: `bash`, `python -c`, `os.system`, and `curl`.
- Direct/presigned-looking HTTPS MP4 URL.
- Source object key path.
- Presigned S3/R2 marker such as `X-Amz-Signature`.
- Bare `downloadUrl`.
- Nested `renderLogObjectKey` and `renders/...` storage path.
- Nested object key named `downloadUrl`.
- Unsafe GPT revision output returning through `request_gpt_edit_plan_patch` falls back to `None`.

## Validation

- `git diff --check` passed.
- `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py` passed.
- Focused GPT patch safety tests passed:
  - `test_gpt_patch_validator_rejects_ffmpeg_commands`
  - `test_gpt_patch_validator_rejects_local_render_urls_and_storage_keys`
  - `test_revision_commands_are_deterministic_patches`
  - `test_revision_patch_request_rejects_unsafe_gpt_output`
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover ios/backend/tests -v` passed: `39` tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v` passed: `47` tests.
- `npm test -- --test-reporter=spec` passed in `services/control-plane`: `20` tests.
- `npm run typecheck` passed in `services/control-plane`.
- `python3 -m unittest scripts.test_submission_readiness_preflight scripts.test_launch_backend_config_preflight -v` passed: `9` tests.
- `bash ios/scripts/verify_internal_staging_config.sh` passed.
- Build iOS Apps simulator Debug build passed.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -configuration Debug -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -derivedDataPath /tmp/hoopclips-ux3-cookbook-mcp-dd CODE_SIGNING_ALLOWED=NO -hideShellScriptEnvironment` passed.
- `python3 scripts/submission_readiness_preflight.py` remained **NO-GO** as expected before commit: `pass=16 warn=1 fail=10`.

## Launch Notes

This hardening supports the launch invariant that GPT may guide editing but cannot generate renderer commands, local-render instructions, presigned URLs, or storage internals. Backend repair and deterministic validation still run before any render.

Submission remains **NO-GO** until signing/upload credentials, staging deploy proof, Worker `/v1/editing/version`, signed archive/IPA, and installed TestFlight smoke are proven.

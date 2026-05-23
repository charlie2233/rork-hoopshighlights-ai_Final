# Phase UX5 AI Edit User Prompt

## Goal

Add an optional Export AI Edit text box so users can give the cloud editor creative direction without moving planning, rendering, or validation into iOS.

## Architecture

- iOS collects a short `userPrompt` and sends it with `CreateEditJobRequest`.
- The control plane treats `userPrompt` as ordinary JSON request metadata and forwards it to the editing service.
- The editing service owns validation, sanitization, GPT context construction, edit planning, patching, and rendering.
- GPT receives only a deterministic `userEditIntent` derived from the prompt alongside template cookbook rules and existing candidate clip metadata.
- The prompt cannot include URLs, presigned URL markers, or storage-key field names.

## Safety Rules

- The prompt never gives GPT permission to invent clips, exact timestamps, FFmpeg commands, shell commands, storage paths, or render instructions.
- GPT can only use the structured intent when compatible with template rules, plan-tier policy, candidate clips, and backend validators.
- If GPT is disabled or unavailable, existing deterministic fallback behavior still works.

## Validation

- iOS request model includes optional `userPrompt`.
- Backend request model trims whitespace, clamps length through schema, and rejects URL/storage markers.
- GPT reranker payload includes structured `userEditIntent` without raw prompt text, source video, presigned URLs, or storage keys.

## Evidence

- `npm --prefix services/control-plane test` - 20/20 tests passed.
- `npm --prefix services/control-plane run typecheck` - passed.
- `PYTHONPATH=ios/backend:services/editing /tmp/hoopclips-ios-backend-venv/bin/python -m unittest ios.backend.tests.test_edit_plan_agent services.editing.tests.test_gpt_reranker` - 39 tests passed.
- `xcodebuild test -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -only-testing:HoopsClipsTests/HoopsClipsTests -skipPackagePluginValidation` - `** TEST SUCCEEDED **`.
- Build iOS Apps MCP `build_sim` for `HoopsClips` Debug on iPhone 17 Pro simulator - succeeded; existing Swift 6/deprecation warnings remain in video analysis/export services.
- `xcodebuild build-for-testing -project ios/HoopsClips.xcodeproj -scheme HoopsClips -destination 'platform=iOS Simulator,id=7ECBD8FA-B0A2-4C3B-9A5C-EB73D19B99F2' -skipPackagePluginValidation` - `** TEST BUILD SUCCEEDED **`.
- `python3 -m py_compile ios/backend/app/editing.py services/editing/editing_app/gpt_reranker.py` - passed.
- `git diff --check` - passed.
- Secret/storage grep across touched files found only expected schema fields and fixture strings; no real credentials or full presigned URLs.

# Phase Launch67 Editing Analyze Fallback

Date: 2026-05-30
Branch: `codex/phase-launch67-editing-analyze-fallback`
Base: `main` at `d2f2461`

## Scope

Unblock real selected-team cloud analysis after the staging Worker accepts an upload and queues analysis. A real accuracy collection attempt reached the queue but failed before clips were produced:

- jobId: `22757c17e22a4c37bb1f9f8b52017e57`
- stage: `External inference dispatch failed`
- failureReason: `External inference dispatch failed with status 404.`

The Worker already falls back from legacy inference to the editing provider for `/v1/analyze` compatibility statuses. The deployed editing service had `/v1/team-scan`, but not `/v1/analyze`, so full analysis fallback could still end in a 404.

## Changes

- Added `POST /v1/analyze` to `services/editing`.
- The endpoint accepts the existing Worker `InferenceDispatchRequest`.
- The endpoint materializes the remote source in cloud service storage, runs the existing cloud analysis pipeline, and posts the existing inference callback contract.
- The callback payload omits `sourceUrl`, `sourceObjectKey`, raw storage keys, and full presigned URLs.
- Added a regression test proving Worker-style dispatch is accepted and callback payloads stay storage-safe.

## Architecture

- Cloud backend still owns analysis, team attribution, GPT-assisted selection inputs, callbacks, and storage.
- iOS behavior is unchanged.
- GPT does not replace deterministic timestamp/CV/FFmpeg logic.
- No FFmpeg commands are accepted from GPT or the client.

## Evidence

Commands run:

```bash
python3 -m py_compile services/editing/editing_app/main.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_analyze_endpoint_accepts_worker_dispatch_and_posts_callback services.editing.tests.test_editing_service.EditingServiceTests.test_team_scan_endpoint_uses_editing_secret_and_redacts_source_details -v
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v
npm --prefix services/control-plane ci
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test -- --test-name-pattern 'falls back to editing analysis|team scan provider|selected team'
git diff --check
```

Results:

- Python compile passed.
- Focused editing tests passed: 2 tests.
- Full editing-service tests passed: 116 tests.
- Control-plane typecheck passed.
- Focused control-plane tests passed: 30 tests.
- Diff whitespace check passed.

## Launch Notes

This code must be deployed before rerunning the real accuracy collection. After deploy, rerun:

```bash
python3 scripts/collect_team_highlight_accuracy_case.py --video-path /Users/hanfei/Downloads/326_1770329282.mp4 --case-id launch67_downloads_326_team --video-id downloads_326_1770329282 --team-mode team --duration-seconds 30 --output-dir artifacts/team_highlight_accuracy_launch67 --manifest artifacts/team_highlight_accuracy_launch67_manifest.json --poll-interval-seconds 5 --timeout-seconds 900
```

If that completes, fill the generated manual label template from human review before building a launch-grade accuracy report.

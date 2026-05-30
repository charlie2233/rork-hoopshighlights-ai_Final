# Phase Launch56: Team Scan Provider Fallback

## Goal

Unblock selected-team launch smoke by making `/jobs/{jobId}/team-scan` resilient when the primary inference provider returns `unavailable`. The Worker still owns only orchestration; cloud services still own video materialization, quick scan, GPT-assisted jersey/team attribution, analysis, rendering, and storage.

## Root Cause Evidence

- Live staging selected-team collection failed before this branch because team scan returned no selectable teams.
- Failed staging job: `ced2f2c062304a65bfba078a19b2d92f`.
- Request ID: `3457fcbf-f394-4a42-bc48-223ff7d51447`.
- Upload trace ID: `910e9e95997848f9a8a26f5ab879d152`.
- Worker response was sanitized: `status=unavailable`, `detectedTeams=[]`, no presigned URL or R2 credential output.

## Changes

- Added a Worker team-scan provider chain:
  - primary: `INFERENCE_BASE_URL` with `INFERENCE_SHARED_SECRET`.
  - fallback: `EDITING_BASE_URL` with `EDITING_SHARED_SECRET`.
- Added `/v1/team-scan` to the editing Cloud Run service so the fallback can materialize the uploaded source from a presigned read URL, run the existing backend candidate generation + team quick scan, and return only detected team options.
- Added deploy secret mapping for `HOOPS_INTERNAL_PROCESS_SECRET` from the existing `HOOPS_EDITING_SERVICE_SECRET` secret so reused backend quick-scan settings validate in staging.
- Preserved redaction rules: no full presigned URLs, R2 object keys, or secret values in public responses/events.

## Validation

- `npm --prefix services/control-plane run typecheck` passed.
- `npm --prefix services/control-plane test` passed: 29 tests.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile services/editing/editing_app/main.py services/editing/tests/test_editing_service.py` passed.
- `PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v` passed: 115 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v` passed: 112 tests.
- `python3 -m unittest scripts.test_main_workflow_codecheck_triggers scripts.test_launch_backend_config_preflight -v` passed: 11 tests.
- `git diff --check` passed.

## Device Evidence

- Wired iPhone detected HoopClips build `5` installed after the user updated.
- Build 5 was launched on device with `xcrun devicectl device process launch`.

## Follow-Up

- Deploy this branch to staging once pushed.
- Rerun selected-team collection on the real sample video and build the launch team accuracy report.
- Continue installed-device smoke: import/upload, selected team, cloud analysis, Review, Export, AI Edit render, preview, revision, share/open-in.

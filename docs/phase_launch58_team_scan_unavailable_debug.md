# Phase Launch58 - Team Scan Unavailable Debug

## Goal

Unblock selected-team TestFlight smoke after the Worker reached the editing-service team-scan fallback but still returned `status=unavailable` with no selectable teams.

## Root Cause

Live staging smoke reproduced the failure:

```bash
python3 scripts/worker_team_scan_smoke.py \
  --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --duration-seconds 30 \
  --allow-unavailable
```

Result:

- `jobId=4ccd12206c3745dabb0828c28622ebb5`
- `teamScanStatus=unavailable`
- `detectedTeamCount=0`

Cloud Run logs showed the fallback provider was reached, but FastAPI rejected the request before handler logic:

- service: `hoopclips-editing-staging`
- revision: `hoopclips-editing-staging-00027-5kh`
- request: `POST /v1/team-scan`
- status: `422 Unprocessable Entity`

The Worker sends tracing/schema fields (`requestId`, `uploadTraceId`, `traceId`, `schemaVersion`, `modelVersion`) in `InferenceTeamScanRequest`. The backend request model used by `/v1/team-scan` forbids unknown fields, so the editing service rejected the Worker contract before materializing the video or running quick scan.

## Fix

- Extended `ScanCloudAnalysisSourceRequest` to accept the Worker tracing/schema metadata fields.
- Added the Worker metadata fields to the editing service team-scan endpoint regression test.
- Tightened the control-plane fallback test to assert those metadata fields are part of the provider request.

## Validation

Commands run locally:

```bash
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m py_compile ios/backend/app/models.py services/editing/tests/test_editing_service.py
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest services.editing.tests.test_editing_service.EditingServiceTests.test_team_scan_endpoint_uses_editing_secret_and_redacts_source_details -v
npm --prefix services/control-plane test -- --test-name-pattern 'falls back to editing team scan provider'
PYTHONPATH=ios/backend:services/editing /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s services/editing/tests -p 'test_*.py' -v
npm --prefix services/control-plane run typecheck
npm --prefix services/control-plane test
python3 -m unittest scripts.test_main_workflow_codecheck_triggers scripts.test_launch_backend_config_preflight -v
git diff --check
```

Results:

- Python compile passed.
- Editing service team-scan endpoint test passed.
- Control-plane fallback test command passed; the filtered Node test run reported 29 passing tests.
- Full editing service suite passed: 115 tests.
- Control-plane typecheck passed.
- Full control-plane suite passed: 29 tests.
- Launch workflow/config script tests passed: 11 tests.
- `git diff --check` passed.

## Deploy And Staging Proof

Deployed the fixed editing service image directly through Google Cloud Build to avoid spending an extra GitHub Actions deploy run:

```bash
gcloud builds submit \
  --config services/editing/cloudbuild.yaml \
  --substitutions _IMAGE_TAG=5a6cd281dede0e33aeea208c947145133002313f .
```

Result:

- Cloud Build ID: `23de68b3-c3f5-4f17-922f-56a3649999dc`
- status: `SUCCESS`
- image tag: `5a6cd281dede0e33aeea208c947145133002313f`
- Cloud Run revision: `hoopclips-editing-staging-00028-tw7`
- traffic: 100 percent to the new revision

Version probe:

```bash
python3 scripts/staging_version_probe.py \
  --expected-git-sha 5a6cd281dede0e33aeea208c947145133002313f \
  --json
```

Result:

- `status=pass`
- Worker git SHA: `5a6cd281dede0e33aeea208c947145133002313f`
- editing git SHA: `5a6cd281dede0e33aeea208c947145133002313f`

Post-deploy live team scan smoke:

```bash
python3 scripts/worker_team_scan_smoke.py \
  --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --duration-seconds 30 \
  --allow-unavailable
```

Result:

- `jobId=d9eeae0cbb224ee893165b880aef11cc`
- `teamScanStatus=scanned`
- `detectedTeamCount=2`
- detected teams: black jersey team, white jersey team

Selected-team start smoke:

```bash
python3 scripts/worker_team_scan_smoke.py \
  --worker-url https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev \
  --video-path /Users/hanfei/Downloads/326_1770329282.mp4 \
  --duration-seconds 30 \
  --start-selected-team
```

Result:

- `jobId=569827cae0ab4d5eb11daaf7dc986032`
- `teamScanStatus=scanned`
- `detectedTeamCount=2`
- selected team handoff: `mode=team`, `teamId=team_black`, `colorLabel=black`, `status=queued`

## Launch Notes

- No secrets, R2 credentials, object keys, or full presigned URLs are included in this evidence.
- This fixes the 422 contract blocker. Staging now returns selectable teams for the sample video and can queue selected-team analysis.

# Phase Clip65: Worker Team Scan Provider

## Goal

Make the production Worker team-scan route call a real cloud-owned scan provider instead of only failing closed. This keeps iOS as the upload/control surface while allowing users to import a video, run a quick jersey-color scan, choose a team or all teams, and then start analysis with backend-enforced policy.

## Change

- Added backend `POST /v1/team-scan` for scan-only provider requests from the Worker.
- The scan-only backend endpoint accepts a Worker-generated source URL, downloads the source inside the cloud backend, extracts candidate clips/keyframes, runs Team Quick Scan, and returns strict `detectedTeams`.
- The endpoint requires the internal/inference shared secret when configured.
- The Worker `POST /v1/analysis/jobs/{jobId}/team-scan` now:
  - verifies upload ownership and source existence,
  - creates a short-lived read URL for the uploaded source,
  - calls `INFERENCE_BASE_URL/v1/team-scan` with `x-hoops-inference-secret`,
  - persists only normalized `detectedTeams` and `teamScanStatus`,
  - never logs full source URLs or credentials,
  - returns `unavailable` if the provider fails or returns no teams.
- Selected-team starts still require scan-backed `teamId` or `colorLabel` before queue dispatch.
- `all` teams mode still starts without a scan.

## Architecture

- Cloud backend owns scan, attribution, candidate generation, GPT selection, edit planning, rendering, storage, and policy.
- iOS only uploads/imports, displays scan choices, sends selected team/all-teams intent, reviews clips, and controls export/share.
- GPT can assist team attribution and clip selection through sampled frames; full videos are not sent to GPT.
- FFmpeg/CV/timestamp logic stays deterministic and backend-owned.

## Quality Impact

- Selected-team mode is now viable through the Worker path once `INFERENCE_BASE_URL` points to a backend with `/v1/team-scan`.
- The scan provider uses the same action-anchored candidate pool and defensive/offensive frame roles already tested for blocks, steals, shot setup, and rim-result context.
- If the model is unsure, the selected-team pipeline still keeps uncertain-attribution clips for user review instead of silently dropping them.

## Validation

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `npm --prefix services/control-plane run typecheck`
  - Passed.
- `npm --prefix services/control-plane exec -- tsx --test services/control-plane/test/control-plane-status-transitions.test.ts`
  - Passed: 7 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_scan_source_endpoint_uses_presigned_source_url_without_job_store ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_scan_source_endpoint_requires_internal_secret_when_configured ios.backend.tests.test_team_quick_scan.TeamQuickScanTests.test_team_scan_endpoint_runs_before_start_and_start_accepts_selection -v`
  - Passed: 3 tests.
- `npm --prefix services/control-plane test`
  - Passed: 26 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v`
  - Passed: 153 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Passed: 93 tests.
- `python3 -m unittest discover -s scripts -p 'test_*.py' -v`
  - Passed: 46 tests.
- `git diff --check`
  - Passed.

## Launch Recommendation

Set Worker `INFERENCE_BASE_URL` to the Cloud Run inference/backend service that includes `/v1/team-scan`, and set Worker `INFERENCE_SHARED_SECRET` to match that service's internal secret. Then run a live staging team-scan smoke with a real uploaded MP4 before claiming selected-team TestFlight readiness. The 85% target still requires labeled footage evaluation across team ownership, made/missed shot outcome, blocks, steals, and uncertain-review cases.

## CI Evidence

After commit `97a3a2d5199c6d328cba35206b0ff2038233802a`, GitHub Actions created these PR runs:

- `Cloud Edit Deploy Preflight` run `26504643215`
  - Failed before any workflow steps were allocated.
  - Failed jobs: `Worker typecheck and dry run`, `Editing backend Python tests`.
  - GitHub annotation: `The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings`.
  - `Verify cloud edit deploy secrets` was skipped because prerequisite jobs did not start.
- `iOS Internal TestFlight Upload` run `26504643094`
  - Failed before any workflow steps were allocated.
  - Failed job: `No-secret internal staging codecheck`.
  - GitHub annotation: `The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings`.
  - `Build internal staging TestFlight archive` was skipped because this was a pull request codecheck run and the codecheck job did not start.

No failed-step logs were available because GitHub did not allocate runners.

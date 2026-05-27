# Phase Clip64: Control-Plane Team Scan Gate

## Goal

Make the production Cloudflare control-plane honor the same scan-backed selected-team contract as the Python backend. Users should choose a team before selected-team analysis, and the backend must only queue that mode when the chosen jersey-color team came from cloud-owned scan evidence.

## Change

- Added control-plane job fields for `detectedTeams` and `teamScanStatus`.
- Added `POST /v1/analysis/jobs/{jobId}/team-scan` routing in the Worker.
- Selected-team starts now require scan-backed teams before queue dispatch.
- A selected `teamId` or `colorLabel` must match a scanned option.
- Missing scan evidence returns `team_scan_required`.
- Mismatched selected team returns `team_selection_unavailable`.
- `teamSelection.mode = "all"` still queues without scan.
- All-team analysis now also expands the analysis candidate pool before Review trimming, improving recall when the user wants both teams.
- Small Review caps now reserve up to two defensive families when possible, so blocks and steals have a better chance to survive scoring-heavy trims.

## Architecture Notes

- Cloud remains the owner of team scan, selection validation, analysis, GPT review, edit planning, rendering, and storage.
- iOS remains the control surface: upload/import, request scan, show team choices, start analysis, review clips, export, preview, download, and share.
- The Worker route does not trust client-supplied team detections in staging/prod. Local tests can seed detections through the harness, but production must use cloud-owned scan output.
- Until the Worker route is connected to a live cloud scan provider, staging/prod Worker calls without provider output return `unavailable`; selected-team start then fails closed instead of pretending the scan happened.

## Quality Impact

- Selected-team precision improves because a skipped or stale team picker cannot queue selected-team analysis.
- Recall improves because all-team and selected-team modes both use the wider prefilter pool before visible Review clipping.
- Blocks and steals are protected as first-class highlight families rather than being crowded out by made shots.
- Uncertain team-attribution clips remain available for user review after a real selected-team scan, matching the internal beta goal of not hiding plausible clips when confidence is below the target.

## Validation

Commands run on branch `codex/phase-clip28-cloud-team-quick-scan`:

- `npm --prefix services/control-plane run typecheck`
  - Passed.
- `npm --prefix services/control-plane test`
  - Passed: 25 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_pipeline_quality -v`
  - Passed: 38 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest ios.backend.tests.test_team_quick_scan -v`
  - Passed: 19 tests.
- `PYTHONPATH=ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover -s ios/backend/tests -p 'test_*.py' -v`
  - Passed: 151 tests.
- `PYTHONPATH=services/editing:ios/backend /Users/hanfei/rork-hoopshighlights-ai_Final/ios/backend/.venv/bin/python -m unittest discover services/editing/tests -v`
  - Passed: 93 tests.
- `git diff --check`
  - Passed.

## Launch Recommendation

Keep this fail-closed gate for internal TestFlight. Do not claim the selected-team 85% target until labeled video evals prove team ownership, shot outcome, blocks, steals, and uncertain-review behavior. Before using selected-team mode through the Worker in staging/prod, connect `team-scan` to a cloud-owned scan provider or route that request to the backend that can materialize the upload and run the scan.

## CI Evidence

After commit `2710235484d189b72475b3496f945cc6883c5f1e`, GitHub Actions created these PR runs:

- `Cloud Edit Deploy Preflight` run `26504067320`
  - Failed before any workflow steps were allocated.
  - Failed jobs: `Editing backend Python tests`, `Worker typecheck and dry run`.
  - GitHub annotation: `The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings`.
  - `Verify cloud edit deploy secrets` was skipped because prerequisite jobs did not start.
- `iOS Internal TestFlight Upload` run `26504067321`
  - Failed before any workflow steps were allocated.
  - Failed job: `No-secret internal staging codecheck`.
  - GitHub annotation: `The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings`.
  - `Build internal staging TestFlight archive` was skipped because this was a pull request codecheck run and the codecheck job did not start.

No failed-step logs were available because GitHub did not allocate runners.
